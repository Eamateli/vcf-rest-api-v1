"""URL routes for the variants API."""

from django.urls import path

from api.views import VariantListView

urlpatterns = [
    path("variants", VariantListView.as_view(), name="variant-list"),
]
