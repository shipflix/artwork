"""Replace approved streaming tiles without regenerating any other artwork."""
import argparse,datetime as dt,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def patch_site(site,root=ROOT):
 site=Path(site);root=Path(root);manifest=json.loads((site/'manifest.json').read_text());assets=json.loads((root/'data/streaming-assets.json').read_text());rows=[r for r in manifest['tiles'] if r['category']=='Streaming Services']
 assert len(rows)==len(assets)==22
 assert {r['key'] for r in rows}==set(assets)
 replacements={}
 for r in rows:
  dest=site/r['tile'];assert dest.parent==site/'images' and dest.is_file()
  source=root/assets[r['key']]['file'];data=source.read_bytes();assert data[:4]==b'RIFF' and data[8:12]==b'WEBP'
  replacements[dest.relative_to(site).as_posix()]=source
 # Hash every other published file so wallpaper/download/gallery preservation is verified.
 protected={p.relative_to(site).as_posix():hashlib.sha256(p.read_bytes()).digest() for p in site.rglob('*') if p.is_file() and p.relative_to(site).as_posix() not in {*replacements,'manifest.json','status.json'}}
 for dest,source in replacements.items():shutil.copyfile(source,site/dest)
 for r in rows:r['tileDimensions']=[2560,1440];r['tileAsset']=assets[r['key']]
 stamp=dt.datetime.now(dt.timezone.utc).isoformat();manifest['streamingTilesUpdatedAt']=stamp
 (site/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,separators=(',',':')))
 status=json.loads((site/'status.json').read_text());status['streamingTilesUpdatedAt']=stamp;(site/'status.json').write_text(json.dumps(status,ensure_ascii=False,separators=(',',':')))
 for path,before in protected.items():assert hashlib.sha256((site/path).read_bytes()).digest()==before,path
 result={'replacedStreamingTiles':len(replacements),'preservedOtherFiles':len(protected),'streamingTilesUpdatedAt':stamp};print(json.dumps(result));return result
if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('site',type=Path);args=parser.parse_args();patch_site(args.site)
