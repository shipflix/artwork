"""Daily public artwork build. Publishes only after every catalogue entry validates."""
import argparse,concurrent.futures as cf,copy,datetime as dt,hashlib,json,os,shutil,sys,threading
from pathlib import Path
from PIL import Image,ImageDraw,ImageOps,ImageFilter
from . import render as base
from . import artwork as art
from .client import Client,SourceUnavailable
from .wallpaper import render_wallpaper
ROOT=base.ROOT;STATE=base.STATE
PRINT=threading.Lock()
def say(s):
 with PRINT:print(s,flush=True)
def load(path,default=None):return json.loads(path.read_text()) if path.exists() else default

def assign_stacks(records):
 """Exact maximum matching prevents repeats of title or artwork across every stack."""
 from collections import deque
 exclusions=load(ROOT/'data/stack-exclusions.json',{})
 rows=[{**r,'titles':[t for t in r['titles'] if t['poster_path'] not in exclusions.get(r['key'],[])]} for r in records if r['style']=='stack'];unique={}
 for r in rows:
  for t in r['titles']:unique.setdefault((t['type'],t['id']),t)
 bypath={};resource={key:bypath.setdefault(t['poster_path'],len(bypath)) for key,t in unique.items()};slots=[(r,pos) for pos in range(3) for r in rows];n=len(slots);m=len(bypath);sink=1+n+m;graph=[[] for _ in range(sink+1)]
 def edge(a,b,cap,cost):graph[a].append([b,len(graph[b]),cap,cost]);graph[b].append([a,len(graph[a])-1,0,-cost])
 for i,(r,pos) in enumerate(slots):
  edge(0,1+i,1,0)
  for rank,t in enumerate(r['titles']):edge(1+i,1+n+resource[(t['type'],t['id'])],1,rank*(8 if pos==0 else 1)+pos)
 for j in range(m):edge(1+n+j,sink,1,0)
 for _ in slots:
  dist=[10**12]*len(graph);dist[0]=0;prev=[None]*len(graph);q=deque([0]);inside={0}
  while q:
   u=q.popleft();inside.remove(u)
   for k,e in enumerate(graph[u]):
    v,rev,cap,cost=e
    if cap and dist[u]+cost<dist[v]:
     dist[v]=dist[u]+cost;prev[v]=(u,k)
     if v not in inside:q.append(v);inside.add(v)
  if prev[sink] is None:raise RuntimeError('Insufficient distinct category posters; publication stopped rather than repeating stacks.')
  v=sink
  while v:
   u,k=prev[v];e=graph[u][k];e[2]-=1;graph[v][e[1]][2]+=1;v=u
 chosen={r['key']:[None]*3 for r in rows}
 for i,(r,pos) in enumerate(slots):
  target=next(e[0]-1-n for e in graph[1+i] if 1+n<=e[0]<sink and e[2]==0);chosen[r['key']][pos]=next(t for t in r['titles'] if resource[(t['type'],t['id'])]==target)
 values=[t for ts in chosen.values() for t in ts];assert len(values)==len({(t['type'],t['id']) for t in values})==len({t['poster_path'] for t in values});return chosen

def safe_catalog(catalog):
 """Publishing is allowlisted: no media-server, add-on, token or private account data."""
 allowed={'tmdbDiscover','tmdbCollection','tmdbList','traktList'}
 for r in catalog:
  assert r.get('native',{}).get('tileShape','wide') in {'wide','poster','square'}, 'Invalid Strand tile shape'
  assert r['key'] and '/' not in r['key'] and '..' not in r['key']
  for s in r['sources']:
   assert len(s)==1 and next(iter(s)) in allowed
   text=json.dumps(s).lower()
   assert not any(v in text for v in ['authorization','api_key','password','access_token','mediaserver','addonid','catalogid','127.0.0.1','localhost','jellyfin','emby'])
   for kind in ('tmdbList','tmdbCollection'):
    if kind in s:assert s[kind]['_0'].get('sortBy','original') in {'original','rating','release_date'}, 'Invalid Strand list sort order'
   if 'tmdbDiscover' in s:assert s['tmdbDiscover']['_0'].get('sortBy')!='original', 'Discover sources need an API sort order'
   if 'traktList' in s:assert s['traktList']['_0']['isPublic'] is True and not s['traktList']['_0']['username']

