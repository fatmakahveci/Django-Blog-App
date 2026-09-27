from django.apps import AppConfig


class BlogConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'blog'
    verbose_name = 'Publication'
    # The Python package was renamed, but migrations and content types still
    # identify this app as blog_app. Keep this label stable for existing databases.
    label = 'blog_app'
