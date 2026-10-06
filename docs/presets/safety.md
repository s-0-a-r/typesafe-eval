# Safety Preset (`safety`)

The `safety` preset protects your repository against accidental leaks of credentials, personal contact information, and internal infrastructure addresses.

---

## What It Checks

### 1. Secret Scanning (Zero Raw Leak)
- **AWS Access Keys**: `AKIA...`, `ASIA...`
- **Slack Tokens**: `xoxb-...`, `xoxp-...`, `xapp-...`
- **GitHub Personal Access Tokens**: `ghp_...`, `gho_...`, `ghu_...`, `ghs_...`, `ghr_...`
- **Generic Quoted Secrets & Tokens**: Bearer tokens, private keys, passwords embedded in configuration blocks.

### 2. PII Exposure
- **Personal Email Addresses**: Distinguishes personal emails (`personal`) from organizational shared contact mailboxes (`role`).
  - Free-mail domains (`gmail.com`, `yahoo.com`, `hotmail.com`, `outlook.com`, `icloud.com`) are deterministically classified as personal contact PII.
  - Role emails (`security@company.com`, `support@example.org`, `help@domain.net`) are permitted.
- **International Phone Numbers**: Identifies phone numbers in E.164 and localized formats.

### 3. Infrastructure & Network Exposure
- **Private IPv4 Ranges**: RFC 1918 subnets (`10.x.x.x/8`, `172.16.x.x/12`, `192.168.x.x/16`) flagged when exposed in public documentation (documentation example blocks from RFC 5737 such as `192.0.2.x` are permitted).

---

## Client-Side Redaction & Sanitization Flow

Before any text is evaluated or sent to the TypeSafe System One API:
1. **Secret & PII Detection and Masking**: Discovered secrets are masked with placeholders (e.g. `[REDACTED_AWS_KEY]`, `[SECRET_1]`), and emails/phones/IPs are converted to placeholder tokens (e.g. `[EMAIL_1]`, `[PHONE_1]`). This ensures that even secrets hidden within HTML comments are detected as violations.
2. **HTML Prose Comment Stripping**: Comments like `<!-- internal note -->` in regular prose are stripped from the evaluation payload, while HTML comments inside fenced code blocks (` ``` <!-- example --> ``` `) are preserved.
3. **Contextual Evaluation**: The API evaluates the semantic role of masked placeholders without ever seeing the raw sensitive string.

---

## Offline Safety Check

Run safety checks completely offline without network access:

```bash
typesafe-eval docs/*.md --preset safety --offline
```

If any rule detects an unredacted credential or personal contact email, the CLI exits immediately with code `1`.
