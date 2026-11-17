from pathlib import Path

from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.deconstruct import deconstructible


@deconstructible
class PrivateAttachmentStorage(FileSystemStorage):
    """Filesystem storage outside MEDIA_ROOT.

    Files saved here are only exposed through an authorization-checked view.
    """

    def __init__(self, location=None, base_url=None):
        private_root = location or getattr(
            settings,
            'PRIVATE_MEDIA_ROOT',
            Path(settings.BASE_DIR) / 'private_media',
        )
        super().__init__(location=str(private_root), base_url=None)


private_attachment_storage = PrivateAttachmentStorage()
