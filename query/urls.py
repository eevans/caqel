
from django.conf.urls.defaults import *
from django.conf import settings

urlpatterns = patterns('',
    (r'^$', 'query.views.index'),
    (r'^query/$', 'query.views.query'),
    (r'^describe/keyspaces/$', 'query.views.describe_keyspaces'),
    (r'^static/(?P<path>.*)$', 'django.views.static.serve',
            {'document_root': settings.STATIC_DOCROOT, 'show_indexes': True}),
)
