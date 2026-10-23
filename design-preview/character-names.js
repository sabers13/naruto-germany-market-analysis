/* One formatter for HTML prose, SVG chart labels, tooltips and embedded slides. */
(()=>{
 const data=window.DASHBOARD?.characters||[];
 const aliases=[...new Set([...data.flatMap(c=>[c.name,c.name.split(' ')[0]]),'Naruto','Uchiha','Boruto','Nagato','Pain','Hinata Hyūga'])].sort((a,b)=>b.length-a.length);
 const pattern=aliases.map(name=>name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&')).join('|');
 const expression=new RegExp('(?<![\\p{L}\\p{N}_])('+pattern+')(?![\\p{L}\\p{N}_])','gu');
 const svgNS='http://www.w3.org/2000/svg';
 window.formatCharacterNames=(host)=>{
  if(!host)return;
  const nodes=[];
  if(host.nodeType===Node.TEXT_NODE)nodes.push(host);
  else {const walker=document.createTreeWalker(host,NodeFilter.SHOW_TEXT);while(walker.nextNode())nodes.push(walker.currentNode);}
  for(const node of nodes){
   const parent=node.parentElement;
   if(!parent||parent.closest('.character-name,script,style,title,desc,textarea,option,[data-no-character-font]'))continue;
   expression.lastIndex=0;const matches=[...node.textContent.matchAll(expression)];if(!matches.length)continue;
   const frag=document.createDocumentFragment();let start=0;
   for(const match of matches){if(match.index>start)frag.append(document.createTextNode(node.textContent.slice(start,match.index)));
    const span=parent.namespaceURI===svgNS?document.createElementNS(svgNS,'tspan'):document.createElement('span');span.setAttribute('class','character-name');span.textContent=match[0];frag.append(span);start=match.index+match[0].length;
   }
   if(start<node.textContent.length)frag.append(document.createTextNode(node.textContent.slice(start)));node.replaceWith(frag);
  }
 };
 window.observeCharacterNames=host=>{
  const observer=new MutationObserver(records=>{for(const record of records){if(record.type==='characterData')window.formatCharacterNames(record.target);else for(const added of record.addedNodes)if(added.nodeType===Node.TEXT_NODE||added.nodeType===Node.ELEMENT_NODE)window.formatCharacterNames(added);}});
  observer.observe(host,{childList:true,subtree:true,characterData:true});return observer;
 };
})();
