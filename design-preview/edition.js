/* Edition layer for contract 1.2.0. Loads after preview.js and re-renders.
   Both editions: Naruto leaves the candidate table and gets his own page, source
   counts and the trend reference come from the release, flat trends read as flat.
   Regions come from Google Trends (interview.js swaps in the Kleinanzeigen map).
   Public edition (meta.edition === 'public'): no Kleinanzeigen figures. Every number comes from window.DASHBOARD. */
'use strict';
const PUBLIC=D.meta.edition==='public';
const BC=D.benchmark_comparison;
const narutoRow=D.characters.find(c=>c.role==='benchmark');
const scoreSources=D.sources.filter(s=>s.in_score).length,contextSources=D.sources.length-scoreSources;
const trendRef=Number((/=\s*([\d.]+)/.exec(D.momentum.unit)||[])[1]);
const refText=locale=>trendRef.toLocaleString(locale,{maximumFractionDigits:1});
// HANDOFF_UI §19: a 12-month move smaller than Google's integer rounding reads as flat
// (Sasuke −0.15, Itachi −0.14 index points); Kakashi −0.48 and Hinata −0.69 are real moves.
const FLAT_POINTS=0.25;
const movePoints=k=>{const v=D.momentum.partial_last?TR[k].slice(0,-1):TR[k],mean=a=>a.reduce((s,x)=>s+x,0)/a.length;return mean(v.slice(-4))-mean(v.slice(-8,-4));};
const isFlat=k=>TRFLAG[k]!=='censored'&&Math.abs(movePoints(k))<FLAT_POINTS;
const pct=v=>fmt(v,0)+' %';
const fragment=html=>{const tpl=document.createElement('template');tpl.innerHTML=html;return tpl;};

Object.assign(I18N.en,{
 'nav.naruto':'Naruto','me.srcS':`${scoreSources} sources in the index, ${contextSources} shown only as context`,
 'ov.trendS':`Google searches in Germany, quarterly index on one shared scale (the search term "Naruto" = ${refText('en-US')}), Oct 2021 to Oct 2026`
});
Object.assign(I18N.de,{
 'nav.naruto':'Naruto','me.srcS':`${scoreSources} Quellen im Index, ${contextSources} nur als Kontext`,
 'ov.trendS':`Google-Suchen in Deutschland, Index pro Quartal auf einer gemeinsamen Skala (Suchbegriff „Naruto“ = ${refText('de-DE')}), Okt. 2021 bis Okt. 2026`
});
if(PUBLIC){
 Object.assign(I18N.en,{
  'ov.shopsNote':'Amazon and eBay together, not de-duplicated','ov.t2c':'Amazon, eBay','ov.barsS':'Listings on Amazon and eBay, top 6','h.shops':'Shop listings (Amazon, eBay)',
  'me.heroP':'from the published sources, all collected on {date}. Kleinanzeigen feeds the index, but its figures are not published.',
 });
 Object.assign(I18N.de,{
  'ov.shopsNote':'Amazon und eBay zusammen, nicht bereinigt','ov.t2c':'Amazon, eBay','ov.barsS':'Angebote auf Amazon und eBay, Top 6','h.shops':'Shop-Angebote (Amazon, eBay)',
  'me.heroP':'aus den veröffentlichten Quellen, alle am {date} erhoben. Kleinanzeigen fließt in den Index ein, die Zahlen daraus werden nicht veröffentlicht.',
 });
 // The public page is the published dashboard, not a design review.
 const decorate=window.decoratePreview;
 window.decoratePreview=()=>{decorate();document.querySelector('.review-bar .preview-label')?.remove();};
}

/* Navigation: Naruto gets his own page, before Method. */
{
 const method=document.querySelector('#nav [data-r="method"]');
 method?.insertAdjacentHTML('beforebegin','<a href="#naruto" data-r="naruto" data-i18n="nav.naruto">Naruto</a>');
 const railMethod=document.querySelector('.rail [data-r="method"]');
 railMethod?.insertAdjacentHTML('beforebegin','<a class="icon-btn" href="#naruto" data-r="naruto" data-i18n-label="nav.naruto" aria-label="Naruto"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M4 20V10M10 20V4M16 20v-7M20 20H2"/></svg></a>');
}

/* Overview */
const editionOverview=screens.overview;
screens.overview=()=>{
 const tpl=fragment(editionOverview()),c=tpl.content;
 c.querySelector('tr.bench')?.remove();
 c.querySelector('#all .tbl-wrap')?.insertAdjacentHTML('afterend',`<p class="card-sub" style="margin:12px 0 0">${trText('Naruto is not in this table. ','Naruto steht nicht in dieser Tabelle. ')}<a href="#naruto">${trText('See how the candidates compare with him.','So schneiden die Kandidaten gegen ihn ab.')}</a></p>`);
 if(PUBLIC){
  c.querySelectorAll('.ptile').forEach(p=>{if(p.textContent.includes('Kleinanzeigen'))p.remove();});
  const tiles=c.querySelector('.ptiles');if(tiles)tiles.style.gridTemplateColumns='repeat(2,1fr)';
  // "First place" needs every primary count, including the unpublished Kleinanzeigen ads,
  // so the public page shows the release's own top-3 count instead.
  const label=trText(`Sources with ${first(LEAD.n)} in their top 3`,`Quellen mit ${first(LEAD.n)} in den Top 3`);
  const hero=c.querySelector('.tile.hero');
  if(hero){hero.querySelector('.lab').textContent=label;const v=hero.querySelector('[data-count]');v.dataset.count=LEAD.t3;v.textContent=fmt(LEAD.t3);}
  const prog=c.querySelector('.prog');
  if(prog){prog.querySelector('.t span').textContent=label;prog.querySelector('.t b').textContent=`${LEAD.t3} ${t('of')} ${D.kpis.sources_in_score}`;prog.querySelector('[data-w]').dataset.w=LEAD.t3/D.kpis.sources_in_score*100;}
 }
 return tpl.innerHTML;
};

/* Characters: the public page drops the Kleinanzeigen price bar. */
const editionLower=lowerCharacterContent;
lowerCharacterContent=function(){
 const tpl=fragment(editionLower());
 if(PUBLIC)tpl.content.querySelectorAll('.hb').forEach(b=>{if(b.querySelector('.t span')?.textContent==='Kleinanzeigen')b.remove();});
 return tpl.innerHTML;
};

/* Momentum: flat moves read as flat (no rise or fall language). */
const editionMomentum=screens.momentum;
screens.momentum=()=>{
 const tpl=fragment(editionMomentum()),c=tpl.content;
 const keys=Object.keys(TR),clean=keys.filter(k=>TRFLAG[k]!=='ambiguous_name'&&TRFLAG[k]!=='censored');
 const flat=clean.filter(isFlat);
 const hero=c.querySelector('.hero-card');
 if(hero&&flat.length){
  // Keep the screen's own lead (the list below already leaves it out); it is flat here.
  const coreLead=keys.find(k=>byName(k).n===hero.querySelector('.hero-name').textContent);
  const lead=byName(flat.includes(coreLead)?coreLead:flat[0]);
  flat.sort((a,b)=>(b===lead.k)-(a===lead.k));
  const names=flat.map(k=>first(byName(k).n));
  hero.querySelector('.glass').textContent=trText('Most stable','Am stabilsten');
  hero.querySelector('.hero-name').textContent=lead.n;
  hero.querySelector('.hero-num').innerHTML=trText('flat','flach');
  hero.querySelector('p').textContent=trText(
   `${names.join(' and ')} moved less than Google's rounding over the last 12 months (${flat.map(k=>fmt(movePoints(k),2)).join(' and ')} index points), so they count as flat. Names marked * also mean other things.`,
   `${names.join(' und ')} haben sich in den letzten 12 Monaten weniger bewegt als Googles Rundung (${flat.map(k=>fmt(movePoints(k),2)).join(' und ')} Indexpunkte) und gelten als flach. Mit * markierte Namen haben auch andere Bedeutungen.`);
  hero.querySelectorAll('.hero-list li').forEach(li=>{
   const k=keys.find(x=>li.textContent.startsWith(byName(x).n));
   if(k&&isFlat(k)&&k!==lead.k)li.querySelector('b').textContent=trText('flat','flach');
  });
 }
 return tpl.innerHTML;
};

