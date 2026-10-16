"""Publish reviewed network colour variants while preserving every other asset."""
import argparse,datetime as dt,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.artwork import centred_logo

def patch_site(site,root=ROOT):
 site=Path(site);root=Path(root)
 manifest=json.loads((site/'manifest.json').read_text())
 keys=set(json.loads((root/'data/network-colour-update.json').read_text()))
 curated=json.loads((root/'data/curated.json').read_text())['logos']
 rows=[r for r in manifest['tiles'] if r['key'] in keys]
 assert len(rows)==len(keys) and all(r['category']=='Networks' for r in rows)
 replacements={r['tile'] for r in rows}
 assert all((site/p).is_file() and (site/p).parent==site/'images' for p in replacements)
 protected={p.relative_to(site).as_posix():hashlib.sha256(p.read_bytes()).digest() for p in site.rglob('*') if p.is_file() and p.relative_to(site).as_posix() not in replacements|{'manifest.json','status.json'}}
 for row in rows:
  entry=curated['Networks / '+row['title']]
  centred_logo(entry,site/row['tile'],(1000,1500))
  row['tileDimensions']=[1000,1500];row['tileAsset']=entry
 stamp=dt.datetime.now(dt.timezone.utc).isoformat()
 manifest['networkLogosUpdatedAt']=stamp
 (site/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
 status=json.loads((site/'status.json').read_text());status['networkLogosUpdatedAt']=stamp
 (site/'status.json').write_text(json.dumps(status,ensure_ascii=False,separators=(',',':')))
 for path,before in protected.items():assert hashlib.sha256((site/path).read_bytes()).digest()==before,path
 result={'replacedNetworkTiles':len(rows),'preservedOtherFiles':len(protected),'networkLogosUpdatedAt':stamp};print(json.dumps(result));return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('site',type=Path);args=parser.parse_args();patch_site(args.site)
