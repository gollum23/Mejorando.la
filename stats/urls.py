from django.conf.urls.defaults import patterns, url

urlpatterns = patterns('',
    url(r'^$', 'stats.views.home'),
    url(r'^cursos/(?P<curso_slug>.+?)/(?P<version>\d+)?/?$', 'stats.views.single'),
)