from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def health_check(request):
    return JsonResponse({"status": "ok"})


urlpatterns = [
    path("health/", health_check),
    path("django-admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.accounts.urls")),
    path("api/v1/events/", include("apps.events.urls")),
    path("api/v1/tickets/", include("apps.tickets.urls")),
    path("api/v1/orders/", include("apps.orders.urls")),
    path("api/v1/companies/", include("apps.companies.urls")),
    path("api/v1/admin/", include("apps.audit.urls")),
    path("api/v1/withdrawals/", include("apps.withdrawals.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
