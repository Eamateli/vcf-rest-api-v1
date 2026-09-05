"""HTTP endpoints. Translates requests into vcf_core calls and back."""

from django.conf import settings
from rest_framework.exceptions import NotFound, ParseError
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from api.pagination import paginated_response_body
from api.serializers import VariantSerializer
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
    """GET /variants - a page of variants, or the rows matching ?id=."""

    def get(self, request: Request) -> Response:
        repository = VcfRepository(settings.VCF_PATH)

        variant_id = request.query_params.get("id")
        if variant_id is not None:
            return self._matching_id(repository, variant_id)

        offset, limit = _pagination_params(request)
        page = repository.list_variants(offset=offset, limit=limit)
        return Response(paginated_response_body(page, request))

    def _matching_id(self, repository: VcfRepository, variant_id: str) -> Response:
        """Every row with this ID, or 404 when none match."""
        matches = repository.find_by_id(variant_id)
        if not matches:
            raise NotFound(f"No variant matches id {variant_id!r}.")
        return Response(VariantSerializer(matches, many=True).data)
