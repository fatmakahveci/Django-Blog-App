from django.contrib.syndication.views import Feed
from django.urls import reverse_lazy
from django.utils.html import escape

from .models import Post


class LatestPostsFeed(Feed):
    title = 'Folio · Latest articles'
    link = reverse_lazy('home')
    description = 'Notes on technology, design, and everyday life.'

    def items(self):
        return Post.objects.published().select_related('author')[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        # RSS readers may interpret descriptions as HTML after decoding XML.
        return escape(item.summary)

    def item_pubdate(self, item):
        return item.published_at

    def item_author_name(self, item):
        return item.author_name
