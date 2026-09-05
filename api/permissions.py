"""Shared-secret authorisation for write requests."""

import hmac

from django.conf import settings
from rest_framework.permissions import BasePermission
from rest_framework.request import Request

READ_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


class HasWriteSecret(BasePermission):
    """Reads are open. Writes need Authorization to equal VCF_API_SECRET."""

    def has_permission(self, request: Request, view) -> bool:
        if request.method in READ_METHODS:
            return True

        expected = settings.VCF_API_SECRET
        if not expected:
            # An unset secret must deny every write, never match an empty header.
            return False

        provided = request.headers.get("Authorization", "")
        return hmac.compare_digest(provided, expected)
