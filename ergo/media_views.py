from django.conf import settings
from django.http import Http404
from django.views.static import serve


PROTECTED_MEDIA_PREFIXES = ('task_attachments/',)


def public_media_serve(request, path):
    """Development-only media server that never exposes protected attachments."""
    normalized = path.replace('\\', '/').lstrip('/')
    if normalized.startswith(PROTECTED_MEDIA_PREFIXES):
        raise Http404
    return serve(request, normalized, document_root=settings.MEDIA_ROOT)
