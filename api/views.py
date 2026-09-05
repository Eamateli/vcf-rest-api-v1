"""HTTP endpoints. Translates requests into vcf_core calls and back."""

from django.conf import settings
from rest_framework.exceptions import ParseError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pagination import paginated_response_body
from vcf_core.pagination import DEFAULT_LIMIT
from vcf_core.repository import VcfRepository


def _pagination_params(request: Request) -> tuple[int, int]:
    """Read offset and limit from the query string, rejecting nonsense with 400."""
    try:
        offset = int(request.query_params.get("offset", 0))
        limit = int(request.query_params.get("limit", DEFAULT_LIMIT))
    except ValueError as exc:
        raise ParseError("offset and limit must be integers") from exc

    if offset < 0 or limit < 1:
        raise ParseError("offset must be 0 or greater and limit must be 1 or greater")

    return offset, limit


class VariantListView(APIView):
    """GET /variants - one page of variants from the configured VCF."""

    def get(self, request: Request) -> Response:
        offset, limit = _pagination_params(request)
        repository = VcfRepository(settings.VCF_PATH)
        page = repository.list_variants(offset=offset, limit=limit)
        return Response(paginated_response_body(page, request))
