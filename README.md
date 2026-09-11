# dot-content

Public, shared content source for [MindReset Dot](https://dot.mindreset.tech) ink-screen push scripts.

## Contents

- `words.jsonl` — English vocabulary list for 玉儿 (Andy). One JSON object per line: `{"s": stage, "u": unit, "w": word}`.
- `cron_push_word.py` — Pushes a random word from `words.jsonl` to a Dot device's IMAGE_API block.
- `dot_random_char.py` — Pushes a random Chinese character from the embedded category library to a Dot device's IMAGE_API block.

## Why this repo is public

Single source of truth for word list and push scripts across two hosts:
- **lxf-host (本机)** — pushes to fridge Dot (`B43A455B9660`)
- **yongfu (Oracle cloud)** — pushes to bathroom Dot (`48F6EE576924`)

Updating `words.jsonl` here updates both hosts on their next cron tick.

## What is NOT in this repo

- **DEVICE_IDs / TASK_KEYs** — these are passed as CLI flags per host (see `Multi-host deployment` below). Do not commit them.
- **`DOT_API_KEY`** — lives in each host's `~/.openclaw/.env`, never in code.
- **Font files** — Caveat-Bold.ttf (English, ~50KB) and wqy-zenhei.ttc (Chinese, system font on Ubuntu) are not tracked here. The scripts reference them by absolute path; install or copy separately on each host.
- **State files** (`*.state.json`) — anti-repeat history, per-host.

## Multi-host deployment

### lxf-host (本机) — fridge Dot `B43A455B9660`

```bash
# Word push: every 30 min, S2U11 (current Andy progression)
0,30 * * * * python3 /home/lxf/apps/dot-content-public/cron_push_word.py \
    --from-url https://raw.githubusercontent.com/HenryLoveMiller/dot-content/main/words.jsonl \
    --state-dir /home/lxf/apps/dot_random_word \
    --stage 2 --unit 11 \
    --device-id B43A455B9660 --task-key 8xZ0upAS-gDv \
    >> /home/lxf/apps/dot_random_word/cron.log 2>&1

# Char push: every 2h to the 4th block
0 */2 * * * python3 /home/lxf/apps/dot-content-public/dot_random_char.py \
    --device-id B43A455B9660 --task-key FSb_DDFRcI38 \
    >> /home/lxf/apps/dot_random_char/cron.log 2>&1
```

### yongfu — bathroom Dot `48F6EE576924`

```bash
# Word push only (bathroom has 1 IMAGE_API block, no char block)
15,45 * * * * python3 /home/lxf/ubuntu/apps/dot-content-public/cron_push_word.py \
    --from-url https://raw.githubusercontent.com/HenryLoveMiller/dot-content/main/words.jsonl \
    --state-dir /home/ubuntu/apps/dot_random_word \
    --stage 2 --unit 11 \
    --device-id 48F6EE576924 --task-key GfWF18gqDkEt \
    >> /home/ubuntu/apps/dot_random_word/cron.log 2>&1
```

## Why cron schedules are offset

| Host | Minute pattern | Trigger time (UTC+8) |
|---|---|---|
| lxf-host | `0,30` | :00, :30 |
| yongfu | `15,45` | :15, :45 |

15-minute offset between hosts keeps Dot API request bursts spread out and avoids accidental collision if both hosts ever push to the same device (they don't today, but defense in depth).

## One-time setup on a new host

```bash
# 1. Clone this repo (or scp the directory)
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/HenryLoveMiller/dot-content.git dot-content-public

# 2. Install Python deps (Pillow for image rendering)
pip install --user Pillow

# 3. Set up API key (do NOT commit this)
mkdir -p ~/.openclaw
echo 'DOT_API_KEY=<your_key_here>' > ~/.openclaw/.env
chmod 600 ~/.openclaw/.env

# 4. Install Caveat-Bold.ttf (English) — copy from any host that has it
mkdir -p ~/.fonts
cp /path/to/Caveat-Bold.ttf ~/.fonts/
# wqy-zenhei.ttc is already on Ubuntu at /usr/share/fonts/truetype/wqy/

# 5. Discover the IMAGE_API block's taskKey for the device
curl -sS "https://dot.mindreset.tech/api/authV2/open/device/<DEVICE_ID>/loop/list" \
    -H "Authorization: Bearer $(grep '^DOT_API_KEY' ~/.openclaw/.env | cut -d= -f2-)" \
    | python3 -c "import sys, json; [print(b['key'], b['type']) for b in json.load(sys.stdin) if b['type']=='IMAGE_API']"

# 6. Add the cron line (see Multi-host deployment above)
crontab -e
```

## Updating the word list

Edit `words.jsonl`, commit, push. Both hosts pick it up on the next cron tick (no restart needed). The state files (`*.state.json`) on each host are independent — adding new words does not reset anti-repeat history.

## Why the old per-host scripts were retired

Before this repo, each host had its own copy of `cron_push_word.py` with the DEVICE_ID and TASK_KEY hardcoded. Adding a new host required:
1. scp the script
2. Edit the hardcoded DEVICE_ID
3. Edit the hardcoded TASK_KEY
4. Edit the hardcoded FONT_PATH
5. Edit the hardcoded words.jsonl path

Now all of those are flags. New host = clone + 1 cron line.