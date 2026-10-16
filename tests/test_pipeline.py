import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from app import build
from app.client import Client,SourceUnavailable
from app.site import write_site
ROOT=Path(__file__).resolve().parents[1]
class PipelineTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.catalog=json.loads((ROOT/'data/catalog.json').read_text())['folders']
 def test_complete_catalogue_is_public_and_has_no_personal_sources(self):
  self.assertEqual(len(self.catalog),784);self.assertEqual(len({r['id'] for r in self.catalog}),784);self.assertEqual(len({r['key'] for r in self.catalog}),784);build.safe_catalog(self.catalog);self.assertEqual(sum(r['recommended'] for r in self.catalog),223)
  for r in self.catalog:
   for s in r['sources']:self.assertNotIn('mediaServer',s);self.assertNotIn('addon',s)
 def test_streaming_and_network_categories_cover_full_upstream_pack(self):
  coverage=json.loads((ROOT/'data/upstream-coverage.json').read_text())['categories'];curated=json.loads((ROOT/'data/curated.json').read_text())
  for group,names in coverage.items():
   rows=[r for r in self.catalog if r['category']==group]
   self.assertEqual({r['title'] for r in rows},set(names))
   for r in rows:
    self.assertTrue(r['sources']);self.assertEqual(r['native']['sources'],r['sources'])
    if group=='Networks':
     self.assertEqual(r['native']['tileShape'],'poster')
     self.assertTrue((ROOT/curated['logos'][group+' / '+r['title']]['file']).is_file())
  template=json.loads((ROOT/'data/strand-template.json').read_text())
  for group,names in coverage.items():
   shelf=next(s for s in template if s['title']==group)
   self.assertEqual({f['title'] for f in shelf['source']['group']['_0']['contentSources']},set(names))
 def test_sensitive_source_rejected(self):
  r=copy.deepcopy(self.catalog[0]);r['sources']=[{'mediaServer':{'_0':{'token':'secret'}}}]
  with self.assertRaises(AssertionError):build.safe_catalog([r])
 def test_person_tile_does_not_use_the_portrait_as_its_movie_wallpaper(self):
  from PIL import Image
  class ArtworkClient:
   def image(self,*args):return Image.new('RGB',(100,150),'green')
   def person(self,*args):return Image.new('RGB',(100,150),'blue')
   def backdrop(self,*args):return Image.new('RGB',(160,90),'red')
  row={'id':'test','key':'test-person','category':'Actors','title':'Example Actor','style':'person','recommended':False,'notes':[],'titles':[{'poster_path':'/test.jpg','id':1,'type':'movie','title':'Example Movie'}]}
  with tempfile.TemporaryDirectory() as tmp:
   site=Path(tmp);result=build.render_record(row,ArtworkClient(),{}, {},site,site/'previous')
   with Image.open(site/result['wallpaper']) as image:
    red,green,blue=image.convert('RGB').getpixel((2000,400));self.assertGreater(red,blue+50)
 def test_all_streaming_tiles_are_bundled_and_copy_without_network_access(self):
  from PIL import Image
  rows=[r for r in self.catalog if r['category']=='Streaming Services']
  self.assertEqual(len(rows),22)
  with tempfile.TemporaryDirectory() as tmp:
   for r in rows:
    out=Path(tmp)/(r['key']+'.webp')
    with patch.object(Client,'image',side_effect=AssertionError('Network access is forbidden')):build.copy_streaming_tile(r,out)
    with Image.open(out) as image:image.verify()
    source=ROOT/'assets/streaming'/(r['key']+Path(r['originalCoverURL']).suffix)
    if source.suffix=='.webp':self.assertEqual(source.read_bytes(),out.read_bytes())
 def test_api_cache_refreshes_on_new_day_but_images_can_remain_cached(self):
  with tempfile.TemporaryDirectory() as tmp:
   cache=Path(tmp);calls=[]
   def download(self,url,path=None,headers=None):
    calls.append(url);path.write_text(json.dumps({'day':str(self.today)}));return path.read_bytes()
   with patch.object(Client,'download',download):
    first=Client(token='test',today=dt.date(2026,10,16),cache=cache);second=Client(token='test',today=dt.date(2026,10,17),cache=cache)
    self.assertEqual(first.api('trending/movie/week'),first.api('trending/movie/week'));self.assertNotEqual(first.api('trending/movie/week'),second.api('trending/movie/week'));self.assertEqual(len(calls),2)
 def test_unreleased_and_repeated_images_are_excluded(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Client(token='test',today=dt.date(2026,10,16),cache=Path(tmp));items=[{'id':1,'title':'Released','poster_path':'/a.jpg','release_date':'2026-10-15'},{'id':2,'title':'Duplicate image','poster_path':'/a.jpg','release_date':'2026-10-14'},{'id':3,'title':'Future','poster_path':'/b.jpg','release_date':'2026-10-17'}];self.assertEqual([r['id'] for r in c.released(items)],[1])
 def test_stack_assignment_is_globally_unique_even_with_overlapping_pools(self):
  def t(i,path=None):return {'id':i,'type':'movie','poster_path':path or f'/{i}.jpg'}
  records=[{'key':'a','style':'stack','titles':[t(1),t(2),t(3),t(4)]},{'key':'b','style':'stack','titles':[t(1),t(5),t(6),t(7,'/2.jpg')]}];result=build.assign_stacks(records);all=[t for values in result.values() for t in values];self.assertEqual(len(all),6);self.assertEqual(len({t['id'] for t in all}),6);self.assertEqual(len({t['poster_path'] for t in all}),6)
 def test_insufficient_unique_posters_stops_instead_of_repeating(self):
  with self.assertRaises(RuntimeError):build.assign_stacks([{'key':'a','style':'stack','titles':[{'id':1,'type':'movie','poster_path':'/1.jpg'}]}])
 def test_import_urls_are_stable_and_recommended_pack_has_223_folders(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);write_site(out,self.catalog,{'tiles':[],'builtAt':'test','preview':True},'https://example.test/artwork',self.catalog)
   full=json.loads((out/'downloads/complete.json').read_text());small=json.loads((out/'downloads/recommended.json').read_text());folders=[f for s in full for f in s['source']['group']['_0']['contentSources']];self.assertEqual(len(folders),784);self.assertEqual(sum(len(s['source']['group']['_0']['contentSources']) for s in small),223)
   for f in folders:
    self.assertTrue(f['coverImageURL'].startswith('https://example.test/artwork/images/'));self.assertNotIn('?',f['coverImageURL']);self.assertNotIn('__BASE_URL__',f['backgroundImageURL'])
 def test_failed_initial_build_does_not_replace_previous_output(self):
  class FailingClient:
   def folder(self,*args,**kwargs):raise SourceUnavailable('offline')
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);output=root/'site';output.mkdir();(output/'sentinel.txt').write_text('last good build');key=self.catalog[0]['key']
   with patch.object(build,'Client',FailingClient),patch.object(build,'STATE',root/'state'),patch('sys.argv',['build','--output',str(output),'--base-url','https://example.test/artwork','--only',key]):
    with self.assertRaises(SourceUnavailable):build.main()
   self.assertEqual((output/'sentinel.txt').read_text(),'last good build')
if __name__=='__main__':unittest.main()
