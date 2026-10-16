/* Pure selection logic shared by the gallery and export checks. */
(function(root){
 const api={configuration(shelves,selected,{hideFolderTitles=true}={}){
  const result=[];
  for(const shelf of shelves){
   const group=shelf.source.group._0;
   const folders=group.contentSources.filter(folder=>selected.has(folder.id));
   if(folders.length)result.push({...shelf,sortOrder:result.length,source:{...shelf.source,group:{...shelf.source.group,_0:{...group,hideTitle:hideFolderTitles,contentSources:folders}}}});
  }
  return result;
 }};
 if(typeof module!=='undefined'&&module.exports)module.exports=api;
 else root.ShipflixSelection=api;
})(typeof globalThis!=='undefined'?globalThis:this);
