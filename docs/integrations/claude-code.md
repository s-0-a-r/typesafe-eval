# Claude Code & IDE Hooks

Integrate `typesafe-eval` into your AI development workflows, including Claude Code, Cursor, and IDE hooks.

---

## 1. Claude Code Hook (`hooks/claude_safety_hook.py`)

`typesafe-eval` includes an automated safety hook for Anthropic's Claude Code CLI.

### Scaffolding
```bash
typesafe-eval init --claude-code
```

This creates `.claude/hooks/post-tool-run.py` (or registers the hook in `hooks/hooks.json`).

### How It Works
When Claude Code edits or generates markdown documentation:
1. The hook triggers on files modified by Claude Code.
2. It executes `typesafe-eval doc.md --preset safety --offline -f json`.
3. If personal emails or credentials are detected, the hook returns an error output directly to Claude Code.
4. Claude Code immediately recognizes the violation and rewrites the content with appropriate mock values or redactions.

---

## 2. Shell & Editor Save Hooks

Add a quick evaluation shortcut or file-save hook in your editor:

```bash
# Example VSCode task or entr file-watcher
find docs -name "*.md" | entr -c typesafe-eval /_ --preset quality --offline
```
