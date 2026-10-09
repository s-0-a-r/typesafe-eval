# Claude Code & IDE Hooks

Integrate `typesafe-eval` into your AI development workflows, including Claude Code, Cursor, and IDE hooks.

---

## 1. Claude Code Hook (`hooks/claude_safety_hook.py`)

`typesafe-eval` includes an automated safety hook for Anthropic's Claude Code CLI.

### Scaffolding
```bash
typesafe-eval init --claude-code
```

This configures `.claude/settings.json` with the nested `PostToolUse` command schema:
```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 hooks/claude_safety_hook.py"
          }
        ]
      }
    ]
  }
}
```
and also writes `hooks/hooks.json` for plugin packaging compatibility.

### How It Works
When Claude Code edits or generates markdown documentation:
1. The hook triggers on files modified by Claude Code.
2. It executes `typesafe-eval doc.md --preset safety --offline -f json`.
3. If personal emails, phone numbers, or credentials are detected, the hook returns an error output (exit code 2) directly to Claude Code.
4. Claude Code immediately recognizes the violation and rewrites the content with appropriate mock values or redactions.

---

## 2. Shell & Editor Save Hooks

Add a quick evaluation shortcut or file-save hook in your editor:

```bash
# Example VSCode task or entr file-watcher
find docs -name "*.md" | entr -c typesafe-eval /_ --preset quality --offline
```
