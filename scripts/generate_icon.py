"""Generate the project's original layers-to-joints icon (Pillow only)."""

from pathlib import Path

from PIL import Image, ImageDraw


def generate():
    root = Path(__file__).resolve().parents[1]
    assets = root / "assets"
    assets.mkdir(exist_ok=True)
    scale = 4
    size = 512
    icon = Image.new("RGBA", (size * scale, size * scale))
    draw = ImageDraw.Draw(icon)

    def polygon(points, color):
        draw.polygon([(round(x * scale), round(y * scale)) for x, y in points], fill=color)

    def line(points, color, width):
        draw.line([(round(x * scale), round(y * scale)) for x, y in points],
                  fill=color, width=round(width * scale), joint="curve")

    def circle(x, y, radius, color):
        draw.ellipse(tuple(round(v * scale) for v in (x-radius, y-radius, x+radius, y+radius)), fill=color)

    # Transparent corners and a restrained blue gradient remain legible at 16px.
    mask = Image.new("L", icon.size)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, icon.width-1, icon.height-1), radius=112 * scale, fill=255)
    for y in range(icon.height):
        t = y / (icon.height - 1)
        color = tuple(round(a + (b-a)*t) for a, b in zip((57, 112, 245), (41, 62, 188)))
        draw.line((0, y, icon.width, y), fill=color + (255,))
    icon.putalpha(mask)

    # Three offset design layers; no third-party product logo is used.
    polygon([(70, 304), (190, 242), (310, 304), (190, 370)], "#8EC8FF")
    polygon([(70, 248), (190, 186), (310, 248), (190, 314)], "#C6E5FF")
    polygon([(70, 192), (190, 130), (310, 192), (190, 258)], "#FFFFFF")

    # Orange joints suggest an editable skeleton, connected to the source layers.
    line([(321, 248), (359, 248)], "#FFFFFF", 15)
    polygon([(350, 227), (378, 248), (350, 269)], "#FFFFFF")
    line([(379, 149), (401, 248), (379, 347)], "#FFB455", 19)
    for x, y, radius in ((379, 149, 29), (401, 248, 29), (379, 347, 29)):
        circle(x, y, radius, "#FFAF45")
        circle(x-5, y-6, 9, "#FFE0A9")

    icon = icon.resize((size, size), Image.Resampling.LANCZOS)
    icon.save(assets / "app-icon.png", optimize=True)
    icon.save(assets / "app-icon.ico", sizes=[(n, n) for n in (16, 20, 24, 32, 40, 48, 64, 96, 128, 256)])
    print("Generated app-icon.png and multi-resolution app-icon.ico")


if __name__ == "__main__":
    generate()