/* Regions: Google Trends by state (regions_trends). */
{
 const RT=D.regions_trends,idx=Object.fromEntries(RT.states.map(s=>[s.code,s.naruto_index]));
 const shareKeys=TOP3.filter(k=>RT.states[0].shares[LONG[k]]!==undefined);
 const range=k=>{const v=RT.states.map(s=>s.shares[LONG[k]]).filter(x=>x!=null);return [Math.min(...v),Math.max(...v)];};
 const reading=k=>({flat:trText('flat, within rounding','flach, innerhalb der Rundung'),hint:trText('hint only','nur ein Hinweis'),ambiguous:trText('name has other meanings','Name hat weitere Bedeutungen')})[RT.readings[LONG[k]]];
 const others=Object.keys(RT.readings).filter(k=>!shareKeys.includes(short(k))&&RT.readings[k]==='flat');
 const othersSpread=Math.max(...others.map(k=>range(short(k))).map(([a,b])=>b-a));
 let focus=RT.states.reduce((a,s)=>s.naruto_index>a.naruto_index?s:a).code;
 const map=()=>{
  const v=Object.values(idx),lo=Math.min(...v),hi=Math.max(...v);
  const fill=x=>`color-mix(in oklab,var(--accent) ${Math.round(15+75*(x-lo)/(hi-lo))}%,var(--bg-card))`;
  return `<div class="geo-map"><svg class="germany-svg" viewBox="0 0 480 580" role="group" aria-label="${trText('Geographic map of Germany’s 16 federal states','Geografische Karte der 16 Bundesländer')}">${window.GERMANY_STATES.map(g=>{const s=RT.states.find(s=>s.code===g.code);return `<path class="map-state" tabindex="0" data-state="${s.code}" role="img" aria-label="${esc(s.name)}: ${s.naruto_index} ${trText('of 100','von 100')}" d="${g.path}" fill="${fill(s.naruto_index)}"><title>${esc(s.name)}: ${s.naruto_index}</title></path>`;}).join('')}<g class="map-boundaries" aria-hidden="true">${window.GERMANY_STATES.map(g=>`<path d="${g.path}"/>`).join('')}</g></svg><div class="map-focus" id="map-focus" aria-live="polite"></div></div><div class="scale"><span>${trText('lower','weniger')} · ${lo}</span><i style="background:color-mix(in oklab,var(--accent) 20%,var(--bg-card))"></i><i style="background:color-mix(in oklab,var(--accent) 45%,var(--bg-card))"></i><i style="background:var(--accent)"></i><span>${hi} · ${trText('higher','mehr')}</span></div><p class="map-note">${trText('Hover or focus a state for its value. Strongest state = 100.','Bundesland berühren oder fokussieren. Stärkstes Bundesland = 100.')}<br>${trText('Data','Daten')}: Google Trends · ${trText('Map','Karte')}: © GeoBasis-DE / BKG (2026), ${trText('adapted','bearbeitet')} · <a href="https://sgx.geodatenzentrum.de/wfs_vg250?service=WFS&request=GetCapabilities" target="_blank" rel="noopener">VG250</a> · <a href="https://www.govdata.de/dl-de/by-2-0" target="_blank" rel="noopener">dl-de/by-2-0</a></p>`;
 };
 screens.regions=()=>{
  const order=[...RT.states].sort((a,b)=>b.naruto_index-a.naruto_index||a.name.localeCompare(b.name)),top=order[0],last=order[order.length-1];
  const lo=last.naruto_index,hi=top.naruto_index,south=order.slice(-2).map(s=>s.name);
  const [y0,y1]=RT.window.split(' ').map(d=>d.slice(0,4));
  const rows=order.map(s=>`<tr><td class="who">${esc(s.name)}</td><td class="lead">${s.naruto_index}</td>${shareKeys.map(k=>`<td>${s.shares[LONG[k]]==null?'–':pct(s.shares[LONG[k]])}</td>`).join('')}</tr>`).join('');
  const hintKey=shareKeys.find(k=>RT.readings[LONG[k]]==='hint');
  const hintNote=hintKey?(()=>{const [,b]=range(hintKey),at=RT.states.filter(s=>s.shares[LONG[hintKey]]===b).map(s=>s.name).join(', ');return trText(`${first(byName(hintKey).n)}'s highest value is in ${at} (${pct(b)}), but that is only a hint. `,`${first(byName(hintKey).n)}s höchster Wert liegt in ${at} (${pct(b)}), das ist aber nur ein Hinweis. `);})():'';
  const missing=RT.missing.map(k=>byName(short(k)).n).join(', ');
  return head(trText('Where in Germany do people search for Naruto?','Wo in Deutschland wird nach Naruto gesucht?'),trText('Share of all Google searches in each state that were for Naruto, strongest state = 100. This measures interest, not the number of fans.','Anteil aller Google-Suchen je Bundesland, die Naruto galten, stärkstes Land = 100. Gemessen wird Interesse, nicht die Zahl der Fans.'),'Google Trends','tag')+`<div class="grid">${card('c7 map-card',trText('Naruto · search interest by state','Naruto · Suchinteresse je Bundesland'),'',map())}<section class="hero-card c5 region-home reveal" aria-label="${esc(trText('Strongest state','Stärkstes Bundesland'))}"><div class="hero-top"><span class="glass">${trText('Strongest state','Stärkstes Bundesland')}</span><span>Google Trends</span></div><div class="hero-name">${esc(top.name)}</div><div class="region-subject">${trText('Naruto search interest','Naruto-Suchinteresse')}</div><div class="hero-num">${hi}<small>${trText('of 100','von 100')}</small></div><p>${trText(`Every state sits between ${lo} and ${hi}. The south is lowest: ${south.join(' and ')} are the two weakest states.`,`Alle Länder liegen zwischen ${lo} und ${hi}. Der Süden liegt am niedrigsten: ${south.join(' und ')} sind die zwei schwächsten Länder.`)}</p><div class="hero-bar"><i style="width:${lo}%"></i></div><div class="hero-ends"><span>${trText('Weakest','Am schwächsten')} · ${esc(last.name)} ${lo}</span><span>${hi-lo} ${trText('points apart','Punkte Abstand')}</span></div><ul class="hero-list">${order.slice(1,4).map(s=>`<li><span>${esc(s.name)}</span><b>${s.naruto_index}</b></li>`).join('')}</ul><p style="margin-top:18px">${trText('Top 3 characters · share by state','Top 3 Charaktere · Anteil je Bundesland')}</p><ul class="hero-list" style="margin-top:6px">${shareKeys.map(k=>{const [a,b]=range(k);return `<li><span>${esc(first(byName(k).n))} · ${reading(k)}</span><b>${a}–${b} %</b></li>`;}).join('')}</ul></section>${card('c12',trText('Every state in numbers','Alle Bundesländer in Zahlen'),trText('Naruto: index, strongest state = 100. Characters: share of their own Google comparison with Naruto, in whole percent, so a 1-point difference can be rounding.','Naruto: Index, stärkstes Land = 100. Charaktere: Anteil an ihrem eigenen Google-Vergleich mit Naruto, in ganzen Prozent; 1 Punkt Unterschied kann Rundung sein.'),`<div class="tbl-wrap"><table class="data"><thead><tr><th>${t('h.state')}</th><th>${trText('Naruto interest','Naruto-Interesse')}</th>${shareKeys.map(k=>`<th><span class="character-name">${esc(first(byName(k).n))}</span></th>`).join('')}</tr></thead><tbody>${rows}</tbody></table></div><p class="card-sub" style="margin:14px 0 0">${hintNote}${trText(`The other candidates with a flat reading differ by ${othersSpread} points or less between states.${missing?` ${missing} has no regional data.`:''} Source: Google Trends, web search, ${y0} to ${y1}; plain search terms, so "Naruto" mostly means the series.`,`Die übrigen flachen Kandidaten unterscheiden sich zwischen den Ländern um höchstens ${othersSpread} Punkte.${missing?` Für ${missing} gibt es keine Regionaldaten.`:''} Quelle: Google Trends, Websuche, ${y0} bis ${y1}; einfache Suchbegriffe, „Naruto“ meint also meist die Serie.`)}</p>`)}</div>`;
 };
 screens.regions_after=()=>{
  const show=code=>{focus=code;const s=RT.states.find(s=>s.code===code);document.getElementById('map-focus').innerHTML=`<span>Naruto</span><strong>${esc(s.name)}</strong><span class="map-value">${s.naruto_index}</span><span>${trText('Search interest, of 100','Suchinteresse, von 100')}</span>`;window.formatCharacterNames?.(document.getElementById('map-focus'));};
  document.querySelectorAll('[data-state]').forEach(p=>{p.onpointerenter=()=>show(p.dataset.state);p.onfocus=()=>show(p.dataset.state);p.onpointerdown=e=>e.preventDefault();});show(focus);
 };
}

