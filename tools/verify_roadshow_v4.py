"""Check actual slide exports and delivery traceability after PowerPoint rendering."""
from pathlib import Path
import hashlib,json
from PIL import Image,ImageDraw
from pptx import Presentation
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'deliverables/20261101_roadshow_v4_fullfront'
files=sorted((OUT/'preview').glob('slide_*.png'))
assert len(files)==5, files
sheet=Image.new('RGB',(1600,5*470),'#253342');draw=ImageDraw.Draw(sheet)
for i,p in enumerate(files):
    im=Image.open(p).convert('RGB');assert im.size==(1600,900)
    assert len(im.resize((160,90)).getcolors(14401) or [])>30
    im.thumbnail((800,450));sheet.paste(im,(0,i*470));draw.text((820,i*470+20),f'Slide {i+1}',fill='white')
sheet=sheet.crop((0,0,900,5*470));sheet.save(OUT/'slides_contactsheet.jpg',quality=92)
ppt=next(OUT.glob('*.pptx'));prs=Presentation(ppt);assert len(prs.slides)==5
for i,s in enumerate(prs.slides):
    for shape in s.shapes:
        assert shape.left>=0 and shape.top>=0,(i,shape.name)
        assert shape.left+shape.width<=prs.slide_width+20000,(i,shape.name,'right overflow')
        assert shape.top+shape.height<=prs.slide_height+20000,(i,shape.name,'bottom overflow')
m=json.loads((OUT/'manifest.json').read_text(encoding='utf-8'))
assert m['normal_summary']['passed']==8 and m['video']['frame_count']==m['video']['decoded_frames']
m['render_verification']={'renderer':'Microsoft PowerPoint COM','slides_rendered':len(files),'resolution':[1600,900],'pdf_present':(OUT/'roadshow_v4.pdf').exists(),'slide_bounds':'pass'}
(OUT/'manifest.json').write_text(json.dumps(m,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'SHA256SUMS.txt').write_text('\n'.join(f'{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(OUT).as_posix()}' for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')+'\n',encoding='utf-8')
print(json.dumps(m['render_verification'],indent=2));print(OUT/'slides_contactsheet.jpg')
