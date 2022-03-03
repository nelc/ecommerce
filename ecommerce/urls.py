

import os

from auth_backends.urls import oauth2_urlpatterns
from django.conf import settings
from django.conf.urls import include
from django.conf.urls.static import static
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, re_path
from django.utils.translation import gettext_lazy as _
from django.views.defaults import page_not_found, server_error
from django.views.generic import TemplateView
from django.views.i18n import JavaScriptCatalog
from drf_yasg import openapi
from drf_yasg.views import get_schema_view
from rest_framework import permissions

from ecommerce.core import views as core_views
from ecommerce.core.url_utils import get_lms_dashboard_url
from ecommerce.core.views import LogoutView
from ecommerce.extensions.payment.views.apple_pay import ApplePayMerchantDomainAssociationView
from ecommerce.extensions.urls import urlpatterns as extensions_patterns


def handler403(_, exception):  # pylint: disable=unused-argument
    """Redirect unauthorized users to the LMS student dashboard.

    Removing URLs isn't the most elegant way to hide Oscar's front-end from
    public view. It would require revising templates and parts of the Oscar core
    which assume that these URLs exist. However, a clean way to, in effect,
    disable these URLs is to only make them available to users with staff
    permissions, the same protection used to guard the management dashboard from
    public access.

    This minimally invasive approach allows us to protect Oscar's front-end
    without sacrificing any internal functionality. Users not authorized to view
    Oscar's front-end are redirected to the LMS student dashboard, as one would
    usually be after signing into the LMS.
    """
    return redirect(get_lms_dashboard_url())


admin.autodiscover()
admin.site.site_header = _('E-Commerce Service Administration')
admin.site.site_title = admin.site.site_header

# NOTE 1: Add our logout override first to ensure it is registered by Django as the actual logout view.
# NOTE 2: These same patterns are used for rest_framework's browseable API authentication links.
AUTH_URLS = [path('logout/', LogoutView.as_view(), name='logout'), ] + oauth2_urlpatterns

WELL_KNOWN_URLS = [
    re_path(r'^.well-known/apple-developer-merchantid-domain-association.txt$',
            ApplePayMerchantDomainAssociationView.as_view(), name='apple_pay_domain_association'),
]

schema_view = get_schema_view(
    openapi.Info(
        title="Ecommerce API",
        default_version='v2',
        description="Ecommerce docs",
    ),
    public=False,
    permission_classes=[permissions.AllowAny],
)

urlpatterns = AUTH_URLS + WELL_KNOWN_URLS + [
    path('admin/', admin.site.urls),
    path('auto_auth/', core_views.AutoAuth.as_view(), name='auto_auth'),
    path('api-auth/', include((AUTH_URLS, 'rest_framework'))),
    path('api-docs/', schema_view.with_ui('swagger', cache_timeout=0), name='api_docs'),
    path('bff/', include(('ecommerce.bff.urls', 'bff'))),
    path('courses/', include(('ecommerce.courses.urls', 'courses'))),
    path('credit/', include(('ecommerce.credit.urls', 'credit'))),
    path('coupons/', include(('ecommerce.coupons.urls', 'coupons'))),
    path('enterprise/', include(('ecommerce.enterprise.urls', 'enterprise'))),
    path('health/', core_views.health, name='health'),
    path('i18n/', include(('django.conf.urls.i18n'))),
    path('jsi18n/', JavaScriptCatalog.as_view(), name='javascript-catalog'),
    path('management/', include(('ecommerce.management.urls', 'management'))),
    path('offers/', include(('ecommerce.extensions.offer.urls', 'offers'))),
    path('programs/', include(('ecommerce.programs.urls', 'programs'))),
]

# Install Oscar extension URLs
urlpatterns += extensions_patterns

robots = TemplateView.as_view(template_name='robots.txt', content_type='text/plain')
urlpatterns += [
    re_path(r'^robots\.txt$', robots, name='robots')
]

# edx-drf-extensions csrf app
urlpatterns += [
    path('', include('csrf.urls')),
]

if settings.DEBUG and settings.MEDIA_ROOT:  # pragma: no cover
    urlpatterns += static(
        settings.MEDIA_URL,
        document_root=settings.MEDIA_ROOT
    )

if settings.DEBUG:  # pragma: no cover
    urlpatterns += [
        path('403/', handler403, name='403'),
        path('404/', page_not_found, name='404'),
        path('500/', server_error, name='500'),
        path('bootstrap/', TemplateView.as_view(template_name='bootstrap-demo.html')),
    ]
    # Allow error pages to be tested

    if os.environ.get('ENABLE_DJANGO_TOOLBAR', False):
        import debug_toolbar  # pylint: disable=import-error, wrong-import-position,wrong-import-order

        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls))
        ]
