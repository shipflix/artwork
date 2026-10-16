import importlib.util,json,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('tile_patch',Path(__file__).resolve().parents[1]/'scripts/publish_streaming_tiles.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class StreamingPatchTests(unittest.TestCase):
 def test_only_22_tiles_change_and_all_wallpapers_downloads_and_urls_survive(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)/'repo';site=Path(temp)/'site';(root/'data').mkdir(parents=True);(root/'assets').mkdir();(site/'images').mkdir(parents=True);(site/'downloads').mkdir();rows=[];assets={};before={}
   for i in range(784):
    key=f'entry-{i}';row={'key':key,'category':'Streaming Services' if i<22 else 'Networks','tile':f'images/{key}.webp','wallpaper':f'images/{key}-background.webp'};rows.append(row)
    for path in [row['tile'],row['wallpaper']]:(site/path).write_bytes(b'original-'+path.encode())
    if i<22:
     path=f'assets/{key}.webp';(root/path).write_bytes(b'RIFF0000WEBPapproved'+str(i).encode());assets[key]={'file':path}
   (root/'data/streaming-assets.json').write_text(json.dumps(assets));(site/'manifest.json').write_text(json.dumps({'tiles':rows,'builtAt':'unchanged'}));(site/'status.json').write_text(json.dumps({'builtAt':'unchanged'}));(site/'downloads/complete.json').write_text('["unchanged shelves and sources"]');(site/'index.html').write_text('unchanged gallery')
   before={p.relative_to(site).as_posix():p.read_bytes() for p in site.rglob('*') if p.is_file()};result=module.patch_site(site,root);after=json.loads((site/'manifest.json').read_text());self.assertEqual(result['replacedStreamingTiles'],22);self.assertEqual(after['builtAt'],'unchanged')
   changed={path for path,data in before.items() if (site/path).read_bytes()!=data};self.assertEqual(changed,{'manifest.json','status.json',*[r['tile'] for r in rows[:22]]})
   self.assertEqual([(r['key'],r['tile'],r['wallpaper']) for r in rows],[(r['key'],r['tile'],r['wallpaper']) for r in after['tiles']])
