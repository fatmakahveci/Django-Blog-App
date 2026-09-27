from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from .models import Post


class PostSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.7

    def items(self):
        return Post.objects.published()

    def lastmod(self, item):
        return item.updated_at


class HomeSitemap(Sitemap):
    changefreq = 'daily'
    priority = 1.0

    def items(self):
        return ['home', 'discover', 'collections']

    def location(self, item):
        return reverse(item)


class CollectionSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.6

    def items(self):
        from .discovery import public_collections
        return public_collections()
