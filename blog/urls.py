from django.urls import path
from django.contrib.sitemaps.views import sitemap

from . import discovery, views
from .feeds import LatestPostsFeed
from .sitemaps import CollectionSitemap, HomeSitemap, PostSitemap

urlpatterns = [
    path('', views.home, name='home'),
    path('discover/', discovery.discover, name='discover'),
    path('trending/', discovery.trending, name='trending'),
    path('for-you/', discovery.for_you, name='for_you'),
    path('reading-history/', discovery.reading_history, name='reading_history'),
    path('collections/', discovery.collections, name='collections'),
    path('collections/<slug:slug>/', discovery.collection_detail, name='collection_detail'),
    path('surprise/', discovery.surprise, name='surprise'),
    path('posts/<slug:slug>/', views.post_detail, name='post_detail'),
    path('posts/<slug:slug>/comments/', views.add_comment, name='add_comment'),
    path('posts/<slug:slug>/react/', views.react, name='react'),
    path('posts/<slug:slug>/vote/', views.vote, name='vote'),
    path('categories/<slug:slug>/', views.category, name='category'),
    path('tags/<slug:slug>/', views.tag, name='tag'),
    path('authors/<int:pk>/', views.author, name='author'),
    path('reading-list/', views.reading_list, name='reading_list'),
    path('rss/', LatestPostsFeed(), name='rss'),
    path('sitemap.xml', sitemap, {'sitemaps': {'home': HomeSitemap, 'posts': PostSitemap, 'collections': CollectionSitemap}}, name='sitemap'),
    path('robots.txt', views.robots, name='robots'),
]