/* Method */
const editionMethod=screens.method;
screens.method=()=>{
 const tpl=fragment(editionMethod()),c=tpl.content;
 if(PUBLIC){
  D.sources.filter(s=>s.records==null).forEach(s=>{
   const label=t(({kleinanzeigen:'s.ka'})[s.id]||'');
   c.querySelectorAll('.src').forEach(row=>{if(row.querySelector('b')?.textContent===label)row.querySelector('em').textContent=trText('not published','nicht veröffentlicht');});
  });
 }
 return tpl.innerHTML;
};

/* Naruto compared with the candidates (ANALYSIS_PLAN §13): fair sources only. */
const SOURCE_LABEL={amazon:['Amazon.de · products','Amazon.de · Produkte'],ebay:['eBay.de · items','eBay.de · Artikel'],kleinanzeigen:['Kleinanzeigen · ads','Kleinanzeigen · Anzeigen'],youtube_comments:['YouTube · German comments','YouTube · deutsche Kommentare'],youtube_videos:['YouTube · German-channel videos','YouTube · Videos deutscher Kanäle'],google_trends:['Google Trends · search interest','Google Trends · Suchinteresse'],anime2you_comments:['Anime2You · comment mentions','Anime2You · Kommentar-Erwähnungen'],anime2you_articles:['Anime2You · articles','Anime2You · Artikel'],narutop99:['NARUTOP99 · fan votes (Europe)','NARUTOP99 · Fan-Stimmen (Europa)']};
const num=(s,re)=>(re.exec(s.detail||'')||[])[1];
const reasonText=s=>{
 const de=LANG==='de',p=num(s,/precision ([\d.]+)/),ci=num(s,/CI from ([\d.]+)/),n=num(s,/n = (\d+)/),r=num(s,/r = ([\d.]+)/);
 const f=x=>x==null?'–':Number(x).toLocaleString(loc(),{minimumFractionDigits:2,maximumFractionDigits:2});
 return ({
  vote:de?'Direkte Stimmen für eine Figur.':'Direct votes for one character.',
  precision_ok:de?`Narutos Treffer sind verlässlich (Genauigkeit ${f(p)}).`:`Naruto's matches are reliable (precision ${f(p)}).`,
  precision_low:de?`Viele „Naruto“-Treffer meinen die Serie (nur ${f(p)} gehören zur Figur).`:`Many "Naruto" matches mean the series (only ${f(p)} are about the character).`,
  precision_uncertain:de?`Zu wenige geprüfte Treffer: ${f(p)} aus ${n} Stichproben, könnte auch nur ${f(ci)} sein.`:`Too few checked matches: ${f(p)} from ${n} samples, could be as low as ${f(ci)}.`,
  alias_restricted:de?'Naruto wird hier enger gezählt als die anderen Charaktere.':'Naruto is counted more narrowly here than the other characters.',
  franchise_dominated:de?`Die Suchen folgen der Serie, nicht der Figur (r = ${f(r)}).`:`Searches follow the series, not the character (r = ${f(r)}).`,
  not_measured:de?'Für Naruto nicht gemessen.':'Not measured for Naruto.'
 })[s.reason]||s.reason;
};
screens.naruto=()=>{
 const fair=BC.sources.filter(s=>s.comparable);
 const nVotes=narutoRow.counts.fan_votes_eu;
 const rows=C.map(c=>({c,v:c.fv==null||!nVotes?null:c.fv/nVotes*100})).filter(x=>x.v!=null).sort((a,b)=>b.v-a.v);
 const band=v=>v>=95&&v<=105;
 const bars=hbars(rows.map(({c,v})=>({l:c.n,v,lead:v>=100,note:band(v)?trText('about the same','etwa gleich'):''})),Math.max(...rows.map(r=>r.v)),pct);
 const sourceRows=BC.sources.map(s=>{
  const hidden=PUBLIC&&s.benchmark_value==null&&s.id==='kleinanzeigen';
  const value=s.benchmark_value==null?(hidden?trText('not published','nicht veröffentlicht'):'–'):fmt(s.benchmark_value,s.id==='google_trends'?1:0);
  return `<tr><td class="who">${esc(trText(...SOURCE_LABEL[s.id]))}</td><td>${s.comparable?`<span class="chip acc">${trText('fair','fair')}</span>`:`<span class="chip flat">${trText('not compared','nicht verglichen')}</span>`}</td><td style="white-space:normal;text-align:left">${esc(reasonText(s))}</td><td>${value}</td></tr>`;
 }).join('');
 return head(trText('How do the candidates compare with Naruto?','Wie schneiden die Kandidaten gegen Naruto ab?'),trText('Naruto is the main character and the name of the series, so most sources count him too high or too low. Only sources where the count is clearly about the character are compared.','Naruto ist die Hauptfigur und der Name der Serie, deshalb zählen ihn die meisten Quellen zu hoch oder zu niedrig. Verglichen werden nur Quellen, bei denen die Zahl klar die Figur meint.'))+`<div class="grid">
  <section class="hero-card c5 region-home reveal" aria-label="${esc(narutoRow.name)}"><div class="hero-top"><span class="glass">${trText('Fair sources','Faire Quellen')}: ${fair.length} ${t('of')} ${BC.sources.length}</span><span>NARUTOP99</span></div><div class="hero-name">${esc(narutoRow.name)}</div><div class="region-subject">${trText('Fan votes in Europe','Fan-Stimmen in Europa')}</div><div class="hero-num">${fmt(nVotes)}<small>${trText('votes','Stimmen')}</small></div><p>${trText(`Only ${fair.length} of ${BC.sources.length} sources allow a fair comparison. One source can't rank anyone above or below Naruto overall; it shows where fans in Europe stand.`,`Nur ${fair.length} von ${BC.sources.length} Quellen erlauben einen fairen Vergleich. Eine Quelle kann niemanden insgesamt vor oder hinter Naruto stellen; sie zeigt, wo die Fans in Europa stehen.`)}</p><ul class="hero-list">${rows.slice(0,4).map(({c,v})=>`<li><span>${esc(c.n)}</span><b>${pct(v)}</b></li>`).join('')}</ul></section>
  ${card('c7',trText("Fan votes as a share of Naruto's","Fan-Stimmen im Verhältnis zu Naruto"),trText(`100 % = Naruto's ${fmt(nVotes)} votes. Between 95 and 105 % reads "about the same".`,`100 % = Narutos ${fmt(nVotes)} Stimmen. Zwischen 95 und 105 % gilt als „etwa gleich“.`),bars)}
  ${card('c12',trText('Which sources are compared, and why','Welche Quellen verglichen werden und warum'),trText('A source is compared only when its count for Naruto means the character, not the series.','Eine Quelle wird nur verglichen, wenn ihre Zahl für Naruto die Figur meint und nicht die Serie.'),`<div class="tbl-wrap"><table class="data"><thead><tr><th>${t('src')}</th><th>${trText('Compared','Verglichen')}</th><th style="text-align:left">${trText('Why','Warum')}</th><th>${trText("Naruto's value","Narutos Wert")}</th></tr></thead><tbody>${sourceRows}</tbody></table></div>`)}
 </div>`;
};

applyLang();render(false);
