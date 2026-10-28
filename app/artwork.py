"""Approved tile styles, globally unique poster allocation, background URLs preserved."""
from pathlib import Path
import json,hashlib,math,argparse,concurrent.futures as cf,copy
from collections import deque
from PIL import Image,ImageDraw,ImageOps,ImageFilter
from . import render as base
ROOT=base.ROOT;OUT=base.STATE/'rendered';ASSETS=ROOT/'assets'
W,H=2560,1440;WHITE='#f5f5f5';CHARCOAL=(26,26,26,255)
TITLE_OVERRIDES=json.loads((ROOT/'data/title-overrides.json').read_text()) if (ROOT/'data/title-overrides.json').exists() else {}
STACK_GROUPS={'Discover','Genres','Seasonal','Film Collections','By Decade','Documentaries','Kids and Family','Reality TV'}
def tile_name(record):return base.slug(record['category'])+'--'+base.slug(record['title'])+'--'+record['id'][:8]+'.webp'
def smooth(t):
    t=max(0,min(1,t));return t*t*(3-2*t)
def write_tile(tile,path):tile.convert('RGB').save(path,'WEBP',quality=92,method=5)
def draw_title(tile,group,title):
    d=ImageDraw.Draw(tile);left=205;maxw=1035
    if title in TITLE_OVERRIDES:
        lines=TITLE_OVERRIDES[title];size=190
        while max(base.font(size).getlength(line) for line in lines)>maxw:size-=2
        ft=base.font(size);lineh=round(size*1.12);y=(H-lineh*len(lines))//2-15
        for i,line in enumerate(lines):d.text((left,y+i*lineh),line,font=ft,fill='#d8c39d' if group=='Film Collections' and line=='Collections' else WHITE)
        return
    if group=='By Decade':
        title={'10s Movies':'2010s','00s Movies':'2000s','90s Movies':'1990s','80s Movies':'1980s','70s Movies':'1970s','60s Movies':'1960s','50s Movies':'1950s','2020s Movies':'2020s'}[title]
        size=310
        while base.font(size).getlength(title)>1100:size-=2
        ft=base.font(size);bb=d.textbbox((0,0),title,font=ft);y=(H-(bb[3]-bb[1]))/2-bb[1]
        d.text((left,y),title[:-1],font=ft,fill=WHITE);d.text((left+ft.getlength(title[:-1]),y),'s',font=ft,fill='#c8df82');return
    if group=='Discover':lines=title.split(' ',1);ft=base.font(190)
    elif group=='Film Collections':
        stem=title.removesuffix(' Collections');size=190
        while max(base.font(size).getlength(stem),base.font(size).getlength('Collections'))>maxw and size>130:size-=2
        ft=base.font(size)
        if ft.getlength(stem)>maxw:
            stemlines,_=base.title_lines(stem,maxw);lines=stemlines+['Collections']
        else:lines=[stem,'Collections']
    else:lines,ft=base.title_lines(title,maxw)
    lineh=round(ft.size*1.12);y=(H-lineh*len(lines))//2-15
    for i,line in enumerate(lines):
        colour=WHITE
        if group=='Discover' and i==len(lines)-1:colour='#c9b4f5'
        if group=='Film Collections' and line=='Collections':colour='#d8c39d'
        d.text((left,y+i*lineh),line,font=ft,fill=colour)
def poster_image(t):
    key=hashlib.sha256(('https://image.tmdb.org/t/p/w500'+t['poster_path']).encode()).hexdigest()
    return Image.open(base.CACHE/'images'/key).convert('RGBA')
def stack_tile(group,title,titles,out):
    tile=Image.new('RGBA',(W,H),CHARCOAL)
    if group=='Discover':
        glow=Image.new('RGBA',(W,H));ImageDraw.Draw(glow).ellipse((1420,1120,2470,1305),fill=(116,76,193,75));tile=Image.alpha_composite(tile,glow.filter(ImageFilter.GaussianBlur(70)))
    draw_title(tile,group,title)
    if group=='By Decade':cardw,cardh=600,900;specs=[(1810,735,8),(1990,715,1),(2190,744,-4)]
    else:cardw,cardh=692,1038;specs=[(1760,735,8),(1955,715,1),(2153,744,-4)]
    for t,(cx,cy,angle) in zip(reversed(titles),specs):
        card=base.poster_card(poster_image(t),(cardw,cardh));rot=card.rotate(angle,Image.Resampling.BICUBIC,expand=True)
        shadow=Image.new('RGBA',rot.size);shadow.putalpha(rot.getchannel('A').point(lambda v:int(v*.27)));shadow=shadow.filter(ImageFilter.GaussianBlur(18))
        xy=(int(cx-rot.width/2),int(cy-rot.height/2));tile.alpha_composite(shadow,(xy[0]+6,xy[1]+14));tile.alpha_composite(rot,xy)
    write_tile(tile,out)
def centred_logo(entry,out,size=(W,H),black=False):
    logo=Image.open(ROOT/entry['file']).convert('RGBA');logo=logo.crop(logo.getchannel('A').getbbox())
    w,h=size
    if size==(W,H):
        scale=min(math.sqrt(620000/(logo.width*logo.height)),1650/logo.width,850/logo.height)
    else:scale=min(w*.68/logo.width,h*.30/logo.height)
    logo=logo.resize((max(1,round(logo.width*scale)),max(1,round(logo.height*scale))),Image.Resampling.LANCZOS)
    tile=Image.new('RGBA',size,(0,0,0,255) if black else CHARCOAL);tile.alpha_composite(logo,((w-logo.width)//2,(h-logo.height)//2));write_tile(tile,out)
def mood_tile(title,entry,out):
    tile=Image.new('RGBA',(W,H),CHARCOAL)
    photo=ImageOps.fit(Image.open(ROOT/entry['file']).convert('RGBA'),(1410,H),Image.Resampling.LANCZOS,centering=tuple(entry.get('centering',[.5,.5])))
    mask=Image.new('L',(353,360));p=mask.load()
    for y in range(360):
        for x in range(353):p[x,y]=round(255*smooth(x/100)*(.94-.20*(y/359)**2))
    photo.putalpha(mask.resize(photo.size,Image.Resampling.BICUBIC));tile.alpha_composite(photo,(1150,0));draw_title(tile,'Moods & Vibes',title);write_tile(tile,out)
def anime_tile(title,entry,out):
    tile=Image.new('RGBA',(W,H),CHARCOAL);art=Image.open(ROOT/entry['file']).convert('RGBA');art=art.crop(art.getchannel('A').getbbox())
    scale=min(1360/art.width,1560/art.height)*entry.get('renderScale',1);art=art.resize((round(art.width*scale),round(art.height*scale)),Image.Resampling.LANCZOS)
    tile.alpha_composite(art,(1300+(1260-art.width)//2,max(50,H-art.height)));draw_title(tile,'Anime',title);write_tile(tile,out)
