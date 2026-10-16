"""TMDB/public Trakt artwork lookup with daily JSON cache and persistent image cache."""
import datetime as dt,hashlib,json,os,time,urllib.request,urllib.parse,urllib.error,threading
from pathlib import Path
from PIL import Image
from . import render as base
class SourceUnavailable(RuntimeError):pass
class Client:
 def __init__(self,token=None,today=None,cache=None):
  self.token=token if token is not None else os.environ.get('TMDB_READ_TOKEN','')
  tokenfile=os.environ.get('TMDB_TOKEN_FILE')
  if not self.token and tokenfile:self.token=Path(tokenfile).read_text().strip()
  self.today=today or dt.datetime.now(dt.timezone.utc).date();self.cache=Path(cache or base.CACHE);self.gate=threading.Semaphore(6)
  for p in [self.cache/'api',self.cache/'images']:p.mkdir(parents=True,exist_ok=True)
 def download(self,url,path=None,headers=None):
  if path and path.exists():return path.read_bytes()
  for attempt in range(4):
   try:
    req=urllib.request.Request(url,headers={'User-Agent':'StrandArtwork/1.0',**(headers or {})})
    with self.gate,urllib.request.urlopen(req,timeout=35) as res:data=res.read()
    if path:
     temporary=path.with_name(path.name+'.'+str(threading.get_ident())+'.tmp');temporary.write_bytes(data);temporary.replace(path)
    return data
   except Exception as exc:
    if isinstance(exc,urllib.error.HTTPError) and exc.code in [400,401,403,404]:raise SourceUnavailable('Remote source refused the lookup') from exc
    if attempt==3:raise SourceUnavailable('Remote artwork source unavailable') from exc
    time.sleep(min(8,2**attempt))
 def api(self,endpoint,params=None):
  params={k:v for k,v in (params or {}).items() if v is not None and v!=''};url='https://api.themoviedb.org/3/'+endpoint+'?'+urllib.parse.urlencode(params)
  # Date is part of the JSON cache key. Yesterday's responses cannot freeze today's build.
  key=base.digest(str(self.today)+'|'+url);path=self.cache/'api'/(key+'.json')
  if path.exists():return json.loads(path.read_text())
  if not self.token:raise SourceUnavailable('TMDB read token is required')
  return json.loads(self.download(url,path,{'Authorization':'Bearer '+self.token}))
 def image(self,path,size='w500'):
  url=path if path.startswith('https://') else 'https://image.tmdb.org/t/p/'+size+path
  # Source assets must be public HTTPS URLs on known artwork hosts.
  host=urllib.parse.urlparse(url).hostname or ''
  if host not in ['image.tmdb.org','art.kaptain.stream','raw.githubusercontent.com','upload.wikimedia.org','thumb.wikimedia.org']:raise SourceUnavailable('Unsupported image host')
  p=self.cache/'images'/base.digest(url);self.download(url,p)
  try:
   with Image.open(p) as im:return im.convert('RGBA')
  except Exception as exc:raise SourceUnavailable('Invalid artwork image') from exc
 def released(self,items,default='movie'):
  result=[];seen=set();images=set()
  for v in items:
   typ=v.get('media_type') or ('tv' if v.get('first_air_date') else default);day=v.get('release_date') or v.get('first_air_date') or v.get('date') or '';image=v.get('poster_path');key=(typ,v.get('id'))
   if not image or not day or day>str(self.today) or v.get('adult') or key in seen or image in images:continue
   seen.add(key);images.add(image);result.append({'id':v['id'],'type':typ,'title':v.get('title') or v.get('name'),'date':day,'poster_path':image,'popularity':v.get('popularity',0),'backdrop_path':v.get('backdrop_path')})
  return result
 def discover(self,value,page=1,popular=False):
  typ=value.get('mediaType','movie');typ='tv' if typ=='tv' else 'movie';sort=value.get('sortBy','popularity.desc')
  if sort=='original':sort='popularity.desc'
  if popular:sort='popularity.desc'
  if typ=='tv':sort=sort.replace('primary_release_date','first_air_date')
  p={'language':'en-US','include_adult':'false','sort_by':sort,'page':page}
  maps={'genres':'with_genres','excludeGenres':'without_genres','keywords':'with_keywords','excludeKeywords':'without_keywords','companies':'with_companies','networks':'with_networks','watchProviders':'with_watch_providers','watchRegion':'watch_region','originalLanguage':'with_original_language','originCountry':'with_origin_country','voteCountGte':'vote_count.gte','voteAverageGte':'vote_average.gte','cast':'with_cast','crew':'with_crew'}
  for key,dest in maps.items():
   v=value.get(key)
   if v not in [None,'',[]]:p[dest]='|'.join(map(str,v)) if isinstance(v,list) else v
  datekey='first_air_date' if typ=='tv' else 'primary_release_date';p[datekey+'.lte']=str(self.today)
  for key,dest in [('releaseDateGte',datekey+'.gte'),('releaseDateLte',datekey+'.lte'),('year','first_air_date_year' if typ=='tv' else 'primary_release_year')]:
   if value.get(key):p[dest]=min(value[key],str(self.today)) if key=='releaseDateLte' else value[key]
  return self.released(self.api('discover/'+typ,p).get('results',[]),typ)
 def source(self,source,page=1,popular=False):
  kind=next(iter(source));v=source[kind]['_0']
  if kind=='tmdbDiscover':return self.discover(v,page,popular)
  if kind=='tmdbCollection':return self.released(self.api('collection/'+str(v['collectionId']),{'language':'en-US'}).get('parts',[]))
  if kind=='tmdbList':return self.released(self.api('list/'+str(v['listId']),{'language':'en-US','page':page}).get('items',[]),v.get('mediaType','movie'))
  if kind=='traktList':
   key=os.environ.get('TRAKT_CLIENT_ID')
   if not key:raise SourceUnavailable('Optional Trakt client ID is not configured')
   url='https://api.trakt.tv/lists/'+str(v['listId'])+'/items?'+urllib.parse.urlencode({'page':page,'limit':40});path=self.cache/'api'/(base.digest(str(self.today)+'|'+url)+'.json');values=json.loads(self.download(url,path,{'trakt-api-version':'2','trakt-api-key':key,'Content-Type':'application/json'}));items=[]
   for row in values:
    typ='tv' if row.get('type')=='show' else 'movie';entry=row.get('show') or row.get('movie') or {};i=entry.get('ids',{}).get('tmdb')
    if i:items.extend(self.released([{**self.api(typ+'/'+str(i),{'language':'en-US'}),'media_type':typ}],typ))
   return items
  raise SourceUnavailable('Unsupported catalogue source')
 def folder(self,recipe,seed=None):
  items=[];notes=[];seen=set();paths=set()
  def add(rows):
   for r in rows:
    key=(r['type'],r['id'])
    if key not in seen and r['poster_path'] not in paths:items.append(r);seen.add(key);paths.add(r['poster_path'])
  # These discovery headings need a full ranked artwork pool, even when the
  # imported provider lists are sparse or unavailable.
  if recipe['category']=='Discover' and recipe['title'] in ('Top Series','Top Movies'):
   typ='tv' if recipe['title']=='Top Series' else 'movie'
   for page in range(1,4):
    add(self.released(self.api(typ+'/top_rated',{'language':'en-US','page':page}).get('results',[]),typ))
   if len(items)<23:raise SourceUnavailable('Too few top-rated posters for the approved grid')
   return items[:60],['Artwork selected from TMDB top-rated '+('series' if typ=='tv' else 'movies')+'.']
  sources=recipe['sources']
  for s in sources[:6]:
   try:add(self.source(s))
   except SourceUnavailable as exc:notes.append(str(exc))
   if len(items)>=48:break
  if len(items)<24:
   for s in sources:
    if 'tmdbDiscover' in s:
     try:add(self.source(s,popular=True));add(self.source(s,page=2,popular=True))
     except SourceUnavailable as exc:notes.append(str(exc))
    if len(items)>=40:break
  if not items and recipe['title']=='Top Series':add(self.released(self.api('tv/top_rated',{'language':'en-US'}).get('results',[]),'tv'))
  if recipe['title']=='For You':
   items=[];seen.clear();paths.clear();add(self.released(self.api('trending/movie/week',{'language':'en-US'}).get('results',[])));add(self.released(self.api('trending/tv/week',{'language':'en-US'}).get('results',[]),'tv'));notes.append('Generic public picks; no personal recommendation account is included.')
  if not items and recipe['category'] in ['Actors','Legendary Directors']:
   people=self.api('search/person',{'query':recipe['title'],'include_adult':'false','language':'en-US'}).get('results',[])
   person=next((p for p in people if p.get('name','').casefold()==recipe['title'].casefold()),None)
   if person:
    credits=self.api('person/'+str(person['id'])+'/combined_credits',{'language':'en-US'})
    values=credits.get('cast',[]) if recipe['category']=='Actors' else [v for v in credits.get('crew',[]) if v.get('job')=='Director']
    add(self.released(values));notes.append('Filmography from TMDB credits.')
  if not items and recipe['title'] in ['Cloverfield collection','Eastrail 177 Trilogy']:
   names={'Cloverfield collection':['Cloverfield','10 Cloverfield Lane','The Cloverfield Paradox'],'Eastrail 177 Trilogy':['Unbreakable','Split','Glass']}[recipe['title']]
   for name in names:
    matches=self.api('search/movie',{'query':name,'include_adult':'false','language':'en-US'}).get('results',[])
    exact=[v for v in matches if v.get('title','').casefold()==name.casefold()];add(self.released((exact or matches)[:1]))
  if not items and seed:
   # Explicit fallback remains visible in status.json; it never claims a live source refresh.
   add(seed.get('titles',[]));notes.append('Using last-known representative artwork because the live source was unavailable.')
  if not items:raise SourceUnavailable('No released poster-bearing titles for '+recipe['title'])
  return items[:60],sorted(set(notes))
 def person(self,name):
  rows=self.api('search/person',{'query':name,'include_adult':'false','language':'en-US'}).get('results',[])
  exact=[r for r in rows if r.get('name','').casefold()==name.casefold()];row=next((r for r in exact+rows if r.get('profile_path')),None)
  if not row:raise SourceUnavailable('No person portrait for '+name)
  return self.image(row['profile_path'],'original')
 def backdrop(self,item):
  detail=self.api(item['type']+'/'+str(item['id']),{'language':'en-US'});path=detail.get('backdrop_path')
  if not path:raise SourceUnavailable('No backdrop for '+item['title'])
  return self.image(path,'original')
