"""Renders branded post cards with Pillow (free) and a short 9:16 video with ffmpeg (free)."""
import io
import shutil
import subprocess
from pathlib import Path

import requests
from PIL import Image, ImageDraw, ImageFont

INK = (27, 31, 59)
ACCENT = (91, 91, 214)
SOFT = (201, 203, 234)
WHITE = (255, 255, 255)

FONT_BOLD = ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
             "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"]
FONT_REG = ["/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"]


def _font(paths, size):
    for p in paths:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=font) <= max_w or not cur:
            cur = t
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _fit_headline(draw, text, max_w, max_lines, start, floor):
    size = start
    while size >= floor:
        f = _font(FONT_BOLD, size)
        lines = _wrap(draw, text, f, max_w)
        if len(lines) <= max_lines:
            return f, lines, size
        size -= 4
    f = _font(FONT_BOLD, floor)
    return f, _wrap(draw, text, f, max_w)[:max_lines], floor


def _cover(url):
    try:
        r = requests.get(url, timeout=30, headers={"User-Agent": "Mozilla/5.0"})
        r.raise_for_status()
        return Image.open(io.BytesIO(r.content)).convert("RGB")
    except Exception:
        return None


def render_card(post: dict, size=(1080, 1350), use_cover=True) -> Image.Image:
    W, H = size
    img = Image.new("RGB", size, INK)
    d = ImageDraw.Draw(img)
    pad = 84
    # soft accent shapes
    d.ellipse((W - 420, -220, W + 200, 400), fill=(38, 43, 84))
    d.ellipse((-260, H - 420, 340, H + 200), fill=(38, 43, 84))

    y = 96 if H < 1500 else 200
    lab = post["label"]
    lf = _font(FONT_BOLD, 30)
    lw = d.textlength(lab, font=lf)
    d.rounded_rectangle((pad, y, pad + lw + 56, y + 62), radius=31, fill=ACCENT)
    d.text((pad + 28, y + 14), lab, font=lf, fill=WHITE)
    y += 110

    fy = H - 190 if H < 1500 else H - 330  # footer line

    cover = _cover(post["cover"]) if (use_cover and post.get("cover")) else None
    if cover:
        box_w, box_h = W - 2 * pad, int((H - 2 * pad) * 0.34)
        cover.thumbnail((box_w, box_h))
    hf, lines, hs = _fit_headline(d, post["headline"], W - 2 * pad, 5 if not cover else 3, 96, 52)
    bf = _font(FONT_REG, 40)
    body_lines = _wrap(d, post["body"], bf, W - 2 * pad)[:6]
    block_h = (cover.height + 48 if cover else 0) + int(hs * 1.18) * len(lines) + 26 + 58 * len(body_lines)
    room = (fy - 40) - y
    y += max(0, (room - block_h) // 2)

    if cover:
        mask = Image.new("L", cover.size, 0)
        ImageDraw.Draw(mask).rounded_rectangle((0, 0, *cover.size), radius=28, fill=255)
        img.paste(cover, ((W - cover.width) // 2, y), mask)
        y += cover.height + 48
    for ln in lines:
        d.text((pad, y), ln, font=hf, fill=WHITE)
        y += int(hs * 1.18)
    y += 26
    for ln in body_lines:
        d.text((pad, y), ln, font=bf, fill=SOFT)
        y += 58

    # footer
    d.line((pad, fy, W - pad, fy), fill=(60, 66, 110), width=3)
    d.text((pad, fy + 34), "VeloceStack", font=_font(FONT_BOLD, 44), fill=WHITE)
    sub = "Link in bio" if post["type"] != "product" else "Instant digital download"
    if post.get("price") and post["type"] == "product":
        sub = f"From {post['price']}  |  instant download"
    if post["type"] == "freebie":
        sub = "Free download  |  link in bio"
    d.text((pad, fy + 92), sub, font=_font(FONT_REG, 32), fill=SOFT)
    return img


def render_video(image_path: Path, out_path: Path, seconds=7) -> bool:
    """Slow-zoom vertical video from a 1080x1920 card. Returns False if ffmpeg is unavailable."""
    if not shutil.which("ffmpeg"):
        return False
    frames = seconds * 30
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(image_path),
           "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
           "-vf", f"scale=2160:3840,zoompan=z='min(zoom+0.0007,1.10)':d={frames}:s=1080x1920:fps=30,format=yuv420p",
           "-t", str(seconds), "-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", "-shortest", str(out_path)]
    try:
        subprocess.run(cmd, check=True, timeout=180)
        return out_path.exists()
    except Exception as e:
        print("video render failed:", e)
        return False
