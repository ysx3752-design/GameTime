"""生成说明文档用的封面与架构图。"""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
ICON = ROOT / "gametime" / "resources" / "app_icon.png"

NAVY = (10, 14, 22)
PURPLE = (124, 92, 255)
PURPLE_DARK = (61, 42, 140)
GREEN = (53, 214, 165)
TEXT = (237, 241, 248)
MUTED = (154, 164, 185)
LIGHT_BG = (247, 248, 252)
INK = (28, 33, 48)
SOFT = (104, 113, 134)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"
    return ImageFont.truetype(path, size)


def make_cover() -> Image.Image:
    scale = 2
    W, H = 1240 * scale, 1754 * scale
    image = Image.new("RGBA", (W, H), NAVY + (255,))
    # 纵向渐变
    top = (12, 16, 27)
    bottom = (26, 21, 53)
    for y in range(H):
        t = y / H
        color = tuple(round(top[i] + (bottom[i] - top[i]) * t) for i in range(3))
        ImageDraw.Draw(image).line([(0, y), (W, y)], fill=color + (255,))

    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([int(W * 0.42), int(-H * 0.16), int(W * 1.25), int(H * 0.47)], fill=(124, 92, 255, 64))
    gd.ellipse([int(-W * 0.25), int(H * 0.58), int(W * 0.45), int(H * 1.2)], fill=(53, 214, 165, 22))
    glow = glow.filter(ImageFilter.GaussianBlur(140 * scale))
    image.alpha_composite(glow)

    draw = ImageDraw.Draw(image)
    # 顶部品牌标识
    icon_size = int(W * 0.17)
    icon = Image.open(ICON).convert("RGBA").resize((icon_size, icon_size), Image.Resampling.LANCZOS)
    icon_x = (W - icon_size) // 2
    icon_y = int(H * 0.175)
    # 阴影
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    sd.rounded_rectangle(
        [icon_x + 10 * scale, icon_y + 22 * scale, icon_x + icon_size + 10 * scale, icon_y + icon_size + 22 * scale],
        radius=icon_size // 5,
        fill=(0, 0, 0, 130),
    )
    shadow = shadow.filter(ImageFilter.GaussianBlur(28 * scale))
    image.alpha_composite(shadow)
    image.alpha_composite(icon, (icon_x, icon_y))

    def center_text(y: int, text: str, f: ImageFont.FreeTypeFont, color, spacing=0) -> int:
        bbox = draw.textbbox((0, 0), text, font=f)
        w = bbox[2] - bbox[0]
        draw.text(((W - w) / 2, y), text, font=f, fill=color)
        return y + (bbox[3] - bbox[1]) + spacing

    y = int(H * 0.40)
    y = center_text(y, "游 时", font(int(120 * scale), True), TEXT, 20 * scale)
    y = center_text(y, "G A M E T I M E", font(int(28 * scale)), (185, 168, 255), 42 * scale)
    draw.line([(W * 0.40, y), (W * 0.60, y)], fill=(124, 92, 255, 190), width=2 * scale)
    y += 34 * scale
    y = center_text(y, "桌面游戏时长记录器", font(int(32 * scale)), (215, 220, 235), 18 * scale)
    y = center_text(y, "产品说明文档", font(int(22 * scale)), MUTED, 0)

    # 特性标签
    tags = ["手动添加", "自动计时", "卸载不丢记录", "本地存储"]
    tag_font = font(int(17 * scale))
    tag_padding_x = 22 * scale
    widths = []
    for tag in tags:
        bbox = draw.textbbox((0, 0), tag, font=tag_font)
        widths.append(bbox[2] - bbox[0] + tag_padding_x * 2)
    gap = 12 * scale
    total = sum(widths) + gap * (len(tags) - 1)
    x = (W - total) / 2
    tag_y = int(H * 0.685)
    for tag, width in zip(tags, widths):
        draw.rounded_rectangle(
            [x, tag_y, x + width, tag_y + 42 * scale],
            radius=21 * scale,
            fill=(36, 31, 61, 255),
            outline=(118, 104, 176, 180),
            width=1 * scale,
        )
        tb = draw.textbbox((0, 0), tag, font=tag_font)
        draw.text(
            (x + (width - (tb[2] - tb[0])) / 2, tag_y + (42 * scale - (tb[3] - tb[1])) / 2 - 3 * scale),
            tag,
            font=tag_font,
            fill=(212, 206, 238),
        )
        x += width + gap

    # 底部
    draw.line([(W * 0.12, H * 0.80), (W * 0.88, H * 0.80)], fill=(255, 255, 255, 22), width=1 * scale)
    meta_font = font(int(18 * scale))
    center_text(int(H * 0.83), "版本 1.0.0   ·   Windows 10 / 11 x64   ·   2026", meta_font, (132, 141, 160))
    center_text(int(H * 0.88), "Python 3.14 · PySide6 / Qt 6.12 · SQLite", font(int(16 * scale)), (105, 114, 135))
    return image.resize((1240, 1754), Image.Resampling.LANCZOS)


def _box(draw, rect, title, subtitle, fill, border, title_color=INK, subtitle_color=SOFT):
    x1, y1, x2, y2 = rect
    draw.rounded_rectangle([x1, y1, x2, y2], radius=18, fill=fill, outline=border, width=2)
    title_font = font(26, True)
    subtitle_font = font(18)
    draw.text((x1 + 22, y1 + 16), title, font=title_font, fill=title_color)
    draw.text((x1 + 22, y1 + 52), subtitle, font=subtitle_font, fill=subtitle_color)


