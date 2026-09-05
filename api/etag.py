"""ETag computation for GET responses (requirement 1c)."""

import hashlib
import os
from urllib.parse import urlencode

from django.conf import settings
from rest_framework.request import Request


def compute_etag(request: Request, media_type: str) -> str:
    """Fingerprint this request: path + sorted query params + negotiated media type.

    The brief derives the ETag from request parameters alone, so a write can leave a
    cached page stale. ETAG_INCLUDE_FILE_MTIME folds in the file's modification time
    to close that gap. st_mtime_ns is metadata, not content, so this still satisfies
    "do not read data from the VCF file".
    """
    parts = [
        request.path,
        urlencode(sorted(request.query_params.items())),
        media_type or "",
    ]

    if getattr(settings, "ETAG_INCLUDE_FILE_MTIME", False):
        parts.append(str(os.stat(settings.VCF_PATH).st_mtime_ns))

    digest = hashlib.sha256("|".join(parts).encode()).hexdigest()
    return f'"{digest}"'
