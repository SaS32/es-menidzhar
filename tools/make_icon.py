"""Generate the Windows icon for ЕС Мениджър: static/icon.ico (+ icon.png).

Run:  python tools/make_icon.py      (needs Pillow)

A white apartment block on the app's accent-blue tile. Every size is drawn
separately (4x supersampled, then downscaled) so the 16/24 px versions get a
simpler window grid instead of a blurred copy of the big one.
"""

import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_ICO = os.path.join(ROOT, "static", "icon.ico")
OUT_PNG = os.path.join(ROOT, "static", "icon.png")

SIZES = [16, 24, 32, 48, 64, 128, 256]
SS = 4  # supersampling factor

TOP = (59, 130, 246)      # --accent (dark theme)
BOTTOM = (29, 78, 216)    # --accent-dk
WHITE = (255, 255, 255)
WINDOW = (37, 99, 235)    # --accent
LIT = (251, 191, 36)      # a couple of lit windows, amber


def draw(size):
    S = size * SS
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))

    # Vertical gradient tile with rounded corners.
    grad = Image.new("RGBA", (S, S))
    gd = ImageDraw.Draw(grad)
    for y in range(S):
        t = y / (S - 1)
        c = tuple(round(TOP[i] + (BOTTOM[i] - TOP[i]) * t) for i in range(3))
        gd.line([(0, y), (S, y)], fill=c + (255,))
    mask = Image.new("L", (S, S), 0)
    pad = round(S * 0.03)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, S - 1 - pad, S - 1 - pad], radius=round(S * 0.22), fill=255
    )
    img.paste(grad, (0, 0), mask)

    d = ImageDraw.Draw(img)
    small = size <= 24
    cols, rows = (2, 3) if small else (3, 4)

    # Building body.
    bx0, bx1 = S * 0.24, S * 0.76
    by0, by1 = S * (0.20 if small else 0.18), S * 0.84
    d.rounded_rectangle([bx0, by0, bx1, by1], radius=S * 0.03, fill=WHITE)
    # Roof ledge.
    d.rectangle([bx0 - S * 0.04, by0 - S * 0.02, bx1 + S * 0.04, by0 + S * 0.035],
                fill=WHITE)
    # Ground line.
    d.rectangle([S * 0.14, by1 - S * 0.01, S * 0.86, by1 + S * 0.035], fill=WHITE)

    # Windows grid, leaving room at the bottom for the door.
    door_h = (by1 - by0) * (0.26 if small else 0.22)
    gx0, gx1 = bx0 + S * 0.06, bx1 - S * 0.06
    gy0, gy1 = by0 + S * 0.08, by1 - door_h - S * 0.05
    gap = S * (0.06 if small else 0.045)
    ww = (gx1 - gx0 - gap * (cols - 1)) / cols
    wh = (gy1 - gy0 - gap * (rows - 1)) / rows
    lit = {(0, 1), (rows - 2, cols - 1)} if not small else {(1, 0)}
    for r in range(rows):
        for c in range(cols):
            x = gx0 + c * (ww + gap)
            y = gy0 + r * (wh + gap)
            d.rectangle([x, y, x + ww, y + wh], fill=LIT if (r, c) in lit else WINDOW)

    # Door.
    dw = (bx1 - bx0) * (0.30 if small else 0.24)
    cx = (bx0 + bx1) / 2
    d.rounded_rectangle([cx - dw / 2, by1 - door_h, cx + dw / 2, by1],
                        radius=S * 0.02, fill=WINDOW)

    return img.resize((size, size), Image.LANCZOS)


def main():
    images = {s: draw(s) for s in SIZES}
    big = images[256]
    big.save(OUT_ICO, format="ICO", sizes=[(s, s) for s in SIZES],
             append_images=[images[s] for s in SIZES if s != 256])
    big.save(OUT_PNG)
    print("wrote", OUT_ICO)
    print("wrote", OUT_PNG)


if __name__ == "__main__":
    main()
