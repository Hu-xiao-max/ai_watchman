# ai_watchman

Show your **Claude Code** and **Codex** subscription usage at a glance — in the GNOME top bar, tmux, Waybar, or a terminal:

```
Claude 5h 32% / 7d 18% | Codex 5h 10% / 7d 4%
```

## Files

| File | Purpose |
|---|---|
| `ai-usage.py` | The core script — prints the usage line (plain text or Waybar JSON) |
| `ai-usage-gnome.zip` | GNOME Shell extension (`ai-usage@local`) bundling the script; refreshes every 5 minutes |
| `install-ai-usage.sh` | One-shot installer for GNOME |

## How it works

- **Claude** — Claude Code pushes rate-limit data to the script through its
  status line hook (`ai-usage.py claude-hook`). The data is cached in
  `~/.cache/ai-usage/claude.json`, so Claude Code must have run with the hook at
  least once.
- **Codex** — the script asks `codex app-server` for your rate limits, at most
  once every 60 seconds, and caches the result in `~/.cache/ai-usage/codex.json`.
  This needs the `codex` CLI installed and logged in. Set `AI_USAGE_CODEX` to use
  a different binary.
- A trailing `~` means the data is more than 5 minutes old or the last query failed.

## Install on GNOME

```bash
./install-ai-usage.sh
```

The installer:

1. Installs the extension into `~/.local/share/gnome-shell/extensions/ai-usage@local/`.
2. Sets `statusLine` in `~/.claude/settings.json` to the Claude hook. This
   **replaces any existing status line**. A backup named
   `settings.json.before-ai-usage-*` is saved first.
3. Turns the extension on. If GNOME doesn't pick it up, sign out and back in once.

Then restart Claude Code so the Claude numbers appear. Click the top-bar item to
see details and reset times.

> The extension's `metadata.json` declares GNOME Shell **50** only. On another
> version, add yours to `shell-version`.

## Use without GNOME

```bash
./ai-usage.py            # plain text (tmux mode)
./ai-usage.py waybar     # JSON for Waybar
```

Set up the Claude hook yourself in `~/.claude/settings.json`:

```json
"statusLine": { "type": "command", "command": "/usr/bin/python3 /path/to/ai-usage.py claude-hook" }
```

**tmux** (`~/.tmux.conf`):

```tmux
set -g status-right '#(/path/to/ai-usage.py)'
set -g status-interval 60
```

**Waybar**:

```json
"custom/ai-usage": {
  "exec": "/path/to/ai-usage.py waybar",
  "return-type": "json",
  "interval": 60
}
```

## Requirements

- Python 3.8+ (standard library only)
- Claude Code and/or the Codex CLI
- GNOME Shell 50 for the top-bar extension

## License

MIT, see [LICENSE](LICENSE).
