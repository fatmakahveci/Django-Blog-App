from django.contrib import admin

from .models import Category, Comment, Post, Tag


@admin.register(Category, Tag)
class TopicAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    search_fields = ['name']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'status', 'published_at', 'featured']
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
