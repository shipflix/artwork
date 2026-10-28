const assert = require('node:assert/strict');
const fs = require('node:fs');
const {configuration} = require('../static/selection.js');
const catalog = JSON.parse(fs.readFileSync('data/catalog.json')).folders;
const shelves = JSON.parse(fs.readFileSync('data/strand-template.json'));
const before = JSON.stringify(shelves);
const select = records => configuration(shelves, new Set(records.map(r=>r.id)));
const count = rows => rows.reduce((n,r)=>n+r.source.group._0.contentSources.length,0);
assert.equal(count(select(catalog)),787);
assert.deepEqual(select([]),[]);
const recommended=select(catalog.filter(r=>r.recommended));
assert.equal(count(recommended),163);
assert.equal(count(recommended.filter(r=>r.title==='Film Collections')),11);
assert.equal(count(recommended.filter(r=>r.title==='Networks')),20);
assert.equal(count(select(catalog.filter(r=>r.category==='Networks'))),80);
const film=catalog.filter(r=>r.category==='Film Collections');
assert.equal(count(select(film)),255);
assert.equal(count(select(film.filter(r=>r.style==='franchise'))),244);
const subset=[catalog[0],catalog.find(r=>r.category==='Networks'),film.find(r=>r.style==='franchise')];
const result=select(subset);
assert.equal(count(result),3);
assert.deepEqual(result.map(r=>r.sortOrder),result.map((_,i)=>i));
for(const row of result){
 const original=shelves.find(s=>s.id===row.id);
 for(const folder of row.source.group._0.contentSources)
  assert.deepEqual(folder,original.source.group._0.contentSources.find(f=>f.id===folder.id));
}
assert.ok(result.every(row=>row.source.group._0.hideTitle===true));
const visibleTitles=configuration(shelves,new Set(subset.map(r=>r.id)),{hideFolderTitles:false});
assert.ok(visibleTitles.every(row=>row.source.group._0.hideTitle===false));
assert.equal(count(visibleTitles),count(result));
for(let i=0;i<result.length;i++)assert.deepEqual(visibleTitles[i].source.group._0.contentSources,result[i].source.group._0.contentSources);
assert.equal(JSON.stringify(shelves),before);
console.log('Selection checks passed: recommended, all, empty, franchises, mixed subsets, sources and ordering.');
