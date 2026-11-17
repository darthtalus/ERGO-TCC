from django.conf import settings
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('pages.urls')),
    path('admin/', admin.site.urls),
    path('login/', include('accounts.urls')),
    path('tasks/', include('tasks.urls')),
    path('upgrades/', include('upgrades.urls')), 
    path('params/', include('user_aspects.urls')),
    path('reports/', include([
        path('', include('user_aspects.urls_reports')),
    ])),
    path('i18n/', include('django.conf.urls.i18n')),
]

handler404 = 'pages.views.custom_404'
handler500 = 'pages.views.custom_500'

if settings.DEBUG:
    urlpatterns = [
        path('__debug__/', include('debug_toolbar.urls')),
    ] + urlpatterns
if settings.DEBUG:
    from ergo.media_views import public_media_serve

    urlpatterns += [
        path(f"{settings.MEDIA_URL.lstrip('/')}<path:path>", public_media_serve),
    ]
