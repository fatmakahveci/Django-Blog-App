"""Reader discovery pages, all using the shared publication visibility rule."""
from datetime import timedelta
import secrets

from django.core.paginator import Paginator
from django.db.models import Case, Count, IntegerField, OuterRef, Q, Subquery, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from .models import Category, Collection, Comment, Post, Reaction
from .views import render_listing


def bounded_ids(raw, limit=20):
    values = (raw or '')[:limit * 11].split(',')[:limit]
    return list(dict.fromkeys(int(value) for value in values if value.isascii() and value.isdigit() and len(value) <= 10))


def public_collections():
    return Collection.objects.filter(is_public=True).annotate(
        article_count=Count('posts', filter=Q(posts__in=Post.objects.published())),
    ).filter(article_count__gt=0).order_by('name', 'pk')


@require_safe
def discover(request):
    posts = Post.objects.published()
    length = request.GET.get('length', '')
    if length == 'short':
        posts = posts.filter(word_count__lte=600)
    elif length == 'medium':
        posts = posts.filter(word_count__gt=600, word_count__lte=1400)
    elif length == 'long':
        posts = posts.filter(word_count__gt=1400)
    else:
        length = ''
    topics = Category.objects.annotate(article_count=Count('posts', filter=Q(posts__in=Post.objects.published()))).filter(article_count__gt=0).order_by('name', 'pk')
    return render_listing(request, posts, 'Discover', 'A fresh perspective is a good place to start.',
                          is_discover=True, length=length, topics=topics,
                          collections=public_collections()[:3])


@require_safe
def trending(request):
    since = timezone.now() - timedelta(days=7)
    # Separate aggregate subqueries avoid multiplying comments by reactions.
    reactions = Reaction.objects.filter(post_id=OuterRef('pk'), created_at__gte=since).order_by().values('post_id').annotate(total=Count('pk')).values('total')
    comments = Comment.objects.filter(post_id=OuterRef('pk'), approved=True, created_at__gte=since).order_by().values('post_id').annotate(total=Count('pk')).values('total')
    posts = Post.objects.published().annotate(
        weekly_score=Coalesce(Subquery(reactions), 0) + Coalesce(Subquery(comments), 0),
    ).filter(weekly_score__gt=0)
    return render_listing(request, posts, 'Trending this week',
                          'Ranked by reactions and approved comments from the last seven days. Every response counts equally.',
                          is_trending=True, locked_order=('-weekly_score', '-published_at', '-pk'))


@never_cache
@require_safe
def for_you(request):
    ids = bounded_ids(request.GET.get('topics'))
    return render_listing(request, Post.objects.published().filter(category_id__in=ids), 'For you',
                          'The latest stories from topics you follow. Your choices stay in this browser.', is_for_you=True)


@never_cache
@require_safe
def reading_history(request):
    ids = bounded_ids(request.GET.get('ids'))
    order = Case(*[When(pk=pk, then=position) for position, pk in enumerate(ids)], default=len(ids), output_field=IntegerField())
    posts = Post.objects.published().filter(pk__in=ids).annotate(history_position=order)
    return render_listing(request, posts, 'Continue reading',
                          'Your 20 most recently opened stories, saved only in this browser.', is_history=True,
                          locked_order=('history_position',))


@require_safe
def collections(request):
    page = Paginator(public_collections(), 12).get_page(request.GET.get('page'))
    return render(request, 'blog/collections.html', {'page_obj': page, 'is_collections': True})


@require_safe
def collection_detail(request, slug):
    collection = get_object_or_404(public_collections(), slug=slug)
    posts = Post.objects.published().filter(collections=collection).with_card_data().order_by('collection_entries__position', 'collection_entries__pk')
    page = Paginator(posts, 12).get_page(request.GET.get('page'))
    return render(request, 'blog/collection_detail.html', {
        'collection': collection, 'page_obj': page, 'is_collections': True,
        'canonical_path': collection.get_absolute_url(),
    })


@never_cache
@require_safe
def surprise(request):
    posts = Post.objects.published().order_by('pk')
    count = posts.count()
    if not count:
        return redirect('discover')
    # Choose an offset without sorting the entire table by a random expression.
    post = posts.only('slug')[secrets.randbelow(count):][:1].first()
    return redirect(post.get_absolute_url() if post else 'discover')
