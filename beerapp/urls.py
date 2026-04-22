from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    path("analytics/", include("analytics.urls")),
    path("", include("beers.urls")),
]
