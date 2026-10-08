# Multimodal Diagram & Image Evaluation

Technical RFCs, system design proposals, and architecture specifications frequently include visual diagrams (`![Architecture](./diagrams/arch.png)`), sequence diagrams, and UI mockups. While textual descriptions articulate high-level responsibilities, visual diagrams often depict network boundaries, database replication tiers, caching topologies, and security zones that prose alone may omit or misstate.

Starting in **v1.2.0**, `typesafe-eval` supports optional, opt-in **multimodal document evaluation** via the OpenAI Decisions API (`POST /v1/decisions` powered by `gpt-6-luna`).

---

## 1. Quick Invocations

Multimodal evaluation is **strictly opt-in** to protect documents against unintended data egress.

```bash
# Evaluate technical specifications including diagrams via OpenAI Decisions API
typesafe-eval docs/rfc/*.md --preset tech-spec --provider openai --include-images

# Use alias --multimodal flag
typesafe-eval docs/rfc/*.md --preset tech-spec --provider openai --multimodal

# Specify maximum images per document (1–128, default 5)
typesafe-eval docs/rfc/*.md --preset tech-spec --provider openai --include-images --max-images-per-doc 8

# Output pure JSON stream for CI or agent workflows
typesafe-eval docs/rfc/*.md --preset tech-spec --provider openai --include-images -f json
```

---

## 2. Project Configuration (`.typesafe-eval.yaml`)

You can enable multimodal evaluation repository-wide or per-directory in your `.typesafe-eval.yaml` or `pyproject.toml`:

```yaml
# .typesafe-eval.yaml
preset: tech-spec
provider: openai
model: gpt-6-luna
include_images: true
max_images_per_doc: 5
```

Or in `pyproject.toml`:

```toml
[tool.typesafe-eval]
preset = "tech-spec"
provider = "openai"
include_images = true
max_images_per_doc = 5
```

---

## 3. How Image Discovery Works

When `--include-images` is active, `typesafe-eval` scans the markdown text before API dispatch:

1. **Syntax Detection**: Discovers both Markdown image links (`![Alt text](./diagrams/arch.png)`) and HTML tags (`<img src="./diagrams/flow.jpg" alt="Sequence flow">`).
2. **Code Block Protection**: Skips image references embedded inside fenced code blocks (```` ```...``` ````) or inline code spans (` `...` `) so that code snippets and documentation examples are not treated as rendered diagrams.
3. **Document-Relative Resolution**: Relative paths are resolved relative to the directory of the markdown document being evaluated.
4. **Supported Image Formats**:
   - `PNG` (`.png`) &rarr; `image/png`
   - `JPEG` (`.jpg`, `.jpeg`) &rarr; `image/jpeg`
   - `WebP` (`.webp`) &rarr; `image/webp`
   - `GIF` (`.gif`) &rarr; `image/gif`
5. **Budgets & Guardrails**:
   - **File Size Limit**: Maximum 10MB per image file. Files exceeding this budget are skipped and recorded in `warnings`.
   - **Count Budget**: Documents with more images than `max_images_per_doc` (default 5, max 128) are truncated to the first $N$ images, with an informational warning recorded.
   - **External URLs**: External `http://` / `https://` URLs are skipped with a warning to ensure reproducibility and prevent unauthenticated remote network calls.
   - **Missing Files**: Missing or unreadable image files are skipped with a warning and do not abort the document evaluation.
6. **Data URL Encoding**: Valid local images are encoded into inline base64 Data URLs (`data:image/png;base64,...`) and forwarded to the model backend.

---

## 4. Provider Backend Support

| Decision Engine | Multimodal Capability | Operational Behavior |
| :--- | :---: | :--- |
| **OpenAI Decisions API** (`gpt-6-luna`) | ✅ Native Multimodal | Encodes document into `[input_text, input_image, ...]` parts in the Decisions API request payload. |
| **TypeSafe System One** (`jev`) | ⚠️ Text-Only | Emits an informational notice to `stderr` that embedded images were skipped; continues text evaluation cleanly. |

---

## 5. Security & Zero Raw Leakage Boundary

> [!WARNING]
> **Image Pixels Are Not OCR-Redacted**
> While `typesafe-eval` aggressively scans and redacts raw secrets, passwords, Slack tokens, AWS keys, and personal PII from **Markdown text prose** before API dispatch, OCR-based redacting of embedded image pixels is not supported.
>
> When `--include-images` is enabled, `typesafe-eval` emits a security advisory to `stderr`:
> ```text
> Security advisory: Multimodal evaluation is enabled. Embedded images are NOT
> automatically redacted for credentials or PII. Ensure diagrams do not contain
> sensitive secrets or private information.
> ```

Following the `typesafe-eval` contract, the security advisory is strictly emitted to `stderr`; `stdout` remains a pure JSON stream suitable for `jq` and automated CI pipelines.

---

## 6. Python API Integration

```python
from typesafe_eval import evaluate_document, evaluate

# Evaluate a local file with images
result = evaluate_document(
    "docs/rfc/system-architecture.md",
    preset="tech-spec",
    include_images=True,
    max_images_per_doc=5,
)

print(f"Images evaluated: {result.images_evaluated}")
print(f"Image paths: {result.image_paths}")
print(f"Warnings: {result.warnings}")
```
