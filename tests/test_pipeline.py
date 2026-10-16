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
  self.assertEqual(len(self.catalog),784);self.assertEqual(len({r['id'] for r in self.catalog}),784);self.assertEqual(len({r['key'] for r in self.catalog}),784);build.safe_catalog(self.catalog);self.assertEqual(sum(r['recommended'] for r in self.catalog),163)
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
 def test_hallmark_mystery_uses_its_film_collections_not_hallmark_channel(self):
  r=next(r for r in self.catalog if r['category']=='Networks' and r['title']=='Hallmark Mystery')
  self.assertEqual(len(r['sources']),6)
  self.assertTrue(all('tmdbCollection' in s for s in r['sources']))
 def test_list_api_sort_order_is_rejected_before_publishing(self):
  r=copy.deepcopy(next(r for r in self.catalog if r['category']=='Spotlight'))
  self.assertEqual(r['sources'][0]['tmdbList']['_0']['sortBy'],'rating')
  r['sources'][0]['tmdbList']['_0']['sortBy']='vote_average.desc'
  with self.assertRaisesRegex(AssertionError,'Invalid Strand list sort order'):build.safe_catalog([r])
 def test_international_imports_show_each_source_as_a_row(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);write_site(out,self.catalog,{'tiles':[]},'https://example.test/artwork',self.catalog)
   exports=[json.loads((out/'downloads/complete.json').read_text()),json.loads((out/'downloads/international-cinema.json').read_text())]
   for exported in exports:
    row=next(s for s in exported if s['title']=='International Cinema')
    folders=row['source']['group']['_0']['contentSources'];self.assertEqual(len(folders),65)
    for f in folders:
     self.assertIs(f['showsSourceRows'],True)
     original=next(r for r in self.catalog if r['id']==f['id']);self.assertEqual(f['sources'],original['sources']);self.assertIs(original['native']['showsSourceRows'],True)
 def test_streaming_imports_use_wide_tiles(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);write_site(out,self.catalog,{'tiles':[]},'https://example.test/artwork',self.catalog)
   for filename in ('complete.json','recommended.json','streaming-services.json'):
    rows=json.loads((out/'downloads'/filename).read_text());group=next(s for s in rows if s['title']=='Streaming Services')['source']['group']['_0']
    self.assertEqual(group['tileShape'],'wide');self.assertEqual(len(group['contentSources']),22)
    for folder in group['contentSources']:
     self.assertEqual(folder['tileShape'],'wide');self.assertIs(folder['showsSourceRows'],True)
   for record in self.catalog:
    if record['category']=='Streaming Services':self.assertEqual(record['native']['tileShape'],'wide')
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
    source=ROOT/json.loads((ROOT/'data/streaming-assets.json').read_text())[r['key']]['file']
    if source.suffix=='.webp':self.assertEqual(source.read_bytes(),out.read_bytes())
 def test_top_discovery_artwork_has_enough_posters_for_grid(self):
  with tempfile.TemporaryDirectory() as tmp:
   c=Client(token='test',today=dt.date(2026,10,16),cache=Path(tmp))
   def api(endpoint,params):
    return {'results':[{'id':params['page']*100+i,'name':'Series','title':'Movie','poster_path':f"/{params['page']}-{i}.jpg",'release_date':'2020-01-01','first_air_date':'2020-01-01'} for i in range(20)]}
   with patch.object(c,'api',side_effect=api),patch.object(c,'source',side_effect=AssertionError('Sparse provider lists must not control top-rated artwork')):
    for title in ('Top Series','Top Movies'):
     items,_=c.folder({'category':'Discover','title':title,'sources':[]})
     self.assertEqual(len(items),60);self.assertEqual(len({t['poster_path'] for t in items}),60)
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
 def test_import_urls_are_stable_and_recommended_pack_has_163_folders(self):
  with tempfile.TemporaryDirectory() as tmp:
   out=Path(tmp);write_site(out,self.catalog,{'tiles':[],'builtAt':'test','preview':True},'https://example.test/artwork',self.catalog)
   full=json.loads((out/'downloads/complete.json').read_text());small=json.loads((out/'downloads/recommended.json').read_text());folders=[f for s in full for f in s['source']['group']['_0']['contentSources']];self.assertEqual(len(folders),784);self.assertEqual(sum(len(s['source']['group']['_0']['contentSources']) for s in small),163)
   for f in folders:
    self.assertIn(f['tileShape'],{'wide','poster','square'});self.assertIs(f['showsSourceRows'],True)
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
