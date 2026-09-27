from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from django.forms.models import BaseInlineFormSet
from django.http import Http404
from django.shortcuts import render
from django.urls import path
from django.utils import timezone
from django.views.decorators.http import require_safe

from .models import Category, Collection, CollectionEntry, Comment, Poll, PollChoice, Post, Tag


admin.site.site_header = 'Folio editor'
admin.site.site_title = 'Folio editor'
admin.site.index_title = 'Your publication'
admin.site.index_template = 'blog/editor_index.html'


@admin.register(Category, Tag)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'publication_state', 'published_at', 'featured']
    change_form_template = 'blog/editor_post_form.html'
    save_on_top = True
    list_filter = ['status', 'featured', 'category', 'published_at']
    search_fields = ['title', 'excerpt', 'body']
    autocomplete_fields = ['category', 'tags']
    list_select_related = ['author', 'category']
    date_hierarchy = 'published_at'
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = [
        ('Article', {'fields': ['title', 'excerpt', 'body', 'author']}),
        ('Presentation', {'fields': ['category', 'tags', 'cover_style', 'featured']}),
        ('Publication', {'fields': ['status', 'published_at', 'slug', 'created_at', 'updated_at']}),
    ]

    def get_urls(self):
        return [
            path('<int:object_id>/preview/', self.admin_site.admin_view(require_safe(self.preview)),
                 name='blog_app_post_preview'),
            *super().get_urls(),
        ]

    def preview(self, request, object_id):
        # Staff membership alone must never grant access to unpublished work.
        if not self.has_view_or_change_permission(request):
            raise PermissionDenied
        post = self.get_object(request, object_id)
        if post is None:
            raise Http404
        if not self.has_view_or_change_permission(request, post):
            raise PermissionDenied
        response = render(request, 'blog/detail.html', {
            'post': post, 'tags': post.tags.all(), 'is_preview': True,
            'preview_status': self.publication_state(post),
            'can_edit_post': self.has_change_permission(request, post),
        })
        response['X-Robots-Tag'] = 'noindex, nofollow'
        return response

    @admin.display(description='Visibility', ordering='status')
    def publication_state(self, obj):
        if obj.status == Post.Status.DRAFT:
            return 'Draft — private'
        if obj.published_at > timezone.now():
            return 'Scheduled — private until publication'
        return 'Published — public'

    def view_on_site(self, obj):
        if obj.status == Post.Status.PUBLISHED and obj.published_at <= timezone.now():
            return obj.get_absolute_url()
        return None

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, text in {
            'body': 'Write plain text. Separate paragraphs with a blank line; HTML is displayed as text.',
            'excerpt': 'Optional summary for article cards. Leave blank to use the beginning of your article.',
            'slug': 'Optional. Leave blank to generate a permanent link from the title.',
            'status': 'Drafts stay private. Choose Published / scheduled to make this article available at the publication time.',
        }.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

    def get_changeform_initial_data(self, request):
        return {'author': request.user.pk}

    def get_readonly_fields(self, request, obj=None):
        # Published links remain stable when an editor changes the title.
        return [*super().get_readonly_fields(request, obj), *(['slug'] if obj else [])]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ['name', 'post', 'approved', 'created_at']
    list_filter = ['approved', 'created_at']
    search_fields = ['name', 'body', 'post__title']
    list_select_related = ['post']
    readonly_fields = ['created_at']
    actions = ['approve', 'hide']

    @admin.action(description='Approve selected comments', permissions=['change'])
    def approve(self, request, queryset):
        self.message_user(request, f'{queryset.update(approved=True)} comments approved.')

    @admin.action(description='Hide selected comments', permissions=['change'])
    def hide(self, request, queryset):
        self.message_user(request, f'{queryset.update(approved=False)} comments hidden.')


class CollectionEntryInline(admin.TabularInline):
    model = CollectionEntry
    autocomplete_fields = ['post']
    extra = 1


@admin.register(Collection)
class CollectionAdmin(TopicAdmin):
    list_display = ['name', 'is_public']
    list_filter = ['is_public']
    fields = ['name', 'slug', 'description', 'is_public']
    inlines = [CollectionEntryInline]


class PollChoiceFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        labels = [form.cleaned_data['label'].strip().casefold() for form in self.forms
                  if form.cleaned_data and not form.cleaned_data.get('DELETE') and 'label' in form.cleaned_data]
        if len(labels) != len(set(labels)):
            raise ValidationError('Each poll answer must be different.')


class PollChoiceInline(admin.TabularInline):
    model = PollChoice
    formset = PollChoiceFormSet
    extra = 0
    min_num = 2
    max_num = 4

    def get_formset(self, request, obj=None, **kwargs):
        # Django sets max_num=0 when adding is forbidden; existing answers remain valid.
        return super().get_formset(request, obj, validate_min=True,
                                   validate_max=self.has_add_permission(request, obj), **kwargs)

    def get_readonly_fields(self, request, obj=None):
        return ['label', 'position'] if obj and obj.votes.exists() else []

    def has_add_permission(self, request, obj=None):
        return super().has_add_permission(request, obj) and not (obj and obj.votes.exists())

    def has_delete_permission(self, request, obj=None):
        return super().has_delete_permission(request, obj) and not (obj and obj.votes.exists())


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ['question', 'post', 'is_open']
    list_filter = ['is_open']
    list_select_related = ['post']
    search_fields = ['question', 'post__title']
    autocomplete_fields = ['post']
    inlines = [PollChoiceInline]

    def get_readonly_fields(self, request, obj=None):
        # Keep votes meaningful: answers and the question are fixed after voting.
        return ['post', 'question'] if obj and obj.votes.exists() else []
