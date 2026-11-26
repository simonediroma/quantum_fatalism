"""Copertina del podcast (3000×3000): una griglia curvata da un pozzo di potenziale,
la geodetica che la attraversa, titolo e autore. Solo Pillow e font di sistema."""
import math
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

W = 3000
SS = 2                                    # supersampling per linee morbide
BG, GRID, LINE, TEXT, SUB = (14, 17, 28), (60, 74, 110), (232, 168, 76), (240, 236, 226), (168, 176, 196)
SERIF = "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf"
SERIF_I = "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf"
SANS = "/usr/share/fonts/opentype/inter/Inter-Medium.otf"

def warp(x, y, cx, cy, depth, r):
    dx, dy = x - cx, y - cy
    d = math.hypot(dx, dy)
    k = depth * math.exp(-(d / r) ** 2)   # spinta verso il centro del pozzo
    return x - dx * k, y - dy * k

def main(out):
    S = W * SS
    img = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(img)
    cx, cy, depth, r = S * 0.56, S * 0.40, 0.55, S * 0.22
    step, n = S / 24, 120
    for i in range(-2, 27):               # linee della griglia curvata
        for vertical in (True, False):
            pts = []
            for j in range(n + 1):
                a, b = i * step, -2 * step + j * (S + 4 * step) / n
                x, y = (a, b) if vertical else (b, a)
                pts.append(warp(x, y, cx, cy, depth, r))
            d.line(pts, fill=GRID, width=3 * SS)
    glow = Image.new("RGB", (S, S), (0, 0, 0))
    g = ImageDraw.Draw(glow)
    pts = []                              # la geodetica: curva verso il pozzo e lo aggira
    p0, p2 = (-0.05 * S, 0.50 * S), (1.05 * S, 0.06 * S)
    c = (cx - 0.10 * S, cy + 0.20 * S)    # controllo tirato verso il pozzo
    for j in range(400):
        t = j / 399
        x = (1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t ** 2 * p2[0]
        y = (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t ** 2 * p2[1]
        pts.append((x, y))
    g.line(pts, fill=LINE, width=26 * SS)
    glow = glow.filter(ImageFilter.GaussianBlur(40 * SS))
    img = Image.composite(glow, img, glow.convert("L").point(lambda v: min(255, v * 2)))
    d = ImageDraw.Draw(img)
    d.line(pts, fill=LINE, width=9 * SS)
    img = img.resize((W, W), Image.LANCZOS)
    d = ImageDraw.Draw(img)
    shade = Image.new("L", (W, W), 0)     # velo scuro sotto il testo
    ImageDraw.Draw(shade).rectangle([0, int(W * 0.58), W, W], fill=210)
    img = Image.composite(Image.new("RGB", (W, W), BG), img, shade.filter(ImageFilter.GaussianBlur(160)))
    d = ImageDraw.Draw(img)
    m = 190
    top = W * 0.60
    d.text((m, top), "L'universo", font=ImageFont.truetype(SERIF, 300), fill=TEXT)
    d.text((m, top + 310), "a minima energia", font=ImageFont.truetype(SERIF, 300), fill=TEXT)
    d.text((m, top + 690), "Teoria e metafisica del fatalismo quantico", font=ImageFont.truetype(SERIF_I, 112), fill=SUB)
    d.text((m, W - m - 90), "SIMONE RAZZANO", font=ImageFont.truetype(SANS, 92), fill=LINE)
    d.text((W - m, W - m - 90), "PODCAST", font=ImageFont.truetype(SANS, 92), fill=SUB, anchor="ra")
    img.save(out, "JPEG", quality=90, optimize=True)
    print(out, f"{Path(out).stat().st_size // 1024} KB")

if __name__ == "__main__":
    main(Path(__file__).with_name("cover.jpg"))
