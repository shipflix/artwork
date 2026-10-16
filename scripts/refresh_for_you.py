"""Replace the rejected For You poster without changing other artwork."""
import datetime as dt,hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.build import Client,ROOT,load
from app.artwork import stack_tile
site=Path(sys.argv[1]);manifest=load(site/'manifest.json');record=next(r for r in manifest['tiles'] if r['key']=='discover--for-you')
blocked=set(load(ROOT/'data/stack-exclusions.json',{}).get(record['key'],[]));chosen=list(record['tileTitles'])
used_ids={(t['type'],t['id']) for r in manifest['tiles'] for t in r.get('tileTitles',[])}
used_paths={t['poster_path'] for r in manifest['tiles'] for t in r.get('tileTitles',[])}
client=Client();replacements=[]
for i,t in enumerate(chosen):
 if t['poster_path'] not in blocked:continue
 candidates=[v for v in record['titles'] if (v['type'],v['id']) not in used_ids and v['poster_path'] not in used_paths|blocked]
 replacement=next((v for v in candidates if v['type']=='tv' and v['id']==97546),None)
 if replacement is None:replacement=next(iter(candidates),None)
 assert replacement,'No unique replacement poster available'
 chosen[i]=replacement;used_ids.add((replacement['type'],replacement['id']));used_paths.add(replacement['poster_path']);replacements.append({'removed':t['title'],'added':replacement['title']})
assert replacements,'Rejected poster is not present; no publication needed'
protected={p.relative_to(site).as_posix():hashlib.sha256(p.read_bytes()).digest() for p in site.rglob('*') if p.is_file() and p.relative_to(site).as_posix() not in {record['tile'],'manifest.json','status.json'}}
for t in chosen:client.image(t['poster_path'])
stack_tile(record['category'],record['title'],chosen,site/record['tile'])
record['tileTitles']=chosen;stamp=dt.datetime.now(dt.timezone.utc).isoformat();manifest['forYouTileUpdatedAt']=stamp
(site/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
status=load(site/'status.json');status['forYouTileUpdatedAt']=stamp;(site/'status.json').write_text(json.dumps(status,ensure_ascii=False,separators=(',',':')))
for path,before in protected.items():assert hashlib.sha256((site/path).read_bytes()).digest()==before,path
print(json.dumps({'replacements':replacements,'preservedOtherFiles':len(protected)}))
