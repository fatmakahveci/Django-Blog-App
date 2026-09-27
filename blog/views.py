from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST, require_safe
from django.views.decorators.cache import never_cache

from .forms import CommentForm
from .engagement import engagement_context, reader_identity, remember_reader
from .models import Category, CollectionEntry, Poll, PollVote, Post, Reaction, Tag
from .rate_limits import client_digest, submission_retry_after


SORTS = {'newest': ('-published_at', '-pk'), 'oldest': ('published_at', 'pk'), 'discussed': ('-comment_count', '-published_at', '-pk')}


def render_listing(request, posts, title='Latest articles', description='', locked_order=None, **context):
    query = request.GET.get('q', '').strip()[:120]
    sort = request.GET.get('sort', 'newest')
    if sort not in SORTS:
        sort = 'newest'
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(body__icontains=query))
    posts = posts.with_card_data().order_by(*(locked_order or SORTS[sort]))
    featured = None
    if context.get('is_home') and not query and sort == 'newest':
        featured = posts.filter(featured=True).first()
        if featured:
            posts = posts.exclude(pk=featured.pk)
    page = Paginator(posts, 6).get_page(request.GET.get('page'))
    categories = Category.objects.filter(posts__in=Post.objects.published()).distinct()
    return render(request, 'blog/list.html', {
        'page_obj': page, 'categories': categories, 'title': title,
        'description': description, 'q': query, 'sort': sort,
        'locked_order': bool(locked_order),
        'featured': featured if page.number == 1 else None, **context,
    })


@require_safe
def home(request):
    return render_listing(request, Post.objects.published(), is_home=True)


@require_safe
def category(request, slug):
    topic = get_object_or_404(Category.objects.filter(posts__in=Post.objects.published()).distinct(), slug=slug)
    return render_listing(request, Post.objects.published().filter(category=topic), topic.name, topic.description, active_category=topic)


@require_safe
def tag(request, slug):
    topic = get_object_or_404(Tag.objects.filter(posts__in=Post.objects.published()).distinct(), slug=slug)
    return render_listing(request, Post.objects.published().filter(tags=topic), f'#{topic.name}', 'Stories connected by a shared idea.')


@require_safe
def author(request, pk):
    person = get_object_or_404(get_user_model().objects.filter(blog_posts__in=Post.objects.published()).distinct(), pk=pk)
    name = person.get_full_name() or 'Author'
    return render_listing(request, Post.objects.published().filter(author=person), name, 'Explore all published stories by this author.', author_page=True)


def detail_context(post, request, form=None):
    tags = list(post.tags.all())
    related_filter = Q(tags__in=tags)
    if post.category_id:
        related_filter |= Q(category_id=post.category_id)
    related = Post.objects.published().filter(related_filter).exclude(pk=post.pk).distinct().with_card_data()[:3]
    # A popular article must not load every approved comment into memory.
    comments = Paginator(post.comments.filter(approved=True), 20).get_page(request.GET.get('comments_page'))
    entries = post.collection_entries.filter(collection__is_public=True).select_related('collection')
    selected_collection = request.GET.get('collection', '')[:180]
    entry = entries.filter(collection__slug=selected_collection).first() if selected_collection else entries.order_by('collection__name', 'pk').first()
    path_context = {}
    if entry:
        neighbors = CollectionEntry.objects.filter(collection=entry.collection, post__in=Post.objects.published()).select_related('post')
        path_context = {
            'reading_collection': entry.collection,
            'previous_entry': neighbors.filter(Q(position__lt=entry.position) | Q(position=entry.position, pk__lt=entry.pk)).order_by('-position', '-pk').first(),
            'next_entry': neighbors.filter(Q(position__gt=entry.position) | Q(position=entry.position, pk__gt=entry.pk)).order_by('position', 'pk').first(),
        }
    return {
        'post': post, 'tags': tags, 'related_posts': related,
        'comments': comments, 'comment_page': comments,
        'comment_form': form if form is not None else CommentForm(),
        'canonical_path': post.get_absolute_url(),
        **engagement_context(post, request),
        **path_context,
    }


