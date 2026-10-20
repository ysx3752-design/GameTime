"""生成应用图标（可重复执行）。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gametime" / "resources"
SIZE = 1024


def _lerp(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    return tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def make_icon() -> Image.Image:
    scale = 2
    size = SIZE * scale
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    # 对角线渐变（逐行绘制，最后统一缩放，边缘抗锯齿）
    top_left = (136, 107, 255)
    bottom_right = (66, 40, 160)
    for y in range(size):
        for_t = y / size
        for x in range(0, size, 4):
            t = (x / size + for_t) / 2
            color = _lerp(top_left, bottom_right, min(1.0, t))
            draw.rectangle([x, y, min(size, x + 4), y + 1], fill=(*color, 255))
    mask = Image.new("L", (size, size), 0)
    mask_draw = ImageDraw.Draw(mask)
    margin = int(size * 0.035)
    mask_draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(size * 0.235),
        fill=255,
    )
    image.putalpha(mask)

    # 内部柔光
    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    glow_draw.ellipse(
        [int(size * 0.28), int(size * -0.18), int(size * 1.06), int(size * 0.55)],
        fill=(255, 255, 255, 26),
    )
    image.alpha_composite(glow)

    # 外描边
    border = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    border_draw = ImageDraw.Draw(border)
    border_draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=int(size * 0.235),
        outline=(255, 255, 255, 40),
        width=int(size * 0.004),
    )
    image.alpha_composite(border)

    # 游戏手柄式圆形底盘
    circle_box = [
        int(size * 0.205),
        int(size * 0.205),
        int(size * 0.795),
        int(size * 0.795),
    ]
    details = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(details)
    draw.ellipse(
        circle_box,
        fill=(255, 255, 255, 18),
        outline=(255, 255, 255, 34),
        width=int(size * 0.006),
    )

    # 播放三角
    triangle = [
        (int(size * 0.415), int(size * 0.345)),
        (int(size * 0.415), int(size * 0.655)),
        (int(size * 0.705), int(size * 0.5)),
    ]
    shadow = [(x + int(size * 0.012), y + int(size * 0.016)) for x, y in triangle]
    draw.polygon(shadow, fill=(27, 14, 70, 100))
    draw.polygon(triangle, fill=(255, 255, 255, 252))

    # 青绿色时间点
    dot_r = int(size * 0.044)
    dot_cx, dot_cy = int(size * 0.735), int(size * 0.285)
    draw.ellipse(
        [dot_cx - dot_r, dot_cy - dot_r, dot_cx + dot_r, dot_cy + dot_r],
        fill=(53, 214, 165, 255),
    )
    image.alpha_composite(details)

    # 降低到目标尺寸
    return image.resize((SIZE, SIZE), Image.Resampling.LANCZOS)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = make_icon()
    icon.save(OUT / "app_icon.png")
    icon.resize((512, 512), Image.Resampling.LANCZOS).save(OUT / "app_icon_512.png")
    icon.save(
        OUT / "app.ico",
        format="ICO",
        sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Wrote icons to {OUT}")


if __name__ == "__main__":
    main()
