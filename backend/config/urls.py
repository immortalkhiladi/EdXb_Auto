from django.urls import include, path, re_path

from portal.views import common

urlpatterns = [
    path("api/", include("portal.urls")),
    re_path(r"^api/.*$", common.api_not_found),
    re_path(r"^.*$", common.spa),  # React single-page app (client-side routing)
]
