#!/usr/bin/env python3
"""Show Claude Code and Codex subscription quota in tmux or Waybar."""

import argparse
import asyncio
import fcntl
import json
import os
from pathlib import Path
import sys
import tempfile
import time

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "ai-usage"


def read(name):
    try:
        return json.loads((CACHE / name).read_text())
    except (OSError, ValueError):
        return {}


def save(name, value):
    with tempfile.NamedTemporaryFile(mode="w", dir=CACHE, delete=False) as stream:
        path = Path(stream.name)
        try:
            json.dump(value, stream)
            stream.close()
            path.replace(CACHE / name)
        finally:
            path.unlink(missing_ok=True)


def meter(label, data, used_key, reset_key):
    data = data or {}
    used = data.get(used_key)
    if type(used) not in (int, float) or not 0 <= used <= 100:
        return None
    reset = data.get(reset_key)
    return [label, used, reset if type(reset) in (int, float) else None]


def claude_hook():
    try:
        limits = json.load(sys.stdin).get("rate_limits") or {}
    except (ValueError, AttributeError):
        return
    meters = [meter(label, limits.get(key), "used_percentage", "resets_at")
              for key, label in (("five_hour", "5h"), ("seven_day", "7d"))]
    if limits:
        save("claude.json", {"at": time.time(), "meters": [m for m in meters if m]})
    print(render("Claude", read("claude.json"))[0])


def duration(minutes, fallback):
    if type(minutes) is not int or minutes <= 0:
        return fallback
    if minutes % 1440 == 0:
        return f"{minutes // 1440}d"
    if minutes % 60 == 0:
        return f"{minutes // 60}h"
    return f"{minutes}m"


async def codex_query():
    proc = await asyncio.create_subprocess_exec(
        os.environ.get("AI_USAGE_CODEX", "codex"), "app-server", "--listen", "stdio://",
        stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL, cwd=Path.home(),
    )

    async def send(message):
        proc.stdin.write((json.dumps(message) + "\n").encode())
        await proc.stdin.drain()

    async def receive(request_id):
        while line := await proc.stdout.readline():
            response = json.loads(line)
            if response.get("id") == request_id:
                return response["result"]
        raise EOFError

    async def query():
        await send({"id": 0, "method": "initialize", "params": {
            "clientInfo": {"name": "ai_usage_bar", "version": "1.0.0"},
        }})
        await receive(0)
        await send({"method": "initialized"})
        await send({"id": 1, "method": "account/rateLimits/read"})
        return await receive(1)

    try:
        result = await asyncio.wait_for(query(), timeout=5)
    finally:
        if proc.returncode is None:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
        await proc.communicate()

    buckets = result.get("rateLimitsByLimitId") or {}
    limits = buckets.get("codex") or result.get("rateLimits") or {}
    meters = []
    for key in ("primary", "secondary"):
        window = limits.get(key) or {}
        label = duration(window.get("windowDurationMins"), key)
        entry = meter(label, window, "usedPercent", "resetsAt")
        if entry:
            meters.append(entry)
    return meters


def codex_snapshot():
    with (CACHE / "codex.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return read("codex.json")
        snapshot = read("codex.json")
        now = time.time()
        if now - snapshot.get("attempt", 0) >= 60:
            try:
                snapshot = {"at": time.time(), "meters": asyncio.run(codex_query())}
            except (OSError, ValueError, KeyError, EOFError, TimeoutError):
                snapshot["failed"] = True
            snapshot["attempt"] = now
            save("codex.json", snapshot)
        return snapshot


def render(name, snapshot):
    now = time.time()
    age = max(0, int(now - snapshot.get("at", now)))
    parts = []
    details = []
    for label, used, reset in snapshot.get("meters", []):
        if reset is not None and reset <= now:
            continue
        part = f"{label} {used:g}%"
        parts.append(part)
        details.append(part if reset is None else
                       f"{part} · 重置于 {time.strftime('%m-%d %H:%M', time.localtime(reset))}")
    if parts:
        stale = snapshot.get("failed") or age >= 300
        text = f"{name} {' / '.join(parts)}{' ~' if stale else ''}"
        details.append(f"快照时间距今 {age // 60} 分钟")
    else:
        text = f"{name} —"
        details.append("暂无用量")
    if snapshot.get("failed"):
        details.append("最近一次查询失败")
    return text, f"{name}\n" + "\n".join(details)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", nargs="?", default="tmux",
                        choices=("tmux", "waybar", "claude-hook"))
    mode = parser.parse_args().mode
    CACHE.mkdir(mode=0o700, parents=True, exist_ok=True)
    if mode == "claude-hook":
        claude_hook()
        return
    claude, claude_detail = render("Claude", read("claude.json"))
    codex, codex_detail = render("Codex", codex_snapshot())
    text = f"{claude} | {codex}"
    if mode == "waybar":
        print(json.dumps({"text": text, "tooltip": f"{claude_detail}\n\n{codex_detail}"},
                         ensure_ascii=False))
    else:
        print(text)


if __name__ == "__main__":
    main()
