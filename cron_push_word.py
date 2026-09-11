#!/usr/bin/env python3
"""Random English word push to Dot IMAGE_API block.

Data source: a JSONL word file. Loaded from either a local path or a URL
(GitHub raw, etc.). Use --from-url to pull from a remote source so that
multiple hosts (e.g. lxf-host, yongfu) share the same canonical word list.

Word file format: JSONL, one entry per line:
    {"s":2,"u":1,"w":"apple"}
    {"s":2,"u":2,"w":"teddy bear"}

Filtering:
    --stage N         only pick words from stage N (default: 2)
    --unit  N         only pick words from unit N (default: all units in stage)
    --unit-start N --unit-end M    range of units (inclusive)

Anti-repeat: last N pushed words are stored in
<local-state-file>.state.json (next to local-state-file, or in
--state-dir if set). When --from-url is used, --state-dir is REQUIRED so
the per-host history doesn't get clobbered by other hosts sharing the
same URL.

Usage:
    # Local file
    python3 cron_push_word.py /path/to/words.jsonl --stage 2 --unit 11 \\
        --device-id B43A455B9660 --task-key 8xZ0upAS-gDv

    # Remote (GitHub raw, shared between hosts)
    python3 cron_push_word.py \\
        --from-url https://raw.githubusercontent.com/HenryLoveMiller/dot-content/main/words.jsonl \\
        --state-dir /home/<user>/apps/dot_random_word \\
        --stage 2 --unit 11 \\
        --device-id 48F6EE576924 --task-key GfWF18gqDkEt
"""
import argparse, base64, json, random, sys, urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# === Defaults (override via flags or env) ===
DEFAULT_ENV_FILE = Path("/home/lxf/.openclaw/.env")
DEFAULT_FONT_PATH = "/home/lxf/.fonts/Caveat-Bold.ttf"
W, H = 296, 152
HISTORY_SIZE = 50


def read_api_key(env_file):
    if not env_file.exists():
        print(f"DOT_API_KEY env file missing: {env_file}", file=sys.stderr)
        sys.exit(2)
    for line in env_file.read_text().splitlines():
        if line.startswith("DOT_API_KEY") and "=" in line:
            key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if len(key) >= 20:
                return key
    print("DOT_API_KEY missing or too short", file=sys.stderr)
    sys.exit(2)


def fetch_words(source):
    """Return the raw JSONL text from either a local Path or an http(s) URL."""
    if isinstance(source, Path):
        if not source.exists():
            print(f"ERROR: word file not found: {source}", file=sys.stderr)
            sys.exit(2)
        return source.read_text()
    # URL
    try:
        with urllib.request.urlopen(source, timeout=15) as resp:
            if resp.status != 200:
                print(f"ERROR: HTTP {resp.status} fetching {source}", file=sys.stderr)
                sys.exit(2)
            return resp.read().decode()
    except Exception as e:
        print(f"ERROR fetching {source}: {type(e).__name__}: {e}", file=sys.stderr)
        sys.exit(2)


def load_words(text, stage=None, unit=None, unit_start=None, unit_end=None):
    """Load JSONL text, filter by stage/unit. Returns (all_entries, filtered)."""
    entries = []
    for lineno, raw in enumerate(text.splitlines(), 1):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        try:
            obj = json.loads(s)
        except json.JSONDecodeError as e:
            print(f"[words] WARN line {lineno}: invalid JSON ({e}): {s[:60]}", file=sys.stderr)
            continue
        w = obj.get("w", "").strip()
        if not w:
            print(f"[words] WARN line {lineno}: empty word, skipped", file=sys.stderr)
            continue
        entries.append((int(obj["s"]), int(obj["u"]), w))

    def keep(t):
        s, u, w = t
        if stage is not None and s != stage:
            return False
        if unit is not None and u != unit:
            return False
        if unit_start is not None and u < unit_start:
            return False
        if unit_end is not None and u > unit_end:
            return False
        return True

    filtered = [t for t in entries if keep(t)]
    return entries, filtered


def load_history(state_path):
    if not state_path.exists():
        return []
    try:
        h = json.loads(state_path.read_text())
        return h if isinstance(h, list) else []
    except (json.JSONDecodeError, OSError):
        return []


def save_history(state_path, history):
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(history))
    except OSError as e:
        print(f"[state] WARN: could not save history: {e}", file=sys.stderr)


def render_png(word, font_path, w, h):
    target_w = int(w * 0.85)
    font_size = 130
    while font_size > 24:
        font = ImageFont.truetype(font_path, font_size)
        bbox = font.getbbox(word)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        if text_w <= target_w:
            break
        font_size = int(font_size * (target_w / text_w) * 0.97)

    pad_top, pad_bottom = 4, 8  # descender-safe for g/p/q/y
    canvas_w = text_w + 12
    canvas_h = text_h + pad_top + pad_bottom
    text_img = Image.new("L", (canvas_w, canvas_h), 255)
    td = ImageDraw.Draw(text_img)
    td.text((-bbox[0] + 6, pad_top - bbox[1]), word, fill=0, font=font)

    final = Image.new("L", (w, h), 255)
    x = (w - canvas_w) // 2
    y = (h - canvas_h) // 2
    final.paste(text_img, (x, y))
    return final


