"""Draws the Discord Compress logo: ui/logo.png and icon.ico."""
import os
from PIL import Image, ImageDraw, ImageFilter

S = 1024
HERE = os.path.dirname(os.path.abspath(__file__))


def lerp(a, b, t):
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))


def gradient(size, stops):
    # diagonal gradient through the colour stops
    img = Image.new("RGB", (size, size))
    px = img.load()
    for y in range(size):
        for x in range(size):
            t = (x + y) / (2 * size - 2) * (len(stops) - 1)
            i = min(int(t), len(stops) - 2)
            px[x, y] = lerp(stops[i], stops[i + 1], t - i)
    return img


def draw():
    pad, r = 64, 230
    tile = gradient(S, [(88, 101, 242), (124, 92, 246), (214, 88, 214)]).convert("RGBA")
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, S - pad, S - pad], r, fill=255)

    # glass sheen on the upper half and a thin bright rim
    sheen = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(sheen)
    d.ellipse([-200, -620, S + 200, S * 0.52], fill=(255, 255, 255, 40))
    sheen = sheen.filter(ImageFilter.GaussianBlur(90))
    d = ImageDraw.Draw(sheen)
    d.rounded_rectangle([pad + 6, pad + 6, S - pad - 6, S - pad - 6], r - 6,
                        outline=(255, 255, 255, 90), width=10)
    tile = Image.alpha_composite(tile, sheen)

    # glyph: play triangle squeezed by two chevrons
    glyph = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    g = ImageDraw.Draw(glyph)
    white = (255, 255, 255, 255)
    g.polygon([(420, 380), (420, 644), (640, 512)], fill=white)
    w = 46
    g.line([(352, 206), (512, 300), (672, 206)], fill=white, width=w, joint="curve")
    g.line([(352, 818), (512, 724), (672, 818)], fill=white, width=w, joint="curve")
    for x, y in [(352, 206), (672, 206), (352, 818), (672, 818)]:
        g.ellipse([x - w / 2, y - w / 2, x + w / 2, y + w / 2], fill=white)

    shadow = Image.new("RGBA", (S, S), (20, 10, 60, 0))
    shadow.putalpha(glyph.getchannel("A").point(lambda a: a * 0.45))
    shadow = shadow.filter(ImageFilter.GaussianBlur(18)).transform(
        (S, S), Image.AFFINE, (1, 0, 0, 0, 1, -14))
    tile = Image.alpha_composite(Image.alpha_composite(tile, shadow), glyph)

    out = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    out.paste(tile, (0, 0), mask)
    return out


if __name__ == "__main__":
    logo = draw()
    os.makedirs(os.path.join(HERE, "ui"), exist_ok=True)
    logo.resize((256, 256), Image.LANCZOS).save(os.path.join(HERE, "ui", "logo.png"))
    logo.save(os.path.join(HERE, "icon.ico"),
              sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    logo.resize((512, 512), Image.LANCZOS).save(os.path.join(HERE, "logo-512.png"))
