"""Turn a core Page into the JSON body the API returns."""

from typing import Any

from rest_framework.request import Request

from api.serializers import VariantSerializer
from vcf_core.models import Variant
from vcf_core.pagination import Page


def _page_url(request: Request, offset: int, limit: int) -> str:
    """The current URL with offset and limit replaced, other params kept."""
    query = request.query_params.copy()
    query["offset"] = offset
    query["limit"] = limit
    return request.build_absolute_uri(f"{request.path}?{query.urlencode()}")


def paginated_response_body(page: Page[Variant], request: Request) -> dict[str, Any]:
    """The response body: navigation links plus this page's variants."""
    return {
        "next": _page_url(request, page.next_offset, page.limit) if page.has_next else None,
        "previous": (
            _page_url(request, page.previous_offset, page.limit)
            if page.previous_offset is not None
            else None
        ),
        "results": VariantSerializer(page.items, many=True).data,
    }
