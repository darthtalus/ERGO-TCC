from pathlib import Path

from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


MAX_ATTACHMENT_SIZE = 10 * 1024 * 1024
ALLOWED_ATTACHMENT_EXTENSIONS = {
    '.pdf', '.png', '.jpg', '.jpeg', '.txt', '.csv',
    '.doc', '.docx', '.xls', '.xlsx',
}
ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    'application/pdf',
    'image/png',
    'image/jpeg',
    'text/plain',
    'text/csv',
    'application/msword',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    'application/octet-stream',  # Some browsers use this for Office files.
}


def validate_attachment_size(uploaded_file):
    if uploaded_file and uploaded_file.size > MAX_ATTACHMENT_SIZE:
        raise ValidationError(_('The attachment must be 10 MB or smaller.'))


def validate_attachment_extension(uploaded_file):
    suffix = Path(uploaded_file.name).suffix.lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise ValidationError(
            _('Unsupported attachment type. Use PDF, image, text, CSV, Word, or Excel files.')
        )
