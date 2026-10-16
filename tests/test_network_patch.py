import importlib.util,json,tempfile,unittest
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('network_patch',ROOT/'scripts/publish_network_tiles.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class NetworkPatchTests(unittest.TestCase):
 def test_colour_logos_preserve_wallpapers_other_tiles_and_imports(self):
  keys=set(json.loads((ROOT/'data/network-colour-update.json').read_text()))
  records=[r for r in json.loads((ROOT/'data/catalog.json').read_text())['folders'] if r['key'] in keys]
  with tempfile.TemporaryDirectory() as temp:
   site=Path(temp);(site/'images').mkdir();rows=[]
   for record in records:
    row={**record,'tile':'images/'+record['key']+'.webp','wallpaper':'images/'+record['key']+'-background.webp'};rows.append(row)
    (site/row['tile']).write_bytes(b'old tile');(site/row['wallpaper']).write_bytes(b'approved wallpaper')
   (site/'images/other.webp').write_bytes(b'unrelated tile');(site/'complete.json').write_text('unchanged native sources')
   (site/'manifest.json').write_text(json.dumps({'tiles':rows,'builtAt':'original'}));(site/'status.json').write_text('{}')
   before={p.relative_to(site).as_posix():p.read_bytes() for p in site.rglob('*') if p.is_file()}
   result=module.patch_site(site);self.assertEqual(result['replacedNetworkTiles'],7)
   changed={name for name,data in before.items() if (site/name).read_bytes()!=data}
   self.assertEqual(changed,{'manifest.json','status.json',*[r['tile'] for r in rows]})
   for row in rows:
    with Image.open(site/row['tile']) as im:
     self.assertEqual(im.size,(1000,1500));self.assertTrue(all(abs(x-26)<3 for x in im.getpixel((0,0))))
     # Each reviewed variant must contain a visible coloured part of the logo.
     self.assertTrue(any(max(rgb)-min(rgb)>60 for rgb in im.resize((100,150)).get_flattened_data()))
   self.assertEqual(json.loads((site/'manifest.json').read_text())['builtAt'],'original')