def fade_background(image,out):
 """Sparse collections use a real film backdrop, never repeated poster padding."""
 wall=ImageOps.fit(image.convert('RGB'),(2560,1440),Image.Resampling.LANCZOS);fade=Image.new('L',(640,360));blur=Image.new('L',(640,360));fp=fade.load();bp=blur.load()
 for y in range(360):
  yy=y/359
  for x in range(640):
   xx=x/639;dark=min(1,.12+.68*(1-xx)**1.6+.76*yy**1.8*(1-.85*xx));corner=art.smooth(1-(((1-xx)/.34)**2+(yy/.40)**2)**.5);baseblur=.8*art.smooth((dark-.22)/.65);dark=1-(1-dark)*(1-.48*corner);fp[x,y]=round(255*dark);bp[x,y]=round(255*(1-(1-baseblur)*(1-.60*corner)))
 wall=Image.composite(wall.filter(ImageFilter.GaussianBlur(16)),wall,blur.resize(wall.size,Image.Resampling.BICUBIC));wall=Image.composite(Image.new('RGB',wall.size,'black'),wall,fade.resize(wall.size,Image.Resampling.BICUBIC));art.write_tile(wall,out)

def photographic_tile(title,image,out):
 tile=Image.new('RGBA',(2560,1440),art.CHARCOAL);photo=ImageOps.fit(image.convert('RGB'),(1410,1440),Image.Resampling.LANCZOS);mask=Image.new('L',(353,360));p=mask.load()
 for y in range(360):
  for x in range(353):p[x,y]=round(255*art.smooth(x/100)*(.94-.20*(y/359)**2))
 tile.paste(photo,(1150,0),mask.resize(photo.size,Image.Resampling.BICUBIC));art.draw_title(tile,'Based on',title);art.write_tile(tile,out)

def prepare(recipe,client,seed,previous):
 data=copy.deepcopy(recipe);data['notes']=[]
 try:items,notes=client.folder(recipe,seed);data.update(titles=items,notes=notes)
 except SourceUnavailable:
  if previous:data.update(titles=previous['titles'],notes=['Source unavailable; last successful title selection retained.'])
  else:raise
 # Small or strongly overlapping spotlight lists use a single scene instead of reusing stacks.
 if data['style']=='stack' and len(data['titles'])<3:data['style']='franchise'
 return data

def copy_streaming_tile(recipe,out):
 """Use the approved bundled tiles at stable published paths."""
 assets=load(ROOT/'data/streaming-assets.json',{})
 entry=assets.get(recipe['key'])
 source=ROOT/entry['file'] if entry else ROOT/'assets/streaming'/(recipe['key']+Path(recipe['originalCoverURL']).suffix)
 if source.suffix=='.webp':shutil.copy2(source,out)
 else:
  with Image.open(source) as image:image.convert('RGB').save(out,'WEBP',quality=94)

def background_uses_grid(recipe):
 return len(recipe['titles'])>=23 and not (recipe['category']=='Film Collections' and recipe['style']=='franchise')

def render_background(recipe,client,out,hero=None):
 if background_uses_grid(recipe):
  titles=recipe['titles'][:23]
  assert len({t['poster_path'] for t in titles})==23
  posters=[client.image(t['poster_path']).convert('RGB') for t in titles]
  layout=render_wallpaper(posters,out)
  assert len({i['posterIndex'] for i in layout})==len(layout)
  return 'poster-columns-v9'
 if hero is None or recipe['style']=='person':
  try:hero=client.backdrop(recipe['titles'][0])
  except SourceUnavailable:hero=client.image(recipe['titles'][0]['poster_path'],'original')
 fade_background(hero,out)
 return 'cinematic backdrop (franchise)' if recipe['category']=='Film Collections' and recipe['style']=='franchise' else 'cinematic backdrop (small source selection)'

