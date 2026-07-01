"""Attachment upload processing — validation and compression.

Images are compressed with Pillow: resized to max 1920 px, EXIF-stripped,
recompressed to JPEG (quality 75) or kept as PNG/WebP/GIF where appropriate.

PDFs and office documents are stored as-is — meaningful PDF compression
requires a system-level tool (pikepdf/libqpdf) and is out of scope here.
"""

import io

from django.core.exceptions import ValidationError

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB per file
MAX_ATTACHMENTS_PER_TICKET = 5
IMAGE_MAX_DIMENSION = 1920
IMAGE_QUALITY = 75

IMAGE_MIME_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}

ALLOWED_MIME_TYPES = IMAGE_MIME_TYPES | {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/msword",
    "application/vnd.ms-excel",
}

MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/msword": ".doc",
    "application/vnd.ms-excel": ".xls",
}


def process_upload(file_obj, content_type: str) -> tuple[bytes, str]:
    """Validate and compress an uploaded file.

    Returns (processed_bytes, final_content_type).
    Raises ValidationError for oversized or disallowed files.
    """
    raw = file_obj.read()

    if len(raw) > MAX_FILE_SIZE:
        mb = len(raw) / 1024 / 1024
        raise ValidationError(f"File exceeds the 10 MB limit ({mb:.1f} MB uploaded).")

    # Normalise content type — browsers sometimes send subtypes with parameters
    base_type = content_type.split(";")[0].strip().lower()

    if base_type not in ALLOWED_MIME_TYPES:
        raise ValidationError(f"File type '{base_type}' is not permitted.")

    if base_type in IMAGE_MIME_TYPES:
        return _compress_image(raw, base_type)

    return raw, base_type


def _compress_image(raw: bytes, content_type: str) -> tuple[bytes, str]:
    """Resize and recompress an image. Returns (bytes, final_content_type)."""
    from PIL import Image, ImageOps  # deferred — only needed for image uploads

    img = Image.open(io.BytesIO(raw))

    # Fix EXIF rotation metadata and strip all EXIF to reduce file size
    img = ImageOps.exif_transpose(img)

    # Resize if either dimension exceeds the cap
    w, h = img.size
    if max(w, h) > IMAGE_MAX_DIMENSION:
        ratio = IMAGE_MAX_DIMENSION / max(w, h)
        img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

    out = io.BytesIO()

    if content_type == "image/gif":
        img.save(out, format="GIF", optimize=True)
        return out.getvalue(), "image/gif"

    if content_type == "image/webp":
        img.save(out, format="WEBP", quality=IMAGE_QUALITY, method=6)
        return out.getvalue(), "image/webp"

    if content_type == "image/png":
        has_alpha = img.mode in ("RGBA", "LA") or (
            img.mode == "P" and "transparency" in img.info
        )
        if has_alpha:
            img.save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
        # PNG without transparency — convert to JPEG unless PNG is already smaller
        png_buf = io.BytesIO()
        img.save(png_buf, format="PNG", optimize=True)
        jpg_buf = io.BytesIO()
        img.convert("RGB").save(jpg_buf, format="JPEG", quality=IMAGE_QUALITY, optimize=True)
        if len(png_buf.getvalue()) <= len(jpg_buf.getvalue()):
            return png_buf.getvalue(), "image/png"
        return jpg_buf.getvalue(), "image/jpeg"

    # JPEG (and any unhandled image type)
    img = img.convert("RGB")
    img.save(out, format="JPEG", quality=IMAGE_QUALITY, optimize=True)
    return out.getvalue(), "image/jpeg"
