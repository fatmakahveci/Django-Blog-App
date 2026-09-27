from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.views.decorators.http import require_POST, require_safe
from django.views.decorators.cache import never_cache

from .forms import CommentForm
from .models import Category, Comment, Post, Tag


SORTS = {'newest': ('-published_at', '-pk'), 'oldest': ('published_at', 'pk'), 'discussed': ('-comment_count', '-published_at', '-pk')}


def render_listing(request, posts, title='Latest articles', description='', **context):
    query = request.GET.get('q', '').strip()[:120]
    sort = request.GET.get('sort', 'newest')
    if sort not in SORTS:
        sort = 'newest'
    if query:
        posts = posts.filter(Q(title__icontains=query) | Q(excerpt__icontains=query) | Q(body__icontains=query))
    posts = posts.with_card_data().order_by(*SORTS[sort])
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
        'featured': featured if page.number == 1 else None, **context,
    })


@require_safe
def home(request):
    return render_listing(request, Post.objects.published(), is_home=True)


@require_safe
def category(request, slug):
    topic = get_object_or_404(Category, slug=slug)
    return render_listing(request, Post.objects.published().filter(category=topic), topic.name, topic.description, active_category=topic)


@require_safe
def tag(request, slug):
    topic = get_object_or_404(Tag, slug=slug)
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
    return {
        'post': post, 'tags': tags, 'related_posts': related,
        'comments': comments, 'comment_page': comments,
        'comment_form': form if form is not None else CommentForm(),
        'canonical_path': post.get_absolute_url(),
    }


@require_safe
def post_detail(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    return render(request, 'blog/detail.html', detail_context(post, request))


@never_cache
@require_POST
def add_comment(request, slug):
    post = get_object_or_404(Post.objects.published().with_card_data(), slug=slug)
    form = CommentForm(request.POST)
    if form.is_valid():
        digest = salted_hmac('blog.comment-client', request.META.get('REMOTE_ADDR', ''), algorithm='sha256').hexdigest()
        recent = Comment.objects.filter(client_digest=digest, created_at__gte=timezone.now() - timedelta(minutes=10))
        # Check only for the third row; counting a spam backlog is unnecessary.
        if recent.order_by().values('pk')[2:3].exists():
            form.add_error(None, 'You have posted several comments recently. Please try again in 10 minutes.')
            response = render(request, 'blog/detail.html', detail_context(post, request, form), status=429)
            response['Retry-After'] = '600'
            return response
        comment = form.save(commit=False)
        comment.post = post
        comment.client_digest = digest
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
    return HttpResponse(f'User-agent: *\nAllow: /\nDisallow: /admin/\nDisallow: /reading-list/\nSitemap: {sitemap_url}\n', content_type='text/plain')