@never_cache
@require_safe
def post_detail(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    return render(request, 'blog/detail.html', detail_context(post, request))


def feedback_error(request, post, message, status=400):
    messages.error(request, message)
    return render(request, 'blog/detail.html', detail_context(post, request), status=status)


def feedback_limit_response(request, post):
    retry_after = submission_retry_after(request, 'feedback', 30)
    if retry_after:
        response = feedback_error(request, post, 'Too many responses from this connection. Please try again in a few minutes.', status=429)
        response['Retry-After'] = str(retry_after)
        return response


@never_cache
@require_POST
def react(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    kind = request.POST.get('kind', '')
    if kind not in {*Reaction.Kind.values, 'remove'}:
        return feedback_error(request, post, 'Choose a reaction from the available options.')
    limited = feedback_limit_response(request, post)
    if limited is not None:
        return limited
    digest, token = reader_identity(request, create=kind != 'remove')
    if kind == 'remove':
        post.reactions.filter(reader_digest=digest).delete()
        messages.success(request, 'Your reaction was removed.')
    else:
        Reaction.objects.update_or_create(post=post, reader_digest=digest, defaults={'kind': kind})
        messages.success(request, 'Thank you. Your reaction has been saved.')
    return remember_reader(redirect(post.get_absolute_url() + '#reactions'), token)


@never_cache
@require_POST
def vote(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    poll = get_object_or_404(Poll, post=post)
    if not poll.is_open:
        return feedback_error(request, post, 'This poll is closed. You can still see the results.', status=409)
    raw_choice = request.POST.get('choice', '')
    choice = poll.choices.filter(pk=int(raw_choice)).first() if raw_choice.isascii() and raw_choice.isdigit() and len(raw_choice) <= 10 else None
    if not choice or poll.choices.count() < 2:
        return feedback_error(request, post, 'Choose an answer from this poll.')
    limited = feedback_limit_response(request, post)
    if limited is not None:
        return limited
    digest, token = reader_identity(request, create=True)
    _, created = PollVote.objects.get_or_create(poll=poll, reader_digest=digest, defaults={'choice': choice})
    messages.success(request, 'Your vote is in. Thank you for taking part.' if created else 'You have already voted in this poll.')
    return remember_reader(redirect(post.get_absolute_url() + '#reader-poll'), token)


@never_cache
@require_POST
def add_comment(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    form = CommentForm(request.POST)
    if form.is_valid():
        retry_after = submission_retry_after(request, 'comment', 3)
        if retry_after:
            form.add_error(None, 'You have posted several comments recently. Please try again in 10 minutes.')
            response = render(request, 'blog/detail.html', detail_context(post, request, form), status=429)
            response['Retry-After'] = str(retry_after)
            return response
        comment = form.save(commit=False)
        comment.post = post
        comment.client_digest = client_digest(request, 'comment')
        comment.save()
        messages.success(request, 'Thank you for your comment. It will appear here after approval.')
        return redirect(post.get_absolute_url() + '#comments')
    return render(request, 'blog/detail.html', detail_context(post, request, form), status=400)


@never_cache
@require_safe
def reading_list(request):
    # Bound both input size and SQL parameters. Only public posts can be returned.
    raw = request.GET.get('ids', '')[:1200].split(',')[:100]
    ids = [int(value) for value in raw if value.isascii() and value.isdigit() and len(value) <= 10]
    return render_listing(request, Post.objects.published().filter(pk__in=ids), 'Reading list', 'Ideas to come back to. This list is saved only in this browser.', is_reading_list=True)


@require_safe
def robots(request):
    sitemap_url = request.build_absolute_uri(reverse('sitemap'))
    return HttpResponse(f'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /reading-list/\nDisallow: /reading-history/\nDisallow: /for-you/\nSitemap: {sitemap_url}\n', content_type='text/plain')
