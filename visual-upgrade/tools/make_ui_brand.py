"""使用本机字体绘制静态品牌字图，游戏运行时只读取 PNG。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "assets/game/ui/coastal-drive-logo.png"
TITLE_FONT = "C:/Windows/Fonts/msyhbd.ttc"

PAGE_TITLES = {
    "选择驾驶": "menu",
    "无限高速": "highway",
    "车库": "garage",
    "声音设置": "audio",
    "已暂停": "pause",
    "挑战成功": "success",
    "挑战失败": "failure",
    "驾驶结束": "finished",
}


def main():
    image = Image.new("RGBA", (900, 190), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    latin = ImageFont.truetype("C:/Windows/Fonts/impact.ttf", 112)
    chinese = ImageFont.truetype("C:/Windows/Fonts/msyhbd.ttc", 47)
    ink = (16, 43, 58, 255)
    orange = (244, 124, 36, 255)
    draw.text((34, 5), "COASTAL DRIVE", font=latin, fill=ink)
    draw.polygon(((36, 133), (545, 133), (520, 151), (23, 151)), fill=orange)
    for i in range(5):
        x = 42 + i * 44
        draw.polygon(((x, 157), (x + 18, 157), (x + 9, 169), (x - 9, 169)), fill=orange)
    draw.text((625, 130), "海岸驾驶", font=chinese, fill=ink)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    image.save(DEST)
    for title, slug in PAGE_TITLES.items():
        title_image = Image.new("RGBA", (650, 130), (0, 0, 0, 0))
        title_draw = ImageDraw.Draw(title_image)
        font = ImageFont.truetype(TITLE_FONT, 86)
        box = title_draw.textbbox((0, 0), title, font=font, stroke_width=1)
        x = (650 - (box[2] - box[0])) // 2
        tint = (160, 48, 30, 255) if slug == "failure" else (18, 50, 63, 255)
        title_draw.text((x, 4 - box[1]), title, font=font, fill=tint, stroke_width=1)
        title_image.save(DEST.with_name(f"title-{slug}.png"))


if __name__ == "__main__":
    main()
