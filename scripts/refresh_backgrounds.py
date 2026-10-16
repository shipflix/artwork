"""Refresh requested wallpaper groups, preserving every cover tile and other wallpaper."""
import concurrent.futures as cf,copy,datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.build import ROOT,Client,prepare,render_background
from PIL import Image
site=Path(sys.argv[1]);manifest=json.loads((site/'manifest.json').read_text())
catalog=json.loads((ROOT/'data/catalog.json').read_text())['folders']
groups={'Spotlight','Film Collections','Actors','Legendary Directors'}
previous={r['key']:r for r in manifest['tiles']}
recipes=[r for r in catalog if r['category'] in groups and not (r['style']=='franchise' and previous[r['key']]['backgroundStyle'].startswith('cinematic backdrop'))]
allowed={r['key']+'-background.webp' for r in recipes}
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (site/'images').iterdir() if p.name not in allowed}
client=Client()
def refresh(recipe):
 old=previous[recipe['key']]
 if recipe['style']=='franchise':r={**copy.deepcopy(recipe),'titles':old['titles'],'notes':old.get('notes',[])}
 else:r=prepare(recipe,client,None,old)
 path=site/'images'/(recipe['key']+'-background.webp')
 with cf.ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(client.image,{t['poster_path'] for t in r['titles'][:23]}))
 style=render_background(r,client,path)
 with Image.open(path) as image:image.verify()
 updated={**old,'titles':r['titles'],'notes':r['notes'],'backgroundStyle':style,'wallpaperUpdatedAt':dt.datetime.now(dt.timezone.utc).isoformat()}
 print(recipe['category']+' / '+recipe['title']+': '+style+' ('+str(len(r['titles']))+' posters)',flush=True)
 return recipe['key'],updated
with cf.ThreadPoolExecutor(max_workers=4) as pool:updated=dict(pool.map(refresh,recipes))
for p in (site/'images').iterdir():
 if p.name not in allowed:assert hashes[p.name]==hashlib.sha256(p.read_bytes()).hexdigest()
manifest['tiles']=[updated.get(r['key'],r) for r in manifest['tiles']]
manifest['categoryWallpapersUpdatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
(site/'manifest.json').write_text(json.dumps(manifest,separators=(',',':')))
print(json.dumps({'updatedWallpapers':len(updated),'preservedOtherImages':len(hashes)}))
