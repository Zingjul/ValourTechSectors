from pathlib import PurePosixPath
from zipfile import BadZipFile, ZipFile

from django.core.exceptions import ValidationError


def validate_material_content(uploaded_file):
    """Reject renamed non-documents. This is a format check, not a malware scanner."""
    # Previously saved files have already been checked; avoid fetching entire
    # private objects from S3 every time staff edit their metadata.
    if getattr(uploaded_file, "_committed", False):
        return
    extension = PurePosixPath(uploaded_file.name).suffix.lower()
    position = uploaded_file.tell()
    try:
        uploaded_file.seek(0)
        signature = uploaded_file.read(8)
        if extension == ".pdf":
            valid = signature.startswith(b"%PDF-")
        elif extension == ".doc":
            valid = signature == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
        elif extension == ".docx":
            uploaded_file.seek(0)
            with ZipFile(uploaded_file) as archive:
                names = set(archive.namelist())
                valid = {"[Content_Types].xml", "word/document.xml"}.issubset(names)
                valid = valid and not any(name.lower().endswith("vbaproject.bin") for name in names)
        else:
            return  # FileExtensionValidator supplies the extension-specific error.
    except (BadZipFile, OSError, ValueError):
        valid = False
    finally:
        uploaded_file.seek(position)
    if not valid:
        raise ValidationError("The file contents do not match an allowed PDF, DOC, or non-macro DOCX document.")
