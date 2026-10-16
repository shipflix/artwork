"""Shared rendering primitives. No machine-specific paths or bundled credentials."""
from pathlib import Path
import os,re,hashlib,io
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parent.parent
STATE=Path(os.environ.get('ARTWORK_STATE',str(ROOT/'.state')))
CACHE=STATE/'cache'
for p in [CACHE/'images',CACHE/'api']:p.mkdir(parents=True,exist_ok=True)
FONT=os.environ.get('ARTWORK_FONT','/System/Library/Fonts/HelveticaNeue.ttc')
def slug(s):return re.sub(r'[^a-z0-9]+','-',s.lower()).strip('-')
def digest(s):return hashlib.sha256(s.encode()).hexdigest()
def font(size,bold=True,path=None,index=None):return ImageFont.truetype(path or FONT,int(size),index=(1 if bold else 0) if index is None else index)
def title_lines(title,maxw):
 for size in range(190,86,-4):
  ft=font(size)
  if ft.getlength(title)<=maxw:return [title],ft
  candidates=[];words=title.split()
  for i in range(1,len(words)):
   lines=[' '.join(words[:i]),' '.join(words[i:])]
   if max(ft.getlength(x) for x in lines)<=maxw:candidates.append((abs(ft.getlength(lines[0])-ft.getlength(lines[1])),lines))
  if candidates:return min(candidates,key=lambda x:x[0])[1],ft
 # Long franchise names wrap, retaining a legible minimum size.
 ft=font(110);lines=[];line=''
 for word in title.split():
  if line and ft.getlength(line+' '+word)>maxw:lines.append(line);line=word
  else:line=(line+' '+word).strip()
 if line:lines.append(line)
 return lines,ft

def poster_card(im,size):
 p=ImageOps.fit(im.convert('RGB'),size,Image.Resampling.LANCZOS);mask=Image.new('L',size);ImageDraw.Draw(mask).rounded_rectangle((0,0,*size),radius=62,fill=255);p=p.convert('RGBA');p.putalpha(mask);border=Image.new('RGBA',size);ImageDraw.Draw(border).rounded_rectangle((1,1,size[0]-2,size[1]-2),radius=61,outline=(255,255,255,32),width=2);return Image.alpha_composite(p,border)
