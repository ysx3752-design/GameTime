"""生成演示数据（仅用于截图与人工验收，不进入发布包逻辑）。"""

from __future__ import annotations

import math
import random
import shutil
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from gametime.database import Database  # noqa: E402
from gametime.paths import AppPaths  # noqa: E402

DEMO_ROOT = ROOT / "build" / "demo-data"
GAME_ROOT = ROOT / "build" / "demo-games"


GAMES = [
    {
        "name": "艾尔登法环",
        "exe": "eldenring.exe",
        "accent": "#C9A24B",
        "kind": "ring",
        "note": "交界地漫游中",
        "missing": False,
    },
    {
        "name": "赛博朋克 2077",
        "exe": "Cyberpunk2077.exe",
        "accent": "#E8D735",
        "kind": "neon",
        "note": "夜之城，第二次通关",
        "missing": False,
    },
    {
        "name": "黑神话：悟空",
        "exe": "b1-Win64-Shipping.exe",
        "accent": "#D98B3A",
        "kind": "staff",
        "note": "二周目 · 挑战全成就",
        "missing": False,
    },
    {
        "name": "星露谷物语",
        "exe": "Stardew Valley.exe",
        "accent": "#6FBF73",
        "kind": "field",
        "note": "慢慢玩的农场生活",
        "missing": False,
    },
    {
        "name": "荒野大镖客 2",
        "exe": "RDR2.exe",
        "accent": "#C24A3A",
        "kind": "sun",
        "note": "第三章",
        "missing": False,
    },
    {
        "name": "空洞骑士",
        "exe": "hollow_knight.exe",
        "accent": "#9FC7DE",
        "kind": "mask",
        "note": "等待丝之歌",
        "missing": False,
    },
    {
        "name": "只狼：影逝二度",
        "exe": "sekiro.exe",
        "accent": "#B33A3A",
        "kind": "moon",
        "note": "已卸载，记录仍在",
        "missing": True,
    },
]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in ("msyhbd.ttc", "msyh.ttc", "seguisb.ttf", "arialbd.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_icon(kind: str, accent: str, name: str) -> Image.Image:
    size = 512
    image = Image.new("RGB", (size, size), "#111827")
    draw = ImageDraw.Draw(image)
    base = tuple(int(accent[i : i + 2], 16) for i in (1, 3, 5))
    dark = tuple(max(0, int(channel * 0.22)) for channel in base)
    # 径向渐变背景
    for y in range(size):
        for x in range(0, size, 4):
            t = min(1.0, math.hypot(x - size * 0.35, y - size * 0.3) / (size * 1.2))
            color = tuple(int(base[i] * (1 - t) + dark[i] * t) for i in range(3))
            draw.rectangle([x, y, x + 4, y + 1], fill=color)
    overlay = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    if kind == "ring":
        for radius, width, alpha in ((150, 10, 220), (108, 3, 100), (196, 2, 70)):
            od.ellipse(
                [size // 2 - radius, size // 2 - radius, size // 2 + radius, size // 2 + radius],
                outline=(247, 220, 154, alpha),
                width=width,
            )
        od.line([(256, 92), (256, 420)], fill=(247, 220, 154, 70), width=2)
    elif kind == "neon":
        for offset in range(-160, 520, 36):
            od.line([(offset, 512), (offset + 260, 0)], fill=(80, 245, 255, 110), width=7)
        od.rectangle([40, 330, 472, 430], fill=(8, 15, 25, 180))
        od.text((58, 350), "NIGHT CITY", font=_font(54), fill=(240, 244, 52, 240))
    elif kind == "staff":
        od.line([(118, 430), (378, 82)], fill=(246, 207, 139, 230), width=16)
        od.ellipse([286, 38, 382, 134], outline=(255, 226, 170, 210), width=7)
        for angle in range(0, 360, 45):
            x = 334 + math.cos(math.radians(angle)) * 72
            y = 86 + math.sin(math.radians(angle)) * 72
            od.ellipse([x - 5, y - 5, x + 5, y + 5], fill=(255, 206, 120, 220))
    elif kind == "field":
        od.ellipse([340, 45, 440, 145], fill=(255, 217, 100, 230))
        for row in range(6):
            y = 300 + row * 26
            od.arc([-100, y - 80, 300, y + 20], 180, 330, fill=(35, 100, 50, 220), width=6)
            od.arc([180, y - 80, 560, y + 20], 180, 330, fill=(35, 100, 50, 180), width=6)
        od.polygon([(0, 410), (180, 280), (350, 420), (512, 320), (512, 512), (0, 512)], fill=(45, 113, 63, 200))
    elif kind == "sun":
        od.ellipse([318, 86, 430, 198], fill=(240, 150, 70, 220))
        od.polygon([(0, 430), (140, 300), (260, 390), (360, 290), (512, 390), (512, 512), (0, 512)], fill=(47, 30, 26, 240))
        od.rectangle([0, 430, 512, 512], fill=(37, 23, 21, 240))
    elif kind == "mask":
        od.ellipse([112, 92, 400, 420], fill=(232, 242, 248, 235))
        od.polygon([(152, 210), (218, 120), (240, 244)], fill=(18, 26, 36, 255))
        od.polygon([(360, 210), (294, 120), (272, 244)], fill=(18, 26, 36, 255))
        od.polygon([(202, 314), (256, 344), (310, 314), (256, 380)], fill=(18, 26, 36, 220))
    elif kind == "moon":
        od.ellipse([110, 80, 402, 372], fill=(244, 229, 205, 235))
        od.ellipse([190, 140, 440, 390], fill=(30, 20, 28, 255))
        od.line([(60, 430), (450, 380)], fill=(239, 210, 170, 120), width=4)
    image = Image.alpha_composite(image.convert("RGBA"), overlay)
    # 细微暗角
    vignette = Image.new("L", (size, size), 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse([-120, -120, size + 120, size + 120], fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(80))
    dark_layer = Image.new("RGBA", (size, size), (0, 0, 0, 110))
    image = Image.composite(image, dark_layer, vignette)
    # 游戏名版式
    draw = ImageDraw.Draw(image)
    draw.rectangle([0, 380, 512, 512], fill=(8, 11, 18, 145))
    label = name if len(name) <= 6 else name[:6]
    draw.text((34, 404), label, font=_font(38), fill=(255, 255, 255, 240))
    return image.convert("RGB")


def _local_ts(day: date, hour: int, minute: int) -> int:
    return int(datetime.combine(day, dtime(hour, minute)).astimezone().timestamp())


def seed() -> None:
    for target in (DEMO_ROOT, GAME_ROOT):
        if target.exists():
            resolved = target.resolve()
            if ROOT not in resolved.parents:
                raise RuntimeError(f"拒绝删除项目外目录：{resolved}")
            shutil.rmtree(target)
    paths = AppPaths(DEMO_ROOT).ensure()
    db = Database(paths.database)
    rng = random.Random(20261020)
    now = datetime.now().astimezone()
    today = now.date()
    inserted: list[tuple[int, dict]] = []
    for index, spec in enumerate(GAMES):
        game_dir = GAME_ROOT / f"game{index + 1}"
        game_dir.mkdir(parents=True, exist_ok=True)
        exe_path = game_dir / spec["exe"]
        if not spec["missing"]:
            exe_path.write_bytes(b"MZ" + b"\x00" * 4096)
        icon_name = f"demo_{index + 1}.png"
        icon = make_icon(spec["kind"], spec["accent"], spec["name"])
        icon.save(paths.icons / icon_name, "PNG")
        game_id = db.add_game(
            name=spec["name"],
            exe_path=str(exe_path),
            exe_name=spec["exe"],
            icon_file=icon_name,
            accent=spec["accent"],
            notes=spec["note"],
            now=int(now.timestamp()) - 86400 * 30,
        )
        inserted.append((game_id, spec))

    # 近 14 天合理的游玩记录
    plans = {
        "艾尔登法环": [95, 142, 68, 120, 155, 80, 135],
        "赛博朋克 2077": [45, 88, 62, 75, 110, 52, 96],
        "黑神话：悟空": [122, 74, 156, 90, 133, 170, 88],
        "星露谷物语": [38, 54, 42, 66, 35, 58, 48],
        "荒野大镖客 2": [70, 96, 44, 110, 85, 64, 92],
        "空洞骑士": [28, 45, 37, 62, 51, 43, 35],
        "只狼：影逝二度": [55, 72, 0, 0, 0, 0, 0],
    }
    for game_id, spec in inserted:
        durations = plans[spec["name"]]
        session_index = 0
        for days_ago in range(13, -1, -1):
            if spec["missing"]:
                if days_ago not in (10, 12):
                    continue
                count = 1
            else:
                if rng.random() < 0.32:
                    continue
                if days_ago == 0:
                    count = 2 if spec["name"] in ("艾尔登法环", "赛博朋克 2077") else 1
                else:
                    count = 1 if rng.random() < 0.65 else 2
            day = today - timedelta(days=days_ago)
            for part in range(count):
                base = durations[session_index % len(durations)]
                session_index += 1
                duration = max(8, int(base * rng.uniform(0.55, 1.05))) * 60
                hour = 13 + part * 4 + rng.randint(0, 2)
                minute = rng.choice((5, 12, 24, 33, 41, 50))
                start = _local_ts(day, min(22, hour), minute)
                if days_ago == 0:
                    # 保证今日总时长在 2 小时左右
                    duration = (70 if spec["name"] == "艾尔登法环" else 38) * 60
                    start = int(now.timestamp()) - duration - 1800 - part * 7200
                session_id = db.start_session(game_id, "auto", start)
                db.finish_session(session_id, duration_seconds=duration, ended_at=start + duration)
                time.sleep(0.001)
    total = db.total_seconds()
    print(f"Demo data at {DEMO_ROOT}; games={len(inserted)}, total={total // 3600}h {(total % 3600) // 60}m")
    db.close()


if __name__ == "__main__":
    seed()
