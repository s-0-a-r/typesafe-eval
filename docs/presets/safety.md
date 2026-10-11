# Safety Preset (`safety`)

The `safety` preset protects repositories against accidental leaks of credentials, personal contact information (PII), and internal infrastructure addresses in documentation and pull requests.

Unlike generic entropy-based scanners (such as `gitleaks` or `detect-secrets`) that trigger false positives on legitimate public contact details, `typesafe-eval` implements **context-aware PII evaluation** calibrated for enterprise and Japanese software engineering workflows.

---

## What It Checks

### 1. Secret Scanning (Zero Raw Leak)
- **AWS Access Keys**: `AKIA...`, `ASIA...`
- **Slack Tokens**: `xoxb-...`, `xoxp-...`, `xapp-...`
- **GitHub Personal Access Tokens**: `ghp_...`, `gho_...`, `ghu_...`, `ghs_...`, `ghr_...`
- **Generic Quoted Secrets & Tokens**: High-entropy strings, private keys, and passwords embedded in code blocks or configuration payloads.

### 2. Contextual Japanese & International Phone Detection
Generic regex tools often flag all 10-to-11 digit numbers, blocking legitimate customer support numbers in technical manuals. `typesafe-eval` differentiates contact types:

- **Flagged as Personal PII**:
  - Japanese personal mobile numbers (`090-xxxx-xxxx`, `080-xxxx-xxxx`, `070-xxxx-xxxx`).
  - Personal E.164 international numbers without organization keywords.
- **Permitted as Support / Corporate Lines**:
  - Toll-free customer inquiry numbers (`0120-xxx-xxx`, `0800-xxx-xxxx`, `1-800-xxx-xxxx`).
  - Navidial lines (`0570-xxx-xxx`).
  - Corporate landlines (`03-xxxx-xxxx`, `06-xxxx-xxxx`) when accompanied by organizational switchboard context (`代表`, `窓口`, `本社`, `お問い合わせ`).

### 3. Contextual Email & Role Address Classification
- **Flagged as Personal PII**:
  - Free-mail domains (`@gmail.com`, `@yahoo.co.jp`, `@yahoo.com`, `@hotmail.com`, `@outlook.com`, `@icloud.com`).
  - Dotted personal corporate mailboxes (`yamada.taro@company.co.jp`) when individual contact privacy is required.
- **Permitted as Organizational Role Inboxes**:
  - Japanese enterprise department aliases (`jinji@...`, `keiri@...`, `somu@...`, `soumu@...`, `koho@...`, `eigyo@...`, `kaihatsu@...`).
  - Standard RFC organizational roles (`security@...`, `support@...`, `help@...`, `info@...`, `admin@...`).

### 4. Infrastructure & Network Exposure
- **Private IPv4 Ranges**: RFC 1918 subnets (`10.x.x.x/8`, `172.16.x.x/12`, `192.168.x.x/16`) flagged when exposed in public documentation. Documentation examples from RFC 5737 (`192.0.2.x`, `198.51.100.x`, `203.0.113.x`) are recognized and permitted.

---

## Differentiation: When to Use Alongside GitLeaks

| Feature | `gitleaks` / `detect-secrets` | `typesafe-eval --preset safety` |
| :--- | :--- | :--- |
| **Primary Scope** | Git commit history, code diffs, high-entropy secrets | Markdown docs, PR summaries, technical RFCs |
| **Japanese Mobile (090/080/070)** | Missed or treated as raw numbers | **Strictly blocked as personal PII** |
| **Toll-Free & Support (0120/0570)** | Often flagged or ignored | **Permitted without false alarms** |
| **Corporate Switchboard (`03` + 代表)** | Often flagged as potential phone leak | **Permitted via contextual keyword analysis** |
| **Japanese Department Inboxes (`jinji@`)** | Often flagged as email leak | **Permitted as shared organizational roles** |
| **Free-Mail vs Role Distinction** | No distinction | **Deterministic separation (`personal` vs `role`)** |
| **Offline Performance** | Instant (local) | **Instant (local with `--offline`)** |

---

## Client-Side Redaction & Sanitization Flow

Before any text is evaluated or sent to the evaluation provider:
1. **Secret & PII Detection and Masking**: Discovered secrets are masked with placeholders (e.g. `[REDACTED_AWS_KEY]`, `[SECRET_1]`), and emails/phones/IPs are converted to placeholder tokens (e.g. `[EMAIL_1]`, `[PHONE_1]`). This ensures that even secrets hidden within HTML comments are detected as violations.
2. **HTML Prose Comment Stripping**: Comments like `<!-- internal note -->` in regular prose are stripped from the evaluation payload, while HTML comments inside fenced code blocks (` ``` <!-- example --> ``` `) are preserved.
3. **Contextual Evaluation**: Providers evaluate the semantic role of masked placeholders without ever receiving the raw sensitive value.

---

## Offline Pre-Commit Usage

Run safety checks completely offline without network access or API credentials:

```bash
# Evaluate git staged markdown files prior to commit
typesafe-eval --staged --preset safety --offline
```

If any unredacted credential, personal mobile number, or free-mail personal address is detected, the CLI exits with code `1`, preventing the commit from landing.
