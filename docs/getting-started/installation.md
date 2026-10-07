# Installation

`typesafe-eval` requires **Python 3.10+**.

---

## 1. Installing via pip

Install the standalone package from PyPI:

```bash
pip install typesafe-eval
```

With optional documentation dependencies:

```bash
pip install "typesafe-eval[docs]"
```

Or for local development:

```bash
pip install "typesafe-eval[dev]"
```

---

## 2. Installing via pipx (Recommended for CLI usage)

To install `typesafe-eval` in an isolated virtual environment accessible globally across your system:

```bash
pipx install typesafe-eval
```

---

## 3. Verify Installation

Check that the CLI executable is available in your PATH:

```bash
typesafe-eval --version
```

Expected output:
```text
typesafe-eval, version 1.0.0
```

> [!NOTE]
> `jev-eval` is also provided as a convenient alias for `typesafe-eval`.

---

## 4. API Key Configuration

`typesafe-eval` supports both TypeSafe System One and OpenAI Decisions API. Set the appropriate API key in your shell environment:

```bash
# For TypeSafe System One (Jev)
export TYPESAFE_API_KEY="your-typesafe-key"

# For OpenAI Decisions API (gpt-6-luna)
export OPENAI_API_KEY="sk-..."
```

You can also pass keys explicitly via the `--api-key` CLI option or programmatically to `evaluate(api_key=...)`.

> [!TIP]
> In CI/CD pipelines, store these values as encrypted repository secrets (e.g., `secrets.TYPESAFE_API_KEY` or `secrets.OPENAI_API_KEY`).
> In local development, you can test without an API key using `--offline` or `--dry-run`.
