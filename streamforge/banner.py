from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
from streamforge.config import resources


def make_banner(path: Path, width: int, height: int, text: str, image_path: str = "") -> None:
    image = Image.new("RGBA", (width, height))
    draw = ImageDraw.Draw(image)
    for x in range(width):
        ratio = x / max(1, width-1)
        draw.line((x, 0, x, height), fill=(int(76 + 86*ratio), 20, int(200-50*ratio), 255))
    left = 20
    if image_path:
        with Image.open(image_path) as source:
            logo = source.convert("RGBA")
            logo.thumbnail((int(width*.25), height-20))
            image.alpha_composite(logo, (10, (height-logo.height)//2))
            left = logo.width + 28
    if text.strip():
        size = max(14, int(width*.055))
        font_path = resources() / "fonts/DejaVuSans.ttf"
        font = ImageFont.truetype(str(font_path), size)
        lines = []
        line = ""
        for word in text[:200].split():
            candidate = (line + " " + word).strip()
            if draw.textlength(candidate, font=font) > width-left-20 and line:
                lines.append(line); line=word
            else:
                line=candidate
        if line:
            lines.append(line)
        lines=lines[:2]
        for index, line in enumerate(lines):
            while draw.textlength(line, font=font)>width-left-20 and len(line)>1:
                line=line[:-2] + "…"
            draw.text((left, height//2 + (index-(len(lines)-1)/2)*(size+6)), line, font=font, fill="white", anchor="lm")
    image.save(path)