def make_architecture() -> Image.Image:
    scale = 2
    W, H = 1240 * scale, 780 * scale
    image = Image.new("RGBA", (W, H), LIGHT_BG + (255,))
    draw = ImageDraw.Draw(image)
    # 背景网格点
    for y in range(40 * scale, H, 36 * scale):
        for x in range(40 * scale, W, 36 * scale):
            draw.ellipse([x, y, x + 2 * scale, y + 2 * scale], fill=(214, 219, 232, 120))

    def S(v):
        return int(v * scale)

    # 层标签
    labels = [
        (S(82), "UI 层 · PySide6", "主窗口、页面、对话框、托盘"),
        (S(310), "服务层", "计时、游戏库、统计、系统集成"),
        (S(555), "持久化 / 系统层", "本地数据与 Windows 集成"),
    ]
    for y, title, sub in labels:
        draw.text((S(48), y), title, font=font(S(22), True), fill=INK)
        draw.text((S(48), y + S(30)), sub, font=font(S(15)), fill=SOFT)

    # UI 层盒子
    _box(draw, (S(330), S(46), S(680), S(150)), "MainWindow", "导航 · 页面切换 · Toast · 生命周期", (238, 235, 255), (185, 173, 245), INK)
    _box(draw, (S(708), S(46), S(1050), S(150)), "Dashboard / Library / Stats / Settings", "四个业务页面", (245, 246, 252), (208, 214, 229))

    # 服务层
    _box(draw, (S(330), S(278), S(574), S(398)), "TrackingEngine", "2s 轮询 · 手动计时 · 10s 心跳", (230, 247, 242), (138, 211, 190))
    _box(draw, (S(596), S(278), S(802), S(398)), "ProcessScanner", "psutil · exe 路径", (230, 247, 242), (138, 211, 190))
    _box(draw, (S(824), S(278), S(1050), S(398)), "GameService", "CRUD · 校验 · 重定位", (232, 240, 255), (151, 183, 235))
    _box(draw, (S(330), S(418), S(574), S(517)), "StatsService", "自然日 · 跨午夜 · 排行", (255, 245, 230), (238, 196, 135))
    _box(draw, (S(596), S(418), S(802), S(517)), "IconService", "提取 · 缓存 · 字母封面", (255, 245, 230), (238, 196, 135))
    _box(draw, (S(824), S(418), S(1050), S(517)), "Settings / Export", "自启 · CSV · 本地优先", (255, 245, 230), (238, 196, 135))

    # 存储层
    _box(draw, (S(330), S(540), S(520), S(632)), "SQLite (WAL)", "games · sessions · settings", (242, 243, 247), (202, 208, 221))
    _box(draw, (S(540), S(540), S(720), S(632)), "icons/*.png", "永久图标缓存", (242, 243, 247), (202, 208, 221))
    _box(draw, (S(740), S(540), S(910), S(632)), "日志 / CSV", "本地文件", (242, 243, 247), (202, 208, 221))
    _box(draw, (S(930), S(540), S(1110), S(632)), "Windows", "托盘 · 注册表 · 单实例", (242, 243, 247), (202, 208, 221))

    # 箭头：UI -> services
    def arrow(x1, y1, x2, y2, color=(150, 140, 190)):
        draw.line([(S(x1), S(y1)), (S(x2), S(y2))], fill=color + (255,), width=S(2))
        # 箭头
        angle = math.atan2(y2 - y1, x2 - x1)
        size = 7
        for sign in (-1, 1):
            px = x2 - size * math.cos(angle + sign * 0.55)
            py = y2 - size * math.sin(angle + sign * 0.55)
            draw.line([(S(x2), S(y2)), (S(px), S(py))], fill=color + (255,), width=S(2))

    arrow(505, 150, 505, 278)
    arrow(870, 150, 870, 278)
    arrow(505, 398, 505, 418)
    arrow(690, 398, 690, 418)
    arrow(930, 398, 930, 418)
    arrow(690, 517, 690, 540)
    arrow(505, 517, 505, 540)
    arrow(870, 517, 870, 540)

    # 侧注
    note_x, note_y = S(48), S(660)
    draw.rounded_rectangle([note_x, note_y, S(1140), S(744)], radius=S(14), fill=(238, 235, 255), outline=(206, 198, 242), width=S(1))
    draw.text((note_x + S(18), note_y + S(14)), "关键约束：进程只与游戏库中的 exe 完整路径求交集；没有磁盘扫描，也没有未知游戏条目。", font=font(S(16), True), fill=(83, 66, 160))

    # 边框
    draw.rounded_rectangle([S(20), S(20), S(W - 20), S(H - 20)], radius=S(26), outline=(219, 223, 234), width=S(2))
    return image.resize((1240, 780), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cover = make_cover()
    cover.save(OUT / "00-cover.png")
    architecture = make_architecture()
    architecture.save(OUT / "08-architecture.png")
    print("wrote", OUT / "00-cover.png", cover.size)
    print("wrote", OUT / "08-architecture.png", architecture.size)


if __name__ == "__main__":
    main()
