"""离线绘制中国高速标志牌面；Pillow只用于制作，不进入游戏运行期。"""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets/game/expressway/signs"
FONT = ROOT / "assets/game/ui/fonts/SourceHanSansSC-Heavy.otf"
WHITE, GREEN, RED, BLACK, YELLOW = "#f5f4ec", "#096a42", "#ca252d", "#171a19", "#ffcf18"


def text(draw, xy, value, size, color=WHITE):
    draw.text(xy, value, fill=color, font=ImageFont.truetype(str(FONT), size), anchor="mm")


def board(size):
    image = Image.new("RGB", size, GREEN)
    draw = ImageDraw.Draw(image)
    margin = max(8, size[1] // 30)
    draw.rounded_rectangle((margin, margin, size[0]-margin-1, size[1]-margin-1),
                           radius=margin, outline=WHITE, width=max(5, margin//2))
    return image, draw


def arrow(draw, x, y, length):
    draw.line((x, y, x, y+length), fill=WHITE, width=int(length*.15))
    draw.polygon(((x-length*.25, y+length*.74), (x+length*.25, y+length*.74),
                  (x, y+length*1.05)), fill=WHITE)


def route(draw, box):
    x, y, w, h = box
    draw.rounded_rectangle((x, y, x+w, y+h), radius=8, fill=WHITE)
    draw.rectangle((x+5, y+5, x+w-5, y+h*.30), fill=RED)
    draw.rectangle((x+5, y+h*.30, x+w-5, y+h-5), fill=GREEN)
    text(draw, (x+w/2,y+h*.16), "省级高速", int(h*.16))
    text(draw, (x+w/2,y+h*.62), "S18", int(h*.43))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ("gantry", "route-direction", "bridge-advance", "advance-sign"):
        size = (1536, 288) if name == "gantry" else (1024, 416)
        image, draw = board(size)
        if name == "gantry":
            route(draw, (70, 30, 150, 180))
            text(draw, (900, 87), "海滨　临海", 112)
            text(draw, (900, 183), "Haibin    Linhai", 44)
            for x in (288, 768, 1248):
                arrow(draw, x, 215, 52)
        elif name in ("route-direction", "advance-sign"):
            route(draw, (55, 70, 200, 260))
            text(draw, (620, 145), "海滨高速", 105)
            text(draw, (620, 267), "HAIBIN EXPWY", 46)
        else:
            text(draw, (512, 140), "海湾一桥", 112)
            text(draw, (512, 270), "HAIWAN BRIDGE", 50)
        image.save(OUT / f"{name}.png")
    image = Image.new("RGB", (512, 512), WHITE)
    draw = ImageDraw.Draw(image)
    draw.ellipse((4,4,508,508), fill=RED)
    draw.ellipse((54,54,458,458), fill=WHITE)
    text(draw, (256,250), "100", 228, BLACK)
    image.save(OUT / "speed-limit.png")
    for name in ("curve-left", "curve-right", "hill-warning", "wind-warning"):
        image = Image.new("RGB", (512, 444), BLACK)
        draw = ImageDraw.Draw(image)
        draw.polygon(((256,12),(14,432),(498,432)), fill=BLACK)
        draw.polygon(((256,54),(59,407),(453,407)), fill=YELLOW)
        if name.startswith("curve"):
            draw.line(((268,362),(268,274),(215,219),(174,219)), fill=BLACK, width=39, joint="curve")
            draw.polygon(((138,219),(198,175),(198,262)), fill=BLACK)
            if name == "curve-right":
                image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif name == "hill-warning":
            draw.polygon(((128,268),(381,365),(128,365)), fill=BLACK)
            draw.ellipse((225,254,254,283), fill=BLACK)
            draw.ellipse((290,280,319,309), fill=BLACK)
            draw.polygon(((224,235),(298,261),(325,287),(209,247)), fill=BLACK)
        else:
            draw.line(((193,191),(193,364)), fill=BLACK, width=15)
            draw.polygon(((200,192),(371,231),(371,275),(200,251)), fill=BLACK)
            for first in (230,291):
                draw.polygon(((first,204+(first-230)*.22),(first+23,209+(first-230)*.22),
                              (first+23,256+(first-230)*.15),(first,253+(first-230)*.15)), fill=YELLOW)
        image.save(OUT / f"{name}.png")
    image, draw = board((256,384))
    route(draw, (42,22,172,135))
    image.save(OUT / "kilometer-base.png")
    digits = Image.new("RGB", (10*96,128), GREEN)
    draw = ImageDraw.Draw(digits)
    for digit in range(10):
        text(draw, (digit*96+48,64), str(digit), 105)
    digits.save(OUT / "digits.png")


if __name__ == "__main__":
    build()
