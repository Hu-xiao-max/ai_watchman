#!/usr/bin/env bash
set -euo pipefail

bundle_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
uuid=ai-usage@local
extension_dir="${XDG_DATA_HOME:-$HOME/.local/share}/gnome-shell/extensions/$uuid"

if ! cmp -s "$bundle_dir/ai-usage-gnome.zip" "$extension_dir/.ai-usage-bundle.zip"; then
    gnome-extensions install --force "$bundle_dir/ai-usage-gnome.zip"
    cp -- "$bundle_dir/ai-usage-gnome.zip" "$extension_dir/.ai-usage-bundle.zip"
fi

python3 - "$extension_dir/ai-usage.py" <<'PY'
import json
import os
from pathlib import Path
import shlex
import shutil
import sys
import tempfile

config = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
hook = {"type": "command", "command": f"/usr/bin/python3 {shlex.quote(sys.argv[1])} claude-hook"}
config = config.resolve()
config.parent.mkdir(parents=True, exist_ok=True)
settings = json.loads(config.read_text()) if config.exists() else {}
if not isinstance(settings, dict):
    sys.exit(f"Expected a JSON object in {config}")
if settings.get("statusLine") != hook:
    if config.exists():
        with tempfile.NamedTemporaryFile(dir=config.parent, prefix="settings.json.before-ai-usage-", delete=False) as backup:
            shutil.copyfile(config, backup.name)
            print(f"Saved Claude settings backup to {backup.name}")
    settings["statusLine"] = hook
    with tempfile.NamedTemporaryFile(mode="w", dir=config.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            json.dump(settings, stream, indent=2, ensure_ascii=False)
            stream.write("\n")
            stream.close()
            temp.replace(config)
        finally:
            temp.unlink(missing_ok=True)
PY

if gnome-extensions info "$uuid" >/dev/null 2>&1; then
    gnome-extensions enable "$uuid"
    if gnome-extensions list --enabled | grep -Fxq "$uuid"; then
        printf '%s\n' 'AI usage is enabled in GNOME. Start or reopen Claude Code to populate its usage.'
        exit 0
    fi
fi

# The running Shell may discover a newly installed extension only at login.
# Add it to GNOME's enabled list now, preserving the other extensions.
/usr/bin/python3 - "$uuid" <<'GNOME'
from gi.repository import Gio
import sys

uuid = sys.argv[1]
settings = Gio.Settings.new("org.gnome.shell")
enabled = settings.get_strv("enabled-extensions")
disabled = settings.get_strv("disabled-extensions")
if uuid in disabled and not settings.set_strv(
    "disabled-extensions", [entry for entry in disabled if entry != uuid]
):
    sys.exit("Could not update GNOME's disabled extensions.")
if uuid not in enabled and not settings.set_strv("enabled-extensions", [*enabled, uuid]):
    sys.exit("Could not update GNOME's enabled extensions.")
Gio.Settings.sync()
GNOME
if ! gsettings get org.gnome.shell enabled-extensions | grep -Fq "'$uuid'"; then
    printf '%s\n' 'GNOME did not save the enable setting. Sign out and back in, then rerun the installer.' >&2
    exit 1
fi
printf '%s\n' 'AI usage is set to load at your next GNOME login. Sign out and back in once.'
