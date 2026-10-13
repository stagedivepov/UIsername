"""Export the original Segoe UI Bold u. with centered visible glyph bounds."""
import os
import re
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts' / 'segoeuib.ttf'
    if not font_path.is_file():
        raise SystemExit('Regenerate these assets on Windows with Segoe UI Bold installed.')
    size = 1600
    scale = size / 100
    font = ImageFont.truetype(str(font_path), round(64 * scale))
    advance = font.getlength('u') - 4.48 * scale
    u = font.getbbox('u', anchor='ls')
    dot = font.getbbox('.', anchor='ls')
    left, top = min(u[0], advance + dot[0]), min(u[1], dot[1])
    right, bottom = max(u[2], advance + dot[2]), max(u[3], dot[3])
    x, y = size / 2 - (left + right) / 2, size / 2 - (top + bottom) / 2
    monogram = (f'<text x="{x/scale:.4f}" y="{y/scale:.4f}" font-family="Segoe UI,Arial,sans-serif" '
                'font-weight="700" font-size="64" letter-spacing="-4.48" fill="currentColor">u.</text>')
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
           '<rect x="3" y="3" width="94" height="94" rx="22" fill="#191522"/>'
           '<g color="#b68cff">' + monogram + '</g></svg>\n')
    (ROOT / 'ui/logo.svg').write_text(svg, encoding='utf-8')
    html_path = ROOT / 'ui/index.html'
    html = html_path.read_text(encoding='utf-8')
    html = re.sub(r'<symbol id="i-monogram"[^>]*>.*?</symbol>',
                  '<symbol id="i-monogram" viewBox="15 15 70 70">' + monogram + '</symbol>', html, count=1, flags=re.S)
    html_path.write_text(html, encoding='utf-8')
    image = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((round(3*scale), round(3*scale), round(97*scale), round(97*scale)),
                           radius=round(22*scale), fill='#191522')
    draw.text((x, y), 'u', font=font, fill='#b68cff', anchor='ls')
    draw.text((x + advance, y), '.', font=font, fill='#b68cff', anchor='ls')
    image.resize((512, 512), Image.Resampling.LANCZOS).save(ROOT / 'ui/logo.png')
    image.resize((256, 256), Image.Resampling.LANCZOS).save(
        ROOT / 'ui/app.ico', format='ICO', sizes=[(n,n) for n in (16,24,32,48,64,128,256)])


if __name__ == '__main__': main()
