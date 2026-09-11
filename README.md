# dot-content

Public, shared content source for [MindReset Dot](https://dot.mindreset.tech) ink-screen push scripts.

## Contents

- `words.jsonl` — English vocabulary list for 玉儿 (Andy). One JSON object per line: `{"s": stage, "u": unit, "w": word}`.
- `cron_push_word.py` — Pushes a random word from `words.jsonl` to a Dot device's IMAGE_API block.
- `dot_random_char.py` — Pushes a random Chinese character from the embedded category library to a Dot device's IMAGE_API block.

## Why this repo is public

Single source of truth for word list and push scripts across two hosts (lxf-host and yongfu, an Oracle cloud VM). Updating `words.jsonl` here updates both hosts on their next cron tick.

## What is NOT in this repo (and must never be)

- **`DOT_API_KEY`** — bearer token. Lives only in each host's `~/.openclaw/.env`. **Never commit.**
- **Dot `deviceId`** (12-char hex) — identifies your device. Rotating is cheap; treat as semi-sensitive.
- **Dot `taskKey`** (per content block) — combined with `DOT_API_KEY`, lets the holder overwrite that block. **Treat as a secret.** If it leaks, rotate it via the Dot console — old `taskKey` is invalidated the moment a new one is generated.
- **Font files** — Caveat-Bold.ttf (English, ~50KB) and wqy-zenhei.ttc (Chinese, system font on Ubuntu) are not tracked here. Install or copy separately on each host.
- **State files** (`*.state.json`) — anti-repeat history, per-host.

## Multi-host deployment (illustrative, NO real IDs)

Topology:

```
lxf-host (本机) ──────────► fridge Dot
yongfu (Oracle cloud) ────► bathroom Dot
```

Each host stores its own `DOT_DEVICE_ID` / `DOT_TASK_KEY_*` in `~/.openclaw/.env`. The scripts accept these via `--device-id` / `--task-key` CLI flags or via env vars `DOT_DEVICE_ID` / `DOT_TASK_KEY` (latter used when migrating from the previous hardcoded-script setup; see Migration below).

### Cron shape (replace placeholder values with your own)

```bash
# Word push on host A (every 30 min, vocabulary unit S2U11)
0,30 * * * * python3 /home/<user>/apps/dot-content-public/cron_push_word.py \
    --from-url https://raw.githubusercontent.com/HenryLoveMiller/ja/dot-content/words.jsonl \
    --state-dir /home/<user>/apps/dot_random_word \
    --stage 2 --unit 11 \
    --device-id <YOUR_DEVICE_ID> --task-key <YOUR_WORD_TASK_KEY> \
    >> /home/<user>/apps/dot_random_word/cron.log 2>&1

# Char push on host A (every 2h to the Chinese-char block)
0 */2 * * * python3 /home/<user>/apps/dot-content-public/dot_random_char.py \
    --device-id <YOUR_DEVICE_ID> --task-key <YOUR_CHAR_TASK_KEY> \
    >> /home/<user>/apps/dot_random_char/cron.log 2>&1

# Word push on host B (offset 15min from host A, word-only — bathroom has 1 IMAGE_API block)
15,45 * * * * python3 /home/<user>/apps/dot-content-public/cron_push_word.py \
    --from-url https://raw.githubusercontent.com/HenryLoveMiller/ja/dot-content/words.jsonl \
    --state-dir /home/<user>/apps/dot_random_word \
    --stage 2 --unit 11 \
    --device-id <YOUR_OTHER_DEVICE_ID> --task-key <YOUR_OTHER_TASK_KEY> \
    >> /home/<user>/apps/dot_random_word/cron.log 2>&1
```

15-minute offset between hosts keeps Dot API request bursts spread out and avoids accidental collision if both hosts ever push to the same device (defense in depth).

## One-time setup on a new host

```bash
# 1. Clone this repo (or scp the directory)
mkdir -p ~/apps && cd ~/apps
git clone https://github.com/HenryLoveMiller/ja.git dot-content-public
git -C dot-content-public checkout dot-content

# 2. Install Python deps (Pillow for image rendering)
pip install --user Pillow

# 3. Set up API key (do NOT commit this)
mkdir -p ~/.openclaw
printf 'DOT_API_KEY=<your_key_here>\nDOT_DEVICE_ID=<your_device_id>\nDOT_TASK_KEY=<your_task_key>\n' > ~/.openclaw/.env
chmod 600 ~/.openclaw/.env

# 4. Install Caveat-Bold.ttf (English) — copy from any host that has it
mkdir -p ~/.fonts
cp /path/to/Caveat-Bold.ttf ~/.fonts/
# wqy-zenhei.ttc is already on Ubuntu at /usr/share/fonts/truetype/wqy/

# 5. Discover the IMAGE_API block's taskKey for the device
DOT_TOKEN=$(grep '^DOT_API_KEY' ~/.openclaw/.env | cut -d= -f2-)
curl -sS "https://dot.mindreset.tech/api/authV2/open/device/<YOUR_DEVICE_ID>/loop/list" \
    -H "Authorization: Bearer $DOT_TOKEN" \
    | python3 -c "import sys, json; [print(b['key'], b['type']) for b in json.load(sys.stdin) if b['type']=='IMAGE_API']"

# 6. Add the cron line (see Multi-host deployment above), filling in your IDs
crontab -e
```

## Updating the word list

Edit `words.jsonl`, commit, push to `ja` branch `dot-content`. Both hosts pick it up on the next cron tick (no restart needed). The state files (`*.state.json`) on each host are independent — adding new words does not reset anti-repeat history.

## Migration from per-host hardcoded scripts

Before this repo, each host had its own copy of `cron_push_word.py` with the DEVICE_ID and TASK_KEY hardcoded. To migrate with **zero cron change**:

1. Replace the script at the path your cron calls:
   ```bash
   ln -sf /home/<user>/apps/dot-content-public/cron_push_word.py /home/<user>/.hermes/scripts/random_word.py
   ln -sf /home/<user>/apps/dot-content-public/dot_random_char.py /home/<user>/.hermes/scripts/random_hanzi.py
   ```
2. Add `DOT_DEVICE_ID` and `DOT_TASK_KEY` to `~/.openclaw/.env` (the scripts pick them up from env when `--device-id` / `--task-key` flags are absent).
3. Keep crontab entries exactly as they were. The new scripts honor `--from-url` (for word file) when set, otherwise fall back to the local path argument your cron already passes.

This avoids touching any cron schedule — only swap the script and update `.env`.

## If a taskKey ever leaks publicly

1. Open the Dot console, regenerate the block's taskKey.
2. Update `~/.openclaw/.env` on every host with the new `DOT_TASK_KEY_*`.
3. Old taskKey immediately stops working. Push scripts using the old value will fail with HTTP 401/403; that's your signal.
4. No need to update this repo — taskKeys are intentionally not committed.