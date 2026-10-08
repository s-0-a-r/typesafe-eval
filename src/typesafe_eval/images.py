"""Markdown embedded image discovery, validation, and base64 Data URL resolution."""

from __future__ import annotations

import base64
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Supported image MIME types per OpenAI Decisions API / Vision specifications
SUPPORTED_EXTENSIONS: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
    ".gif": "image/gif",
}

DEFAULT_MAX_IMAGES_PER_DOC: int = 5
MAX_POSSIBLE_IMAGES: int = 128
DEFAULT_MAX_IMAGE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10 MB

IMAGE_PATTERN = re.compile(
    r'(?:!\[(?P<md_alt>.*?)\]\(\s*(?P<md_src>[^\s\)]+)(?:\s+["\'].*?["\'])?\s*\)|'
    r'<img\s+[^>]*src=["\'](?P<html_src>[^"\']+)["\'][^>]*>)',
    flags=re.IGNORECASE,
)


@dataclass
class ExtractedImage:
    """Represents a validated and encoded document-embedded image."""

    source: str
    path: Path | None
    data_url: str
    alt_text: str = ""
    mime_type: str = ""
    byte_size: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source,
            "path": str(self.path) if self.path else None,
            "data_url": self.data_url,
            "alt_text": self.alt_text,
            "mime_type": self.mime_type,
            "byte_size": self.byte_size,
        }


def strip_markdown_code_blocks(text: str) -> str:
    """Removes fenced code blocks and inline code spans to prevent extracting code examples as images."""
    # Remove fenced code blocks (``` ... ``` or ~~~ ... ~~~)
    clean = re.sub(r"(```|~~~).*?\1", "", text, flags=re.DOTALL)
    # Remove inline code spans (`...`)
    clean = re.sub(r"`[^`\n]+`", "", clean)
    return clean


def extract_and_resolve_images(
    content: str,
    base_path: Path | str | None = None,
    max_images: int = DEFAULT_MAX_IMAGES_PER_DOC,
    max_size_bytes: int = DEFAULT_MAX_IMAGE_SIZE_BYTES,
) -> tuple[list[ExtractedImage], list[str]]:
    """Discovers and resolves images embedded in markdown and HTML.

    Args:
        content: Raw markdown text content.
        base_path: File path or directory of the document for relative path resolution.
        max_images: Maximum number of images to extract before truncating.
        max_size_bytes: Maximum allowed file size per image.

    Returns:
        (extracted_images, warnings)
    """
    clean_text = strip_markdown_code_blocks(content)
    warnings: list[str] = []
    candidates: list[tuple[str, str]] = []  # (src, alt)

    for match in IMAGE_PATTERN.finditer(clean_text):
        md_src = match.group("md_src")
        if md_src is not None:
            src = md_src.strip("<>")
            alt = match.group("md_alt") or ""
        else:
            src = match.group("html_src") or ""
            full_tag = match.group(0)
            alt_match = re.search(r'alt=["\']([^"\']*)["\']', full_tag, flags=re.IGNORECASE)
            alt = alt_match.group(1) if alt_match else ""

        if src:
            candidates.append((src, alt))

    base_dir: Path
    if base_path:
        p = Path(base_path)
        base_dir = p.parent if p.is_file() or (not p.exists() and p.suffix) else p
    else:
        base_dir = Path.cwd()

    extracted: list[ExtractedImage] = []

    for src, alt in candidates:
        # 1. Skip external HTTP/HTTPS URLs
        if src.startswith(("http://", "https://")):
            warnings.append(f"Skipping external image URL: {src}")
            continue

        # 2. Check for inline data URL
        if src.startswith("data:"):
            if src.startswith("data:image/") and ";base64," in src:
                mime = src.split(";")[0].replace("data:", "")
                data_part = src.split(";base64,")[1]
                approx_size = int(len(data_part) * 0.75)
                if approx_size > max_size_bytes:
                    limit_mb = max_size_bytes / (1024 * 1024)
                    size_mb = approx_size / (1024 * 1024)
                    warnings.append(f"Inline data URL image exceeds {limit_mb:.0f}MB limit ({size_mb:.1f}MB)")
                    continue
                extracted.append(
                    ExtractedImage(
                        source=src[:32] + "...",
                        path=None,
                        data_url=src,
                        alt_text=alt,
                        mime_type=mime,
                        byte_size=approx_size,
                    )
                )
            else:
                warnings.append(f"Skipping invalid or unsupported data URL image: {src[:32]}...")
            continue

        # 3. Resolve local filesystem path
        if os.path.isabs(src):
            resolved_path = Path(src).resolve()
        else:
            resolved_path = (base_dir / src).resolve()

        if not resolved_path.is_file():
            warnings.append(f"Image file not found: {src}")
            continue

        # 4. Validate extension / format
        ext = resolved_path.suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported_list = ", ".join(sorted(SUPPORTED_EXTENSIONS.keys()))
            warnings.append(
                f"Unsupported image format '{ext}': {src}. Supported formats: {supported_list}"
            )
            continue

        # 5. Validate file size
        try:
            stat_info = resolved_path.stat()
            file_size = stat_info.st_size
        except OSError as e:
            warnings.append(f"Failed to inspect image file {src}: {e}")
            continue

        if file_size > max_size_bytes:
            limit_mb = max_size_bytes / (1024 * 1024)
            size_mb = file_size / (1024 * 1024)
            warnings.append(f"Image exceeds {limit_mb:.0f}MB limit ({size_mb:.1f}MB): {src}")
            continue

        # 6. Encode image to base64 Data URL
        try:
            raw_bytes = resolved_path.read_bytes()
            b64_content = base64.b64encode(raw_bytes).decode("ascii")
            mime_type = SUPPORTED_EXTENSIONS[ext]
            data_url = f"data:{mime_type};base64,{b64_content}"
            extracted.append(
                ExtractedImage(
                    source=src,
                    path=resolved_path,
                    data_url=data_url,
                    alt_text=alt,
                    mime_type=mime_type,
                    byte_size=file_size,
                )
            )
        except OSError as e:
            warnings.append(f"Failed to read image file {src}: {e}")
            continue

    # 7. Apply image count budget
    budget = min(max_images, MAX_POSSIBLE_IMAGES)
    if len(extracted) > budget:
        warnings.append(
            f"Document contains {len(extracted)} images, exceeding budget of {budget}. "
            f"Truncating to first {budget} images."
        )
        extracted = extracted[:budget]

    return extracted, warnings
