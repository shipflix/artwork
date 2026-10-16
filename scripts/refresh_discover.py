"""Refresh two approved Discover artworks while preserving all other images."""
import datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.build import Client,assign_stacks,prepare,render_record,ROOT
site=Path(sys.argv[1]);manifest=json.loads((site/'manifest.json').read_text())
catalog=json.loads((ROOT/'data/catalog.json').read_text())['folders'];curated=json.loads((ROOT/'data/curated.json').read_text())
keys={'discover--top-series','discover--top-movies'}
previous={r['key']:r for r in manifest['tiles']}
used_ids={(t['type'],t['id']) for r in manifest['tiles'] for t in r.get('tileTitles',[])}
used_paths={t['poster_path'] for r in manifest['tiles'] for t in r.get('tileTitles',[])}
for key in keys:
 old=previous[key]
 for t in old.get('tileTitles') or old.get('titles',[])[:1]:
  used_ids.add((t['type'],t['id']));used_paths.add(t['poster_path'])
client=Client();records=[];available=[]
for recipe in catalog:
 if recipe['key'] not in keys:continue
 r=prepare(recipe,client,None,previous[recipe['key']]);pool=list(r['titles'])
 typ='tv' if recipe['title']=='Top Series' else 'movie'
 def eligible():return [t for t in pool if (t['type'],t['id']) not in used_ids and t['poster_path'] not in used_paths]
 for page in range(4,11):
  if len(eligible())>=3:break
  additions=client.released(client.api(typ+'/top_rated',{'language':'en-US','page':page}).get('results',[]),typ)
  paths={t['poster_path'] for t in pool};pool.extend(t for t in additions if t['poster_path'] not in paths)
 assert len(eligible())>=3,'No distinct replacement stack available'
 records.append(r);available.append({**r,'titles':eligible()})
chosen=assign_stacks(available)
allowed={key+suffix+'.webp' for key in keys for suffix in ('','-background')}
hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (site/'images').iterdir() if p.name not in allowed}
updated={r['key']:render_record(r,client,chosen,curated,site,Path('/nonexistent-last-site')) for r in records}
assert all(r['backgroundStyle']=='poster-columns-v9' for r in updated.values())
for p in (site/'images').iterdir():
 if p.name not in allowed:assert hashes[p.name]==hashlib.sha256(p.read_bytes()).hexdigest()
manifest['tiles']=[updated.get(r['key'],r) for r in manifest['tiles']]
manifest['discoverArtworkUpdatedAt']=dt.datetime.now(dt.timezone.utc).isoformat()
(site/'manifest.json').write_text(json.dumps(manifest,separators=(',',':')))
print(json.dumps({'updated':{k:[t['title'] for t in v['tileTitles']] for k,v in updated.items()},'preservedOtherImages':len(hashes)}))
