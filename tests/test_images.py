"""Tests for markdown embedded image discovery, resolution, validation, and encoding."""

import base64
from pathlib import Path

from typesafe_eval.images import (
    SUPPORTED_EXTENSIONS,
    extract_and_resolve_images,
    strip_markdown_code_blocks,
)


def _create_sample_png(
    path: Path, content: bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDRtest"
) -> Path:
    path.write_bytes(content)
    return path


def test_strip_markdown_code_blocks():
    text = (
        "# Document\n"
        "Here is a diagram: ![diag](images/diag.png)\n"
        "```python\n"
        "# code example\n"
        "img_tag = '![code](images/code.png)'\n"
        "```\n"
        "Inline `![inline](images/inline.png)` should also be stripped.\n"
        'And another real one: <img src="images/real.jpg" alt="real">\n'
    )
    clean = strip_markdown_code_blocks(text)
    assert "images/diag.png" in clean
    assert "images/real.jpg" in clean
    assert "images/code.png" not in clean
    assert "images/inline.png" not in clean


def test_extract_and_resolve_markdown_and_html_images(tmp_path):
    img_dir = tmp_path / "diagrams"
    img_dir.mkdir()
    png_file = _create_sample_png(img_dir / "arch.png")
    jpg_file = _create_sample_png(img_dir / "flow.jpg", b"\xff\xd8\xff\xe0\x00\x10JFIF\x00")

    doc_content = (
        "# Architecture RFC\n\n"
        "System overview diagram:\n"
        "![Architecture Diagram](./diagrams/arch.png)\n\n"
        "Data flow:\n"
        '<img src="./diagrams/flow.jpg" alt="Data Flow Sequence">\n'
    )
    doc_path = tmp_path / "rfc.md"
    doc_path.write_text(doc_content, encoding="utf-8")

    images, warnings = extract_and_resolve_images(doc_content, base_path=doc_path)

    assert len(warnings) == 0
    assert len(images) == 2

    # Verify PNG extraction
    img1 = images[0]
    assert img1.source == "./diagrams/arch.png"
    assert img1.path == png_file.resolve()
    assert img1.alt_text == "Architecture Diagram"
    assert img1.mime_type == "image/png"
    assert img1.data_url.startswith("data:image/png;base64,")
    # Verify b64 decode matches raw bytes
    raw_b64 = img1.data_url.split(",")[1]
    assert base64.b64decode(raw_b64) == png_file.read_bytes()

    # Verify JPG extraction
    img2 = images[1]
    assert img2.source == "./diagrams/flow.jpg"
    assert img2.path == jpg_file.resolve()
    assert img2.alt_text == "Data Flow Sequence"
    assert img2.mime_type == "image/jpeg"
    assert img2.data_url.startswith("data:image/jpeg;base64,")


def test_supported_extensions_mapping():
    assert ".png" in SUPPORTED_EXTENSIONS
    assert ".jpg" in SUPPORTED_EXTENSIONS
    assert ".jpeg" in SUPPORTED_EXTENSIONS
    assert ".webp" in SUPPORTED_EXTENSIONS
    assert ".gif" in SUPPORTED_EXTENSIONS
    assert SUPPORTED_EXTENSIONS[".png"] == "image/png"
    assert SUPPORTED_EXTENSIONS[".jpg"] == "image/jpeg"
    assert SUPPORTED_EXTENSIONS[".webp"] == "image/webp"
    assert SUPPORTED_EXTENSIONS[".gif"] == "image/gif"


def test_missing_image_file_skipped_with_warning(tmp_path):
    doc_content = "# Doc\n![Missing](./missing.png)\n"
    images, warnings = extract_and_resolve_images(doc_content, base_path=tmp_path)
    assert len(images) == 0
    assert len(warnings) == 1
    assert "Image file not found: ./missing.png" in warnings[0]


def test_external_http_url_skipped_with_warning(tmp_path):
    doc_content = "# Doc\n![Remote](https://example.com/logo.png)\n"
    images, warnings = extract_and_resolve_images(doc_content, base_path=tmp_path)
    assert len(images) == 0
    assert len(warnings) == 1
    assert "Skipping external image URL: https://example.com/logo.png" in warnings[0]


def test_unsupported_format_skipped_with_warning(tmp_path):
    svg_file = tmp_path / "vector.svg"
    svg_file.write_text("<svg></svg>", encoding="utf-8")

    doc_content = f"# Doc\n![Vector]({svg_file.name})\n"
    images, warnings = extract_and_resolve_images(doc_content, base_path=tmp_path)
    assert len(images) == 0
    assert len(warnings) == 1
    assert "Unsupported image format '.svg'" in warnings[0]


def test_oversized_image_skipped_with_warning(tmp_path):
    big_file = tmp_path / "huge.png"
    # Write 100 bytes but specify a 50 byte max budget for test
    big_file.write_bytes(b"A" * 100)

    doc_content = "# Doc\n![Huge](huge.png)\n"
    images, warnings = extract_and_resolve_images(
        doc_content, base_path=tmp_path, max_size_bytes=50
    )
    assert len(images) == 0
    assert len(warnings) == 1
    assert "Image exceeds" in warnings[0]


def test_image_count_budget_truncation(tmp_path):
    # Create 4 images
    for i in range(4):
        _create_sample_png(tmp_path / f"img_{i}.png")

    doc_content = "\n".join(f"![img{i}](img_{i}.png)" for i in range(4))
    images, warnings = extract_and_resolve_images(doc_content, base_path=tmp_path, max_images=2)

    assert len(images) == 2
    assert images[0].source == "img_0.png"
    assert images[1].source == "img_1.png"
    assert len(warnings) == 1
    assert "exceeding budget of 2. Truncating to first 2 images" in warnings[0]


def test_inline_data_url_support(tmp_path):
    b64_data = base64.b64encode(b"\x89PNGfake").decode("ascii")
    data_url = f"data:image/png;base64,{b64_data}"
    doc_content = f"# Doc\n![Inline]({data_url})\n"

    images, warnings = extract_and_resolve_images(doc_content, base_path=tmp_path)
    assert len(images) == 1
    assert images[0].data_url == data_url
    assert images[0].mime_type == "image/png"
    assert len(warnings) == 0
