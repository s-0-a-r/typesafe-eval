# AGENTS.md & Autonomous Agent Guidance

Guidance and operational boundaries for AI coding assistants (Codex, Claude Code, Cursor, Copilot, Google Antigravity CLI, Aider) operating in repositories using `typesafe-eval`.

---

## The 4 Mandatory Guidance Rules

All autonomous coding agents operating in repositories gated by `typesafe-eval` must follow these 4 rules:

### 1. Don't make scores a loop target (Goodhart's Law)
- Cap automated revision loops at **2 rounds maximum**.
- Do not degrade or distort natural technical writing just to chase higher numeric scores.
- Address specific failure items listed in `violations`, then finalize your edit.

### 2. Language Caveat
- TypeSafe System One (Jev) is calibrated for **English** documentation.
- When evaluating non-English text, treat borderline scores or low confidence with caution and inform the user.

### 3. Near-Threshold Results are Soft
- Questions and candidates marked with `near_threshold: true` fall within $\pm 0.10$ of the decision boundary ($0.40 \le p \le 0.60$).
- Report the calibrated probability range to the user as a contextual observation rather than an absolute failure.

### 4. Never Pass API Keys Through the Agent
- The CLI reads `TYPESAFE_API_KEY` or `OPENAI_API_KEY` directly from the process environment.
- Never ask the user to provide an API key in chat, and never hardcode or echo credentials in commands or scripts.

---

## Agent Invocation Recipes

```bash
# Offline safety dry-run before opening a pull request
typesafe-eval docs/*.md --preset safety --offline -f json

# Quality check on staged changes
typesafe-eval --staged --preset quality -f json

# Real CLI Acceptance Verification
python scripts/verify_ac.py
```