def push(device_id, task_key, api_key, png_bytes):
    payload = {
        "deviceId": device_id,
        "image": base64.b64encode(png_bytes).decode(),
        "refreshNow": True,
        "border": 0,
        "ditherType": "NONE",
        "taskKey": task_key,
    }
    body = json.dumps(payload).encode()
    url = f"https://dot.mindreset.tech/api/authV2/open/device/{device_id}/image"
    req = urllib.request.Request(url, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"[push] HTTP {resp.status}: {resp.read().decode()[:200]}")
            return 0
    except urllib.error.HTTPError as e:
        print(f"[push] HTTP {e.code}: {e.read().decode()[:200]}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[push] ERR {type(e).__name__}: {e}", file=sys.stderr)
        return 1


def main():
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("words_file", nargs="?", help="Path to JSONL word file (omit if --from-url)")
    src.add_argument("--from-url", help="Fetch JSONL from this URL (e.g. GitHub raw)")
    ap.add_argument("--stage", type=int, default=2, help="Stage filter (default: 2)")
    ap.add_argument("--unit", type=int, default=None, help="Single unit filter")
    ap.add_argument("--unit-start", type=int, default=None, help="Unit range start (inclusive)")
    ap.add_argument("--unit-end", type=int, default=None, help="Unit range end (inclusive)")
    ap.add_argument("--device-id", required=True, help="Dot device ID (12-char hex)")
    ap.add_argument("--task-key", required=True, help="Block taskKey from /loop/list (IMAGE_API block)")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to .env containing DOT_API_KEY")
    ap.add_argument("--font", default=DEFAULT_FONT_PATH, help="Path to TTF font")
    ap.add_argument("--state-dir", default=None,
                    help="Dir for state.json (REQUIRED with --from-url; otherwise defaults next to local file)")
    args = ap.parse_args()

    api_key = read_api_key(Path(args.env_file))

    source = args.from_url if args.from_url else Path(args.words_file)
    text = fetch_words(source)
    print(f"[src] loaded from {source}")

    all_entries, pool = load_words(
        text, stage=args.stage, unit=args.unit,
        unit_start=args.unit_start, unit_end=args.unit_end,
    )
    if not pool:
        print(f"ERROR: no words match filter (stage={args.stage}, unit={args.unit}, "
              f"range=[{args.unit_start},{args.unit_end}])", file=sys.stderr)
        print(f"  (total in file: {len(all_entries)})", file=sys.stderr)
        sys.exit(2)

    seen = set()
    dups = []
    for _, _, w in pool:
        k = w.lower()
        if k in seen:
            dups.append(w)
        seen.add(k)
    if dups:
        print(f"[words] WARN: {len(dups)} duplicate(s) in pool: "
              f"{dups[:5]}{'...' if len(dups) > 5 else ''}")

    filter_desc = f"stage={args.stage}"
    if args.unit is not None:
        filter_desc += f" unit=U{args.unit}"
    elif args.unit_start is not None or args.unit_end is not None:
        filter_desc += f" unit=U{args.unit_start}-U{args.unit_end}"
    print(f"[words] → {len(pool)} candidates ({len(seen)} unique) [{filter_desc}]")

    # State file: next to local file, or in --state-dir (required for URL mode)
    if args.from_url:
        if not args.state_dir:
            print("ERROR: --state-dir is required when using --from-url "
                  "(so per-host history isn't shared)", file=sys.stderr)
            sys.exit(2)
        state_path = Path(args.state_dir) / "words.jsonl.state.json"
    else:
        wp = Path(args.words_file)
        state_path = wp.with_suffix(wp.suffix + ".state.json")
        if args.state_dir:
            state_path = Path(args.state_dir) / state_path.name

    history = load_history(state_path)

    available = [t for t in pool if t[2] not in history]
    if not available:
        available = pool
        history = []
        print("[pick] history covered full pool — resetting")

    s, u, word = random.choice(available)
    print(f"[pick] picked={word!r} (S{s}U{u}) excluded {len(pool)-len(available)} recent")

    history.append(word)
    history = history[-HISTORY_SIZE:]
    save_history(state_path, history)

    png = render_png(word, args.font, W, H)
    buf_path = Path("/tmp/dot_word.png")
    png.save(buf_path)
    png_bytes = buf_path.read_bytes()

    sys.exit(push(args.device_id, args.task_key, api_key, png_bytes))


if __name__ == "__main__":
    main()