from django.urls import path
from django.contrib.sitemaps.views import sitemap

from . import views
from .feeds import LatestPostsFeed
from .sitemaps import HomeSitemap, PostSitemap

urlpatterns = [
    path('', views.home, name='home'),
    path('posts/<slug:slug>/', views.post_detail, name='post_detail'),
    path('posts/<slug:slug>/comments/', views.add_comment, name='add_comment'),
    path('categories/<slug:slug>/', views.category, name='category'),
    path('tags/<slug:slug>/', views.tag, name='tag'),
    path('authors/<int:pk>/', views.author, name='author'),
    path('reading-list/', views.reading_list, name='reading_list'),
    path('rss/', LatestPostsFeed(), name='rss'),
    path('sitemap.xml', sitemap, {'sitemaps': {'home': HomeSitemap, 'posts': PostSitemap}}, name='sitemap'),
    path('robots.txt', views.robots, name='robots'),
]
