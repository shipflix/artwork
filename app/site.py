"""Static preview gallery and clean Strand import downloads. No accounts or tracking."""
import copy,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent

def write_site(site,catalog,manifest,base_url,selected):
 base_url=base_url.rstrip('/');keys={r['key'] for r in selected};template=json.loads((ROOT/'data/strand-template.json').read_text());idkeys={r['id']:r['key'] for r in catalog};downloads=site/'downloads';downloads.mkdir(exist_ok=True)
 def materialize(shelves,allowed=None):
  result=[]
  for shelf in copy.deepcopy(shelves):
   folders=shelf['source']['group']['_0']['contentSources'];folders[:]=[f for f in folders if idkeys[f['id']] in keys and (allowed is None or idkeys[f['id']] in allowed)]
   for f in folders:
    for key in ['coverImageURL','backgroundImageURL']:f[key]=f[key].replace('__BASE_URL__',base_url)
   if folders:shelf['sortOrder']=len(result);result.append(shelf)
  return result
 full=materialize(template);recommended=materialize(template,{r['key'] for r in catalog if r['recommended']});compact=lambda v:json.dumps(v,ensure_ascii=False,separators=(',',':'))
 (downloads/'complete.json').write_text(compact(full));(downloads/'recommended.json').write_text(compact(recommended))
 for shelf in full:
  key=next(r['key'].split('--')[0] for r in catalog if r['category']==shelf['title']);(downloads/(key+'.json')).write_text(compact([shelf]))
 # Releasable public catalogue; never expose personal exports or API credentials.
 (site/'manifest.json').write_text(compact(manifest));(site/'catalogue.json').write_text(compact([{'id':r['id'],'key':r['key'],'title':r['title'],'category':r['category'],'style':r['style'],'recommended':r['recommended']} for r in selected]));(site/'status.json').write_text(compact({k:v for k,v in manifest.items() if k!='tiles'}))
 notes='''Shipflix — independent artwork remix for Kaptain (https://kaptain.stream/)-style collections in Strand.
Shipflix provides artwork and browsing shelves only. It does not host or supply movies, TV episodes or playback streams. Use your own media and services you are authorised to access.
Import only the categories you want. Back up Settings > Shelves > Copy to Clipboard first.
Use Append to add rows; Overwrite replaces all existing shelves. Do not overwrite without a backup.
The complete default collection has 784 folders. Large imports may exceed Strand's iCloud storage allowance alongside other app data; recommended and individual-category downloads are provided.
For You uses generic public picks. Your own recommendations and server settings are never distributed.
Artwork publishing is scheduled daily. The artwork URLs stay the same. A client may continue showing cached images until it revalidates them; same-URL updates were confirmed in Strand on the creator's Apple TV on 16 October 2026. Exact refresh timing and other devices remain unmeasured.
A daily build does not necessarily change every image: logos, character art and curated scene tiles are deliberately fixed; failed upstream lookups retain last-good artwork and appear in status.json.
Films, artwork, logos and trademarks belong to their respective owners. Metadata and film images: TMDB. This product uses the TMDB API but is not endorsed or certified by TMDB. Original category organisation: Kaptain (https://kaptain.stream/). This is an independent project, not an official Kaptain (https://kaptain.stream/) or Strand release.
'''
 (downloads/'READ-ME-FIRST.txt').write_text(notes)
 shutil.copyfile(ROOT/'assets/tmdb-logo.svg',site/'tmdb-logo.svg')
 page=(ROOT/'static/index.html').read_text();(site/'index.html').write_text(page)
