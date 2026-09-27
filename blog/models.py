import math
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.db import models
from django.db.models import Count, Q
from django.urls import reverse
from django.utils import timezone
from django.utils.text import Truncator, slugify


def new_slug(model, text):
    base = slugify(text)[:150] or 'note'
    if model.objects.filter(slug=base).exists():
        return f'{base}-{uuid4().hex[:12]}'
    return base


class Topic(models.Model):
    name = models.CharField(max_length=60, unique=True)
    slug = models.SlugField(max_length=180, unique=True, blank=True)

    class Meta:
        abstract = True
        ordering = ['name']

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = new_slug(type(self), self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Category(Topic):
    description = models.CharField(max_length=240, blank=True)

    class Meta(Topic.Meta):
        verbose_name_plural = 'categories'

    def get_absolute_url(self):
        return reverse('category', kwargs={'slug': self.slug})


class Tag(Topic):
    def get_absolute_url(self):
        return reverse('tag', kwargs={'slug': self.slug})


class PostQuerySet(models.QuerySet):
    def published(self):
        # Every public surface shares this rule, including feeds and sitemaps.
        return self.filter(status='published', published_at__lte=timezone.now())

    def with_card_data(self):
        return self.select_related('author', 'category').prefetch_related('tags').annotate(
            comment_count=Count('comments', filter=Q(comments__approved=True), distinct=True),
        )


class Post(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'draft', 'Draft'
        PUBLISHED = 'published', 'Published / scheduled'

    class Cover(models.TextChoices):
        SAGE = 'sage', 'Sage'
        INK = 'ink', 'Ink'
        CLAY = 'clay', 'Clay'
        SKY = 'sky', 'Sky'

    title = models.CharField(max_length=180)
    slug = models.SlugField(max_length=180, unique=True, blank=True)
    excerpt = models.CharField(max_length=300, blank=True)
    body = models.TextField(validators=[MinLengthValidator(20)])
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='blog_posts')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, blank=True, related_name='posts')
    tags = models.ManyToManyField(Tag, blank=True, related_name='posts')
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.DRAFT)
    published_at = models.DateTimeField(default=timezone.now, help_text='A future date keeps the article private until that time. Time zone: UTC.')
    featured = models.BooleanField(default=False)
    cover_style = models.CharField(max_length=10, choices=Cover.choices, default=Cover.SAGE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ['-published_at', '-pk']
        indexes = [models.Index(fields=['status', 'published_at'], name='post_publication_idx')]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = new_slug(type(self), self.title)
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse('post_detail', kwargs={'slug': self.slug})

    @property
    def summary(self):
        return self.excerpt or Truncator(self.body).words(35)

    @property
    def reading_minutes(self):
        return max(1, math.ceil(len(self.body.split()) / 200))

    @property
    def author_name(self):
        return self.author.get_full_name() or 'Author'

    def __str__(self):
        return self.title


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
    name = models.CharField(max_length=80)
    body = models.TextField(max_length=2000, validators=[MinLengthValidator(10)])
    approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # A keyed digest supports spam limits without storing raw IP addresses.
    client_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        ordering = ['created_at', 'pk']
        indexes = [
            models.Index(fields=['post', 'approved', 'created_at', 'id'], name='comment_public_page_idx'),
            models.Index(fields=['client_digest', 'created_at'], name='comment_rate_limit_idx'),
        ]

    def __str__(self):
        return f'{self.name}: {self.body[:50]}'
