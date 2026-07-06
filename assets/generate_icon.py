"""Generate the Labs Experience Controller icon.

Deep-space rounded square, an amber occupant dot, and cyan presence
arcs — presence radiating through a space. Outputs the two sizes the
home-assistant/brands repo expects.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

SIZE = 512
BG = (11, 18, 32, 255)          # labs deep space
CYAN = (34, 211, 238)           # electric cyan (labs accent)
AMBER = (255, 180, 84, 255)     # occupant warmth

OUT = Path(__file__).parent / "brands" / "custom_integrations" / "labs_experience"


def build() -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((0, 0, SIZE - 1, SIZE - 1), radius=116, fill=BG)

    cx, cy = 172, 344

    # Presence arcs sweeping up-right, fading with distance.
    for radius, alpha, width in ((208, 110, 26), (148, 170, 28), (92, 255, 30)):
        overlay = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.arc(
            (cx - radius, cy - radius, cx + radius, cy + radius),
            start=-83,
            end=7,
            fill=(*CYAN, alpha),
            width=width,
        )
        img = Image.alpha_composite(img, overlay)

    draw = ImageDraw.Draw(img)
    # Occupant glow + dot.
    glow = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse(
        (cx - 58, cy - 58, cx + 58, cy + 58), fill=(255, 180, 84, 60)
    )
    img = Image.alpha_composite(img, glow)
    draw = ImageDraw.Draw(img)
    draw.ellipse((cx - 34, cy - 34, cx + 34, cy + 34), fill=AMBER)
    return img


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    icon = build()
    icon.save(OUT / "icon@2x.png")
    icon.resize((256, 256), Image.LANCZOS).save(OUT / "icon.png")
    print(f"wrote {OUT}/icon.png and icon@2x.png")


if __name__ == "__main__":
    main()
