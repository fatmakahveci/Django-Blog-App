import math
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinLengthValidator
from django.core.exceptions import ValidationError
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
    word_count = models.PositiveIntegerField(default=0, editable=False)
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
        # Store the count for database-side reading-length filters.
        self.word_count = len(self.body.split())
        if kwargs.get('update_fields') and 'body' in kwargs['update_fields']:
            kwargs['update_fields'] = {*kwargs['update_fields'], 'word_count'}
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


class SubmissionQuota(models.Model):
    # Separate keyed digests for each action group; never persist raw IPs.
    key = models.CharField(max_length=64, primary_key=True, editable=False)
    expires_at = models.DateTimeField(db_index=True)
    used = models.PositiveSmallIntegerField(default=0)


class Collection(Topic):
    description = models.CharField(max_length=300)
    is_public = models.BooleanField(default=False)
    posts = models.ManyToManyField(Post, through='CollectionEntry', related_name='collections')

    def get_absolute_url(self):
        return reverse('collection_detail', kwargs={'slug': self.slug})


class CollectionEntry(models.Model):
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name='entries')
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='collection_entries')
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['position', 'pk']
        constraints = [models.UniqueConstraint(fields=['collection', 'post'], name='unique_collection_post')]

    def __str__(self):
        return f'{self.position}. {self.post.title}'


class Reaction(models.Model):
    class Kind(models.TextChoices):
        USEFUL = 'useful', 'Useful'
        INSIGHTFUL = 'insightful', 'Insightful'
        INSPIRING = 'inspiring', 'Inspiring'

    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='reactions')
    kind = models.CharField(max_length=12, choices=Kind.choices)
    reader_digest = models.CharField(max_length=64, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['post', 'reader_digest'], name='unique_reader_reaction')]
        indexes = [models.Index(fields=['post', 'created_at'], name='reaction_activity_idx')]


class Poll(models.Model):
    post = models.OneToOneField(Post, on_delete=models.CASCADE, related_name='poll')
    question = models.CharField(max_length=180)
    is_open = models.BooleanField(default=True)

    def __str__(self):
        return self.question


class PollChoice(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='choices')
    label = models.CharField(max_length=120)
    position = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['position', 'pk']

    def __str__(self):
        return self.label


class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='votes')
    choice = models.ForeignKey(PollChoice, on_delete=models.CASCADE, related_name='votes')
    reader_digest = models.CharField(max_length=64, editable=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['poll', 'reader_digest'], name='unique_reader_poll_vote')]

    def clean(self):
        if self.choice_id and self.poll_id and self.choice.poll_id != self.poll_id:
            raise ValidationError({'choice': 'Choose an answer from this poll.'})