def render_record(r,client,chosen,curated,site,previous_site):
 images=site/'images';images.mkdir(exist_ok=True);tile=images/(r['key']+'.webp');wall=images/(r['key']+'-background.webp');group,title=r['category'],r['title'];entry={};hero=None
 try:
  required={t['poster_path'] for t in r['titles'][:23]+chosen.get(r['key'],[])}
  with cf.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(client.image,required))
  if r['style']=='stack':art.stack_tile(group,title,chosen[r['key']],tile)
  elif group=='Anime':entry=curated['characters'][title];art.anime_tile(title,entry,tile)
  elif group=='Moods & Vibes':entry=curated['moods'][title];art.mood_tile(title,entry,tile)
  elif group=='Based on':entry=curated['basedOn'][title];art.mood_tile(title,entry,tile)
  elif group=='Streaming Services':
   copy_streaming_tile(r,tile)
  elif r['style']=='logo':
   entry=curated['logos'][group+' / '+title];art.centred_logo(entry,tile,(1000,1500) if group=='Networks' else (2560,1440),False)
  elif r['style']=='person':
   hero=client.person(title);photographic_tile(title,hero,tile)
  else:
   try:hero=client.backdrop(r['titles'][0])
   except SourceUnavailable:hero=client.image(r['titles'][0]['poster_path'],'original')
   label=title if title in art.TITLE_OVERRIDES else title.removesuffix(' Collection').removesuffix(' collection')
   photographic_tile(label,hero,tile)
  background_style=render_background(r,client,wall,hero)
  for path in [tile,wall]:
   with Image.open(path) as im:im.verify()
 except Exception:
  # No blank or broken replacement: preserve both last-good images together.
  for path in [tile,wall]:
   old=previous_site/'images'/path.name
   if not old.exists():raise
   shutil.copy2(old,path)
  r['notes'].append('Rendering or image fetch failed; both last-good images retained.');background_style='retained last-good artwork'
 with Image.open(tile) as im:dimensions=list(im.size)
 result={'id':r['id'],'key':r['key'],'title':title,'category':group,'recommended':r['recommended'],'style':r['style'],'tile':'images/'+tile.name,'wallpaper':'images/'+wall.name,'tileDimensions':dimensions,'backgroundStyle':background_style,'tileTitles':chosen.get(r['key'],[]),'titles':r['titles'],'tileAsset':entry,'notes':r['notes'],'builtAt':dt.datetime.now(dt.timezone.utc).isoformat()}
 say('Rendered '+group+' / '+title);return result

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--output',default='_site');parser.add_argument('--base-url',default=os.environ.get('ARTWORK_BASE_URL',''));parser.add_argument('--only',help='Comma-separated folder keys, for a smoke build');parser.add_argument('--workers',type=int,default=4);parser.add_argument('--plan-only',action='store_true');parser.add_argument('--catalogue-only',action='store_true');args=parser.parse_args();catalog=load(ROOT/'data/catalog.json')['folders'];safe_catalog(catalog)
 if not args.base_url:parser.error('--base-url is required; it is the permanent public Pages address')
 if not args.base_url.startswith('https://'):parser.error('Public artwork requires an HTTPS base URL')
 client=Client();curated=load(ROOT/'data/curated.json');seed=load(ROOT/'data/seed.json',{});oldmeta=load(STATE/'last-manifest.json',{'tiles':[]});previous={r['key']:r for r in oldmeta['tiles']};previous_site=STATE/'last-site';target=Path(args.output);stage=target.with_name(target.name+'-staging');shutil.rmtree(stage,ignore_errors=True);stage.mkdir(parents=True)
 selected=catalog
 if args.only:
  keys=set(args.only.split(','));selected=[r for r in catalog if r['key'] in keys];assert len(selected)==len(keys)
 if args.catalogue_only:
  from .site import write_site
  manifest={'tiles':[], 'builtAt':dt.datetime.now(dt.timezone.utc).isoformat(),'preview':True};write_site(stage,catalog,manifest,args.base_url,selected);shutil.rmtree(target,ignore_errors=True);stage.replace(target);return
 prepared=[]
 with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
  tasks={pool.submit(prepare,r,client,seed.get(r['key']),previous.get(r['key'])):r for r in selected}
  for f in cf.as_completed(tasks):
   r=f.result();prepared.append(r);say('Selected '+r['category']+' / '+r['title']+' ('+str(len(r['titles']))+' candidates)')
 say('Assigning distinct posters across all stacks');chosen=assign_stacks(prepared);done=[]
 if args.plan_only:
  STATE.mkdir(exist_ok=True,parents=True);(STATE/'render-plan.json').write_text(json.dumps({'recipes':prepared,'stacks':chosen},ensure_ascii=False,indent=2));say('Plan validated: '+str(len(prepared))+' folders');return
 with cf.ThreadPoolExecutor(max_workers=args.workers) as pool:
  tasks=[pool.submit(render_record,r,client,chosen,curated,stage,previous_site) for r in prepared]
  for f in cf.as_completed(tasks):done.append(f.result())
 order={r['key']:i for i,r in enumerate(catalog)};done.sort(key=lambda r:order[r['key']]);manifest={'builtAt':dt.datetime.now(dt.timezone.utc).isoformat(),'tiles':done,'partialSmokeBuild':bool(args.only),'globallyDistinctStackPosters':sum(len(v) for v in chosen.values()),'notes':sorted({n for r in done for n in r['notes']})}
 from .site import write_site
 write_site(stage,catalog,manifest,args.base_url,selected)
 assert all((stage/r[k]).is_file() for r in done for k in ['tile','wallpaper'])
 size=sum(p.stat().st_size for p in stage.rglob('*') if p.is_file());assert size<900*1024*1024,'Site would approach GitHub Pages 1 GB published-site limit'
 # Only a completed, validated generation replaces the published bundle.
 shutil.rmtree(target,ignore_errors=True);stage.replace(target)
 if not args.only:
  shutil.rmtree(previous_site,ignore_errors=True);shutil.copytree(target,previous_site);STATE.mkdir(exist_ok=True,parents=True);(STATE/'last-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2))
 say('Complete: '+str(len(done))+' folders, '+str(round(size/1024/1024,1))+' MB. '+str(len(manifest['notes']))+' source notices.')
if __name__=='__main__':main()
