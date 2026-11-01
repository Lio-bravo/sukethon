"""Assemble rendered slides into a contact sheet for visual review."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw
p = Path(__file__).resolve().parents[1] / 'deliverables/20261101_roadshow'
files = sorted((p/'preview').glob('*.PNG')) + sorted((p/'preview').glob('*.png'))
files = sorted(set(files), key=lambda f: int(''.join(c for c in f.stem if c.isdigit()) or 0))
assert len(files)==13, [str(f) for f in files]
sheet = Image.new('RGB', (1200, 5*247), '#253342')
for i, f in enumerate(files):
    img=Image.open(f).convert('RGB'); img.thumbnail((390,220))
    x=(i%3)*400; y=(i//3)*247
    sheet.paste(img,(x,y)); ImageDraw.Draw(sheet).text((x+8,y+224),str(i+1),fill='white')
sheet.save(p/'slides_overview.jpg')
print('Preview:', p/'slides_overview.jpg')
