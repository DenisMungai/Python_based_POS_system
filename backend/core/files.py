"""Safe local file writes and validated asset copying."""

import os
import shutil
import tempfile
import uuid
from pathlib import Path

from backend.core.errors import ValidationError

SAFE_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


def atomic_write(path: Path, content: bytes) -> None:
    """Atomically replace a file using a same-directory temporary file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    except Exception:
        if os.path.exists(temporary_name):
            os.unlink(temporary_name)
        raise


def copy_image(source: Path, destination_dir: Path, max_bytes: int = 5_000_000) -> Path:
    """Copy an image into managed storage with a generated filename."""
    extension = source.suffix.lower()
    if extension not in SAFE_IMAGE_EXTENSIONS:
        raise ValidationError("Unsupported image file type.")
    if not source.is_file() or source.stat().st_size > max_bytes:
        raise ValidationError("Image is missing or exceeds the size limit.")
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / f"{uuid.uuid4().hex}{extension}"
    shutil.copyfile(source, destination)
    return destination
