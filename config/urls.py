from django.contrib import admin
from django.urls import path, include, re_path
from django.conf import settings
from django.contrib.staticfiles.views import serve as serve_staticfiles
from django.views.static import serve as serve_media
from django.views.generic import TemplateView

admin.site.site_header = 'Bristol Food Network Admin'
admin.site.site_title = 'BFN Admin'
admin.site.index_title = 'Marketplace Operations'

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', TemplateView.as_view(template_name='home.html'), name='home'),
    path('accounts/', include('accounts.urls')),
    path('products/', include('products.urls')),
    path('cart/', include('cart.urls')),
    path('orders/', include('orders.urls')),
]

if settings.DEBUG or getattr(settings, 'LOCAL_STATIC_SERVE', False):
    urlpatterns += [
        re_path(r'^static/(?P<path>.*)$', serve_staticfiles, {'insecure': True}),
        re_path(r'^media/(?P<path>.*)$', serve_media, {'document_root': settings.MEDIA_ROOT}),
    ]
