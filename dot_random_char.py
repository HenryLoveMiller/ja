#!/usr/bin/env python3
"""Random Chinese character push (玉儿识字) to Dot IMAGE_API block.

Character library is embedded as Python constants below (no external
data file needed). The library is intentionally small — pictureable
single characters grouped by category, not a full HSK list.

Usage:
    python3 dot_random_char.py --device-id <YOUR_DEVICE_ID> --task-key <YOUR_CHAR_TASK_KEY>
"""
import argparse, base64, json, os, random, sys, urllib.request, urllib.error
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# === Defaults ===
DEFAULT_ENV_FILE = Path("/home/lxf/.openclaw/.env")
DEFAULT_FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"
W, H = 296, 152

# === Character library ===
CATEGORIES = {
    "numbers": "一二三四五六七八九十百千万上下左右前后东南西北里外中大小多少长短高矮半两几双边",
    "nature":   "天地人日月星光风雨雪云雷电水火山石田土沙木林森草花叶竹芽春夏秋冬莲旗金彩桥禾",
    "humans":   "你我他她它们爸妈哥弟姐妹爷奶叔姨儿女子口耳目手足舌牙头发眉毛心身体群师友",
    "animals":  "马牛羊鸡鸭鹅猫狗猪鸟鱼虫虾蛙蚁蝶蜂兔猴熊狮虎瓜果桃李杏梨苹果菜萝卜棋",
    "daily":    "吃喝玩乐哭笑叫喊跑跳走坐站听看读写画说起床穿衣帽鞋袜洗刷爱恨怕喜欢来去出入进门窗户床桌椅打书包笔刀课早校纸船闪飞学音服活爬洞参加办法许放住挂",
    "common":   "是有在个只头条本支把这那哪谁什么的地得没太很真最和同也又还才就吗呢吧呀了去过会能可以对错好坏新旧老少快慢远近红黄蓝绿白黑青紫色不丽久乌亮今从众伞作候全公关到力医厂反变句台向回国声处娃字家尘尺尾工己巴年开弯当影成找数文方无时明昨晚更朋树歌正步比气江海点片生用男皮着睡空立给美自要见觉词语贝车问院鸦业串为",
}


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
    ap.add_argument("--device-id", default=os.environ.get("DOT_DEVICE_ID"),
                    help="Dot device ID (12-char hex). Falls back to env DOT_DEVICE_ID.")
    ap.add_argument("--task-key", default=os.environ.get("DOT_TASK_KEY"),
                    help="Block taskKey from /loop/list (IMAGE_API block). Falls back to env DOT_TASK_KEY.")
    ap.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Path to .env containing DOT_API_KEY")
    ap.add_argument("--font", default=DEFAULT_FONT_PATH, help="Path to TTF/TTC font")
    args = ap.parse_args()

    api_key = read_api_key(Path(args.env_file))

    all_chars = "".join(CATEGORIES.values())
    char = random.choice(all_chars)
    cat = next((k for k, v in CATEGORIES.items() if char in v), "?")
    print(f"[char] picked={char!r} cat={cat}")

    font_size = 126
    font = ImageFont.truetype(args.font, font_size)
    bbox = font.getbbox(char)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    img = Image.new("L", (W, H), 255)
    draw = ImageDraw.Draw(img)
    x = (W - text_w) // 2 - bbox[0]
    y = (H - text_h) // 2 - bbox[1]
    draw.text((x, y), char, fill=0, font=font)

    buf_path = Path("/tmp/dot_char.png")
    img.save(buf_path)
    png_bytes = buf_path.read_bytes()

    sys.exit(push(args.device_id, args.task_key, api_key, png_bytes))


if __name__ == "__main__":
    main()