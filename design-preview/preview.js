/* Review-only extension; the live dashboard and its data contract are untouched. */
'use strict';
const previewParams=new URLSearchParams(location.search);
const previewLayout='split';
// Opens in the light (Naruto) theme unless the link asks for another; the toggle still switches.
root.dataset.theme=previewParams.get('theme')||'light';
const topSix=C.slice(0,6);
if(!topSix.some(c=>c.k===pick))pick=topSix[0].k;
const requestedCharacter=previewParams.get('character');
if(topSix.some(c=>c.k===requestedCharacter))pick=requestedCharacter;
const characterColor=k=>css('--series-'+k)||css('--accent');
const seriesDash={sasuke:'',itachi:'9 4',kakashi:'3 3',madara:'12 3 2 3',minato:'14 4',hinata:'2 4'};
const originalCharacters=screens.characters;
const originalMethod=screens.method;
const originalMomentum=screens.momentum;
const trText=(en,de)=>LANG==='de'?de:en;
const originalOverview=screens.overview;
Object.assign(I18N.en,{
 'ov.of13':'Top character','ov.tableT':'Characters in numbers',
 'ov.heroLab':'Sources ranking {name} at top','ov.sure1':'Sources ranking {name} at top'
});
Object.assign(I18N.de,{
 'ov.of13':'Spitzenreiter','ov.tableT':'Charaktere in Zahlen',
 'ov.heroLab':'Quellen mit {name} an der Spitze','ov.sure1':'Quellen mit {name} an der Spitze'
});
// Use the same seven primary metrics and supplied precision adjustments as the analysis.
const primarySources=[['amazon','amazon_products'],['ebay','ebay_items'],['kleinanzeigen','kleinanzeigen_ads'],['youtube','youtube_comments_de'],['google_trends','google_interest'],['anime2you','anime2you_comment_mentions'],['narutop99','fan_votes_eu']];
const candidates=D.characters.filter(c=>c.role==='candidate');
const primaryValue=(c,source,key)=>{const value=c.counts[key];if(value==null||(source==='google_trends'&&c.flags?.includes('excluded_source')))return null;return value*(c.accuracy?.[source]??1);};
const firstPlaceSources=primarySources.filter(([source,key])=>{const candidate=candidates.find(c=>short(c.key)===LEAD.k),value=primaryValue(candidate,source,key);return value!=null&&value===Math.max(...candidates.map(c=>primaryValue(c,source,key)??-Infinity));}).length;
const outline=(path)=>`<svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${path}</svg>`;
function projectProfile(){
 const skills=[['Python','<path d="m4 5 6 7-6 7M13 19h7"/>'],['pandas','<rect x="3" y="4" width="18" height="16" rx="2"/><path d="M3 10h18M9 4v16M15 10v10"/>'],[trText('Data collection','Datenerhebung'),'<path d="M4 6h16M4 12h16M4 18h16M8 3v18"/>'],[trText('Market analysis','Marktanalyse'),'<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>'],[trText('Data visualisation','Datenvisualisierung'),'<path d="m3 17 6-6 4 4 8-8M15 7h6v6"/>']];
 return `<ul class="project-skills" aria-label="${trText('Project skills','Projektkompetenzen')}">${skills.map(([label,path])=>`<li>${outline(path)}${label}</li>`).join('')}</ul><div class="project-actions"><a class="btn project-source" href="https://github.com/sabers13/naruto-germany-market-analysis" target="_blank" rel="noopener" aria-label="${trText('Source code on GitHub','Quellcode auf GitHub')}">${outline('<path d="M9 19c-4 1-4-2-6-2m12 5v-4c0-1-.4-2-1-2 3 0 6-2 6-6 0-1-.4-2-1-3 0-1 0-2-.2-3-2 0-3 1-4 2a13 13 0 0 0-6 0C8 5 7 4 5 4c-.2 1-.2 2 0 3-1 1-1 2-1 3 0 4 3 6 6 6-.6 0-1 1-1 2v4"/>')}GitHub</a><a class="btn project-contact" href="https://sabersojudi.com/#contact">${outline('<rect x="3" y="7" width="18" height="14" rx="2"/><path d="M8 7V3h8v4M8 7v14M16 7v14"/>')}Hire Me</a></div>`;
}
screens.overview=()=>{
 const template=document.createElement('template');template.innerHTML=originalOverview();
 const pageIntro=template.content.querySelector('.page-head>div');pageIntro.insertAdjacentHTML('beforeend',projectProfile());
 const pageHead=template.content.querySelector('.page-head');pageHead.classList.add('overview-head');
 const podium=document.createElement('figure');podium.className='overview-podium';podium.setAttribute('aria-label',trText('Top three candidates: Sasuke first, Itachi second, Kakashi third','Die drei besten Kandidaten: Sasuke auf Platz eins, Itachi auf Platz zwei, Kakashi auf Platz drei'));
 podium.innerHTML=`${[['itachi',2],['sasuke',1],['kakashi',3]].map(([key,rank])=>`<div class="podium-place podium-${rank}"><img src="avatar-carousel-v2/assets/${key}.webp" alt="${esc(byName(key).n)}" width="512" height="768" decoding="async"><span class="podium-name">${esc(first(byName(key).n))}</span><span class="podium-step"><b>${rank}</b></span></div>`).join('')}`;
 pageHead.append(podium);
 const kpi=template.content.querySelector('.tile.hero [data-count]');kpi.dataset.count=firstPlaceSources;kpi.textContent=fmt(firstPlaceSources);
 const confidence=template.content.querySelector('.prog');confidence.querySelector('.t b').textContent=`${firstPlaceSources} ${t('of')} ${D.kpis.sources_in_score}`;confidence.querySelector('[data-w]').dataset.w=firstPlaceSources/D.kpis.sources_in_score*100;
 return template.innerHTML;
};
function lowerCharacterContent(){
 const template=document.createElement('template');template.innerHTML=originalCharacters();
 const grid=template.content.querySelector('.grid');
 // The original rank/index hero and all seven source counts now live inside the carousel.
 grid.children[0].remove();grid.children[0].remove();
 return grid.innerHTML;
}
function carouselURL(){const p=new URLSearchParams({theme:curTheme(),character:pick,layout:previewLayout,lang:LANG,v:'symbols-off'});return 'design-preview/integrated-carousel.html?'+p;}
screens.characters=()=>head(trText('Six characters. One closer look.','Sechs Charaktere. Ein genauer Blick.'),trText('Explore the top six candidates. Every figure follows the character in the centre.','Entdecke die sechs besten Kandidaten. Alle Zahlen folgen dem Charakter in der Mitte.'))+`<div class="layout-row"><p>${trText('Swipe, use the arrows, or choose a dot. Expand for character artwork.','Wischen, Pfeile oder Punkte verwenden. Erweitern für Charakterbilder.')}</p></div><iframe id="character-carousel" class="carousel-frame" title="${trText('Top six character carousel and source figures','Top-6-Karussell und Quellenzahlen')}" src="${carouselURL()}"></iframe><div class="carousel-lower" id="character-detail-cards">${lowerCharacterContent()}</div>`;
function drawCharacterTrend(){if(TR[pick]&&document.getElementById('chtrend'))areaChart(document.getElementById('chtrend'),{labels:Q.map(q=>q.slice(0,4)),series:[{name:byName(pick).n,values:TR[pick],color:characterColor(pick)}],height:180,xEvery:8,aria:t('ch.trendT')});}
screens.characters_after=()=>{
 configureFrame();drawCharacterTrend();
};
function configureFrame(){document.getElementById('character-carousel')?.contentWindow.postMessage({type:'naruto-config',theme:curTheme(),layout:previewLayout},'*');}
addEventListener('message',e=>{
 const frame=document.getElementById('character-carousel');if((e.origin!==location.origin&&e.origin!=='null')||e.source!==frame?.contentWindow)return;
 if(e.data?.type==='naruto-carousel-height'){const h=Number(e.data.height);if(Number.isFinite(h)&&h>200&&h<2200)frame.style.height=h+'px';}
 if(e.data?.type==='naruto-character'&&topSix.some(c=>c.k===e.data.character)){
  if(pick===e.data.character)return;pick=e.data.character;
  const url=new URL(location.href);url.searchParams.set('character',pick);history.replaceState(null,'',url);
  document.getElementById('character-detail-cards').innerHTML=lowerCharacterContent();drawCharacterTrend();
  document.querySelectorAll('#character-detail-cards [data-w]').forEach(i=>i.style.width=i.dataset.w+'%');decoratePreview();
 }
});
screens.momentum=()=>{
 let html=originalMomentum();
 html=html.replace(t('mo.sub'),trText('Google searches in Germany: compare any number of characters over time.','Google-Suchen in Deutschland: Vergleiche beliebig viele Charaktere im Zeitverlauf.'));
 const changes=Object.keys(TR).filter(k=>TRFLAG[k]!=='ambiguous_name'&&TRFLAG[k]!=='censored').map(k=>TRCHG[k]);
 if(changes.every(v=>v<0))html=html.replaceAll(t('mo.heroLab'),trText('Smallest decline','Geringster Rückgang')); 
 html=html.replace('<div class="plot" id="motrend">',`<div class="selection-actions"><span id="selection-count" aria-live="polite"></span><div><button class="btn btn-sm btn-secondary" id="select-all">${trText('Select all six','Alle sechs wählen')}</button> <button class="btn btn-sm btn-secondary" id="clear-series">${trText('Clear','Leeren')}</button></div></div><div class="plot" id="motrend">`);
 return html.replace(t('mo.chartS'),trText('Google interest in Germany · quarterly means, 0–100. Choose any number of characters.','Google-Interesse in Deutschland · Quartalsmittel, 0–100. Beliebig viele Charaktere wählen.'));
};
screens.momentum_after=()=>{
 const draw=()=>{
  const host=document.getElementById('motrend');
  const series=moSel.map(k=>({name:byName(k).n,values:TR[k],color:characterColor(k)}));
  if(series.length){areaChart(host,{labels:Q,series,height:300,xEvery:4,aria:t('mo.chartT')});host.querySelectorAll('.line-path').forEach((p,i)=>{const k=moSel[moSel.length-1-i];if(seriesDash[k])p.style.strokeDasharray=seriesDash[k];});}
  else host.innerHTML=`<div class="chart-empty">${trText('Choose a character above to draw its trend.','Wähle oben einen Charakter, um seinen Trend zu sehen.')}</div>`;
  document.getElementById('moleg').innerHTML=moSel.map(k=>`<span><svg width="24" height="10" aria-hidden="true"><path d="M0 5H24" stroke="${characterColor(k)}" stroke-width="2.5" stroke-dasharray="${seriesDash[k]}"/></svg> <span class="character-name">${esc(byName(k).n)}</span></span>`).join('');
  document.getElementById('selection-count').textContent=trText(`${moSel.length} of ${Object.keys(TR).length} selected · colour stays with the character`,`${moSel.length} von ${Object.keys(TR).length} gewählt · Farbe bleibt beim Charakter`);
  document.querySelectorAll('[data-mo]').forEach(b=>{b.setAttribute('aria-pressed',String(moSel.includes(b.dataset.mo)));b.style.setProperty('--series',characterColor(b.dataset.mo));});
 };
 document.querySelectorAll('[data-mo]').forEach(b=>b.onclick=()=>{const k=b.dataset.mo;moSel=moSel.includes(k)?moSel.filter(x=>x!==k):[...moSel,k];draw();});
 document.getElementById('select-all').onclick=()=>{moSel=Object.keys(TR);draw();};document.getElementById('clear-series').onclick=()=>{moSel=[];draw();};draw();
};
screens.method=()=>originalMethod().replace(/<a class="btn btn-on"[^>]*\bdownload\b[^>]*>[\s\S]*?<\/a>/,'');
const projectHeader=document.querySelector('.topbar');
const headerInner=document.createElement('div');headerInner.className='topbar-inner';
while(projectHeader.firstChild)headerInner.append(projectHeader.firstChild);
projectHeader.append(headerInner);document.body.prepend(projectHeader);
const ownerLink=headerInner.querySelector('.logo');ownerLink.className='portfolio-brand';ownerLink.textContent='Saber Sojudi';
const headerRight=headerInner.querySelector('.right');headerRight.classList.add('topbar-right');
headerRight.insertAdjacentHTML('beforeend',`<a class="project-wordmark" href="#overview">Naruto × Germany</a><a class="portfolio-back" href="https://sabersojudi.com/" aria-label="${trText('Back to portfolio','Zurück zum Portfolio')}">${outline('<path d="m12 5-7 7 7 7M5 12h14"/>')}<span>${trText('Back','Zurück')}</span></a>`);
const reviewBar=document.createElement('div');reviewBar.className='review-bar';
document.querySelector('.body').before(reviewBar);
const skip=document.createElement('a');skip.href='#view';skip.className='skip-main';skip.textContent='Skip to dashboard';document.body.prepend(skip);
window.decoratePreview=()=>{
 skip.textContent=trText("Skip to dashboard","Zum Dashboard springen");
 reviewBar.innerHTML=`<div><span class="preview-label">${trText('Design preview','Design-Vorschau')}</span><b>Naruto × Germany</b><span>${trText('22 Oct 2026 snapshot','Momentaufnahme 22. Okt. 2026')}</span></div><div><div class="theme-choices" role="group" aria-label="Theme"><button data-preview-theme="light" aria-pressed="${curTheme()==='light'}">Naruto · ${trText('Light','Hell')}</button><button data-preview-theme="dark" aria-pressed="${curTheme()==='dark'}">Uchiha · ${trText('Dark','Dunkel')}</button></div></div>`;
 document.querySelectorAll('[data-preview-theme]').forEach(b=>b.onclick=()=>{const theme=b.dataset.previewTheme;root.dataset.theme=theme;try{localStorage.setItem('preview-theme',theme);}catch{}const u=new URL(location.href);u.searchParams.set('theme',theme);history.replaceState(null,'',u);syncTheme();render(true);});
 formatCharacterNames(view);formatCharacterNames(reviewBar);formatCharacterNames(document.querySelector('.topbar'));
 document.querySelector('meta[name="theme-color"]')?.setAttribute('content',css('--bg-page'));
 document.title=t('nav.'+route())+' · Naruto × Germany — Saber Sojudi';
 document.querySelector('.portfolio-back span').textContent=trText('Back','Zurück');
};
// Keep sidebar theme controls and the preview theme switch in sync.
new MutationObserver(()=>{configureFrame();decoratePreview();}).observe(root,{attributes:true,attributeFilter:['data-theme']});
observeCharacterNames(view);
syncTheme();applyLang();render(false);
