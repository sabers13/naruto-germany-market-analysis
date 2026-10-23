/* Adapted from the owner's glass-carousel template. No framework dependencies. */
"use strict";
const ITEMS = [
  {id:"minato",title:"Minato Namikaze",subtitle:"The Yellow Flash",tagline:"The Fourth Hokage",desc:"Quiet confidence beneath the white cloak. The Yellow Flash stands ready to protect the people he loves."},
  {id:"madara",title:"Madara Uchiha",subtitle:"The Uchiha legend",tagline:"A legacy written in battle",desc:"An imposing presence in crimson armour. Madara carries the strength, pride and ambition of the Uchiha."},
  {id:"kakashi",title:"Kakashi Hatake",subtitle:"The Copy Ninja",tagline:"Always looking out for his team",desc:"A relaxed stance, a watchful eye. Beneath the mask is a teacher who always puts his comrades first."},
  {id:"itachi",title:"Itachi Uchiha",subtitle:"Behind the crimson clouds",tagline:"More than meets the eye",desc:"A quiet gaze beneath the Akatsuki cloak. Itachi's story is one of sacrifice, secrets and devotion to his brother."},
  {id:"sasuke",title:"Sasuke Uchiha",subtitle:"A path of his own",tagline:"The resolve of an Uchiha",desc:"Composed and determined, Sasuke follows his own path. His familiar purple rope belt frames a calm, focused stance."},
  {id:"naruto",title:"Naruto Uzumaki",subtitle:"Never give up",tagline:"A promise he intends to keep",desc:"Arms folded, head held high. Naruto's determination and loyalty turn even the hardest journey into a reason to keep going."},
  {id:"hinata",title:"Hinata Hyuga",subtitle:"Quiet courage",tagline:"Strength in her own way",desc:"Gentle in manner and strong in spirit. Hinata stands with the quiet courage to protect the people who matter to her."}
].filter(item=>item.id!=="naruto").sort((a,b)=>["sasuke","itachi","kakashi","madara","minato","hinata"].indexOf(a.id)-["sasuke","itachi","kakashi","madara","minato","hinata"].indexOf(b.id)).map(item => ({...item,image:`../avatar-carousel-v2/assets/${item.id}.webp`}));

const BACKGROUND_SOURCES = {"minato": "https://wallpapercat.com/minato-namikaze-wallpapers", "madara": "https://wallpapercat.com/madara-uchiha-wallpapers", "kakashi": "https://wallpapercat.com/kakashi-wallpapers", "itachi": "https://wallpapercat.com/itachi-uchiha-wallpapers", "sasuke": null, "naruto": null, "hinata": "https://wallpapercat.com/hinata-hyuga-wallpapers"};

const $ = id => document.getElementById(id);
const root = $("gc"), track = $("gc-track"), N = ITEMS.length;
const motionQuery = matchMedia("(prefers-reduced-motion: reduce)");
let reduce = motionQuery.matches;
let pos = 0, active = 0, playing = null, moved = false;
let barTimer, resizeFrame, returnFocus, slideFrame;
const params = new URLSearchParams(location.search);
const isGerman=params.get('lang')!=='en';
const first = ITEMS.findIndex(item => item.id === params.get("character"));
const storedTheme = params.get("theme");
let explicitTheme = storedTheme === "light" || storedTheme === "dark";
let geometry = {};

const icon = (path, cls="") => `<svg aria-hidden="true" class="${cls}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7">${path}</svg>`;
const expandIcon = icon('<path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/>');
const PLAY = icon('<path d="M8 5v14l11-7Z"/>');
const PAUSE = icon('<path d="M9 5v14M15 5v14"/>');

function media(item, decorative=false, eager=false) {
  return `<img src="${item.image}" alt="${decorative ? "" : `${item.title}, full-body Shippuden illustration`}" width="512" height="768" draggable="false" loading="${eager ? "eager" : "lazy"}" decoding="async"${eager ? ' fetchpriority="high"' : ""}>`;
}

// The supplied template's deterministic low-poly stage, kept neutral behind the glass.
function backdrop() {
  const W=1600,H=1000,cols=12,rows=8; let seed=7;
  const random=()=> (seed=(seed*16807)%2147483647)/2147483647;
  const points=[];
  for(let row=0;row<=rows;row++) for(let col=0;col<=cols;col++)
    points.push([col*W/cols+(col%cols&&row%rows?(random()-.5)*90:0),row*H/rows+(col%cols&&row%rows?(random()-.5)*90:0)]);
  let out="";
  for(let row=0;row<rows;row++) for(let col=0;col<cols;col++) {
    const i=row*(cols+1)+col,a=points[i],b=points[i+1],c=points[i+cols+1],d=points[i+cols+2];
    for(const triangle of [[a,b,d],[a,d,c]]) {
      const tone=Math.floor(8+random()*22);
      out+=`<polygon points="${triangle.map(point=>point.join(",")).join(" ")}" fill="rgb(${tone},${tone},${tone+3})"/>`;
    }
  }
  $("gc-bg").setAttribute("viewBox",`0 0 ${W} ${H}`);
  $("gc-bg").innerHTML=out;
}

const cards = ITEMS.map((item,index) => {
  const card=document.createElement("article");
  card.className="gc-card";
  card.setAttribute("role","group");
  card.setAttribute("aria-roledescription","slide");
  card.setAttribute("aria-label",`${index+1} of ${N}: ${item.title}`);
  card.innerHTML=`<div class="gc-img">${media(item,false,index===(first<0?0:first))}</div>
    <div class="gc-top"><button class="gc-chip" data-expand aria-label="Expand ${item.title}" tabindex="-1">${expandIcon}${isGerman?"Erweitern":"Expand"}</button></div>
    <div class="gc-body"><div class="gc-title"><h2>${item.title}</h2></div></div>`;
  card.addEventListener("click",event=>{
    if(moved) {event.preventDefault(); return;}
    if(event.target.closest("[data-expand]")) return openDetail(index);
    if(index!==active) { stopPlay(); go(index); }
  });
  card.querySelector("img").addEventListener("error",event=>{
    const message=document.createElement("div"); message.className="media-error";message.textContent="Avatar unavailable. Please reload.";
    event.target.replaceWith(message);
  });
  track.append(card);
  return card;
});

const pages = ITEMS.map((item,index)=>{
  const button=document.createElement("button");button.className="gc-page";
  button.setAttribute("aria-label",`Show ${item.title}`);
  button.innerHTML='<span aria-hidden="true"></span>';
  button.addEventListener("click",()=>{stopPlay();go(index);});
  $("gc-pagination").append(button);return button;
});

function measure() {
  const style=getComputedStyle(root);
  for(const key of ["card-w","step-1","step-n","rot-1","rot-n","depth","side-dim"])
    geometry[key]=parseFloat(style.getPropertyValue(`--${key}`));
}
function wrapDelta(index,position) {
  let delta=((index-position)%N+N)%N;
  if(delta>N/2) delta-=N;
  return delta;
}
function layout() {
  cards.forEach((card,index)=>{
    const delta=wrapDelta(index,pos),distance=Math.abs(delta),sign=Math.sign(delta);
    const x=sign*geometry["card-w"]*(geometry["step-1"]*Math.min(distance,1)+geometry["step-n"]*Math.max(distance-1,0));
    const rotation=reduce?0:-sign*(geometry["rot-1"]*Math.min(distance,1)+geometry["rot-n"]*Math.max(distance-1,0));
    const depth=-geometry.depth*distance+(distance<1?40*(1-distance):0);
    const fade=Math.max(0,1-distance*1.6);
    card.style.transform=`translateX(${x}px) translateZ(${depth}px) rotateY(${rotation}deg)`;
    card.style.zIndex=String(100-Math.round(distance*10));
    const edge=Math.max(0,Math.min(1,(3.45-distance)/1.05));
    card.style.opacity=edge*edge*(3-2*edge);
    card.style.pointerEvents=distance>3.2?"none":"";
    card.style.filter=`brightness(${1-(1-geometry["side-dim"])*Math.min(distance,1)}) saturate(${1-.35*Math.min(distance,1)})`;
    card.style.setProperty("--f",fade.toFixed(3));
    card.style.setProperty("--body-shift",`${112*(1-fade)}px`);
    card.classList.toggle("is-active",distance<.005);
    card.setAttribute("aria-hidden",String(distance>.5));
    card.querySelectorAll("button,a").forEach(control=>control.tabIndex=distance<.5?0:-1);
  });
}
function syncURL() {
  updateMetrics();
  parent.postMessage({type:"naruto-character",character:ITEMS[active].id},'*');
  const url=new URL(location.href);
  url.searchParams.set("character",ITEMS[active].id);
  if(explicitTheme) url.searchParams.set("theme",root.dataset.theme); else url.searchParams.delete("theme");
  history.replaceState(null,"",url);
}
function updateBar(immediate=false) {
  const item=ITEMS[active],text=$("gc-nowtext");
  clearTimeout(barTimer);
  text.style.opacity=immediate||reduce?1:0;
  const update=()=>{
    $("gc-ntitle").textContent=item.title;
    $("gc-thumb").innerHTML=media(item,true,true);text.style.opacity=1;
  };
  if(immediate||reduce) update(); else barTimer=setTimeout(update,100);
  pages.forEach((page,index)=>page.setAttribute("aria-current",String(index===active)));
  if(!playing) $("gc-live").textContent=`Character ${active+1} of ${N}: ${item.title}`;
}
function go(index,immediate=false) {
  cancelAnimationFrame(slideFrame);
  const target=((index%N)+N)%N;
  const start=pos,end=pos+wrapDelta(target,pos);
  active=target;updateBar(immediate);syncURL();
  if(immediate||reduce){pos=end;layout();return;}
  let began;
  const tick=now=>{
    began??=now;
    const progress=Math.min(1,(now-began)/420);
    pos=start+(end-start)*(1-Math.pow(1-progress,4));
    layout();
    if(progress<1)slideFrame=requestAnimationFrame(tick);
  };
  slideFrame=requestAnimationFrame(tick);
}
function step(direction) {go(active+direction);}

let dragging=false,pointerId=null,startX=0,startPos=0,lastX=0,lastTime=0,velocity=0;
track.addEventListener("pointerdown",event=>{
  if(event.button!==0||event.target.closest("a,button,summary"))return;
  cancelAnimationFrame(slideFrame);
  dragging=true;moved=false;pointerId=event.pointerId;startX=lastX=event.clientX;
  startPos=pos;lastTime=performance.now();velocity=0;
});
track.addEventListener("pointermove",event=>{
  if(!dragging||event.pointerId!==pointerId)return;
  const dx=event.clientX-startX;
  if(!moved&&Math.abs(dx)>6) {
    moved=true;root.classList.add("dragging");stopPlay();track.setPointerCapture(event.pointerId);
  }
  if(!moved)return;
  const now=performance.now();
  velocity=(event.clientX-lastX)/Math.max(1,now-lastTime);lastX=event.clientX;lastTime=now;
  pos=startPos-dx/(geometry["card-w"]*geometry["step-1"]);layout();
});
function endDrag(event) {
  if(!dragging||event.pointerId!==pointerId)return;
  dragging=false;root.classList.remove("dragging");
  if(moved) {
    const flick=event.type==="pointercancel"?0:Math.max(-3,Math.min(3,-velocity*1.8));
    go(Math.round(pos+flick));
    if(track.hasPointerCapture(event.pointerId))track.releasePointerCapture(event.pointerId);
    setTimeout(()=>moved=false,0);
  }
}
track.addEventListener("pointerup",endDrag);track.addEventListener("pointercancel",endDrag);
track.addEventListener("pointerleave",event=>{if(dragging&&!moved)endDrag(event);});

let wheelTotal=0,wheelLock=0;
root.addEventListener("wheel",event=>{
  if(event.target.closest("dialog"))return;
  const delta=Math.abs(event.deltaX)>Math.abs(event.deltaY)?event.deltaX:(event.shiftKey?event.deltaY:0);
  if(!delta)return;event.preventDefault();stopPlay();wheelTotal+=delta;
  const now=performance.now();
  if(Math.abs(wheelTotal)>40&&now>wheelLock){step(Math.sign(wheelTotal));wheelTotal=0;wheelLock=now+260;}
},{passive:false});
root.addEventListener("keydown",event=>{
  if(event.target.closest("dialog"))return;
  const keys={ArrowRight:()=>step(1),ArrowLeft:()=>step(-1),Home:()=>go(0),End:()=>go(N-1)};
  if(keys[event.key]){event.preventDefault();stopPlay();keys[event.key]();}
  else if(event.key==="Enter"&&(event.target===root||event.target===track)){event.preventDefault();openDetail(active);}
});
$("gc-prev").onclick=()=>{stopPlay();step(-1);};
$("gc-next").onclick=()=>{stopPlay();step(1);};
function startPlay() {
  if(playing||reduce)return;
  playing=setInterval(()=>step(1),3800);
  $("gc-live").setAttribute("aria-live","off");$("gc-live").textContent="";
  $("gc-play").innerHTML=PAUSE;$("gc-play").setAttribute("aria-pressed","true");$("gc-play").setAttribute("aria-label","Pause autoplay");
}
function stopPlay() {
  if(!playing)return;
  clearInterval(playing);playing=null;
  $("gc-live").setAttribute("aria-live","polite");
  $("gc-play").innerHTML=PLAY;$("gc-play").setAttribute("aria-pressed","false");$("gc-play").setAttribute("aria-label","Start autoplay");
}
$("gc-play").onclick=()=>playing?stopPlay():startPlay();
root.addEventListener("focusin",event=>{if(!event.target.closest("#gc-play"))stopPlay();});
document.addEventListener("visibilitychange",()=>{if(document.hidden)stopPlay();});

function openDetail(index) {
  const item=ITEMS[index];stopPlay();returnFocus=document.activeElement;
  $("gc-dhero").innerHTML=media(item,false,true);$("gc-dtitle").textContent=item.title;
  $("gc-dsubtitle").textContent=item.subtitle;$("gc-ddesc").textContent=item.desc;
  const backgroundFile = item.id === "naruto" || item.id === "sasuke" ? `${item.id}-uploaded.png` : `${item.id}.webp`;
  // Third-party wallpapers have no reuse permission: the public edition ships without them.
  const publicEdition = window.DASHBOARD.meta.edition === "public";
  if (!publicEdition) $("gc-dialog").style.setProperty("--detail-art",`url("../avatar-carousel-v2/backgrounds/${backgroundFile}")`);
  const source = publicEdition ? null : BACKGROUND_SOURCES[item.id];
  $("gc-source").hidden = !source;
  if (source) $("gc-source").href = source;
  else $("gc-source").removeAttribute("href");
  $("gc-dialog").showModal();
}
$("gc-dclose").onclick=()=>$("gc-dialog").close();
$("gc-dialog").addEventListener("click",event=>{
  if(event.target!==event.currentTarget)return;
  const box=event.currentTarget.getBoundingClientRect();
  if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)event.currentTarget.close();
});
$("gc-dialog").addEventListener("close",()=>returnFocus?.focus({preventScroll:true}));
function setTheme(theme) {
  root.dataset.theme=theme;document.documentElement.style.colorScheme=theme;
  $("theme-label").textContent=theme==="dark"?"Light":"Dark";
  $("theme-toggle").setAttribute("aria-label",`Switch to ${theme==="dark"?"light":"dark"} theme`);
  $("theme-toggle").setAttribute("aria-pressed",String(theme==="light"));
  document.querySelector('meta[name="theme-color"]').content=theme==="dark"?"#0B0B0D":"#E7E7EA";
  measure();layout();syncURL();
}
$("theme-toggle").onclick=()=>{stopPlay();explicitTheme=true;setTheme(root.dataset.theme==="dark"?"light":"dark");};
addEventListener("resize",()=>{cancelAnimationFrame(resizeFrame);resizeFrame=requestAnimationFrame(()=>{measure();layout();});});
motionQuery.addEventListener("change",()=>{reduce=motionQuery.matches;stopPlay();cancelAnimationFrame(slideFrame);pos=active;measure();layout();});
backdrop();
root.dataset.layout="split";
setTheme(explicitTheme?storedTheme:matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light");
go(first<0?0:first,true);

function updateMetrics(){
 const item=ITEMS[active], c=window.DASHBOARD.characters.find(c=>c.key.split('_')[0]===item.id);
 const de=params.get('lang')!=='en', f=v=>v==null?'–':new Intl.NumberFormat(de?'de-DE':'en-US').format(v);
 const labels=de?['Amazon · Produkte','eBay · Artikel','Kleinanzeigen · Anzeigen','YouTube · Videos (DE)','YouTube · Kommentare (DE)','Anime2You · Artikel','Fan-Stimmen · Europa']:['Amazon · products','eBay · items','Kleinanzeigen · ads','YouTube · videos (DE)','YouTube · comments (DE)','Anime2You · articles','Fan votes · Europe'];
 const counts=['amazon_products','ebay_items','kleinanzeigen_ads','youtube_videos_de','youtube_comments_de','anime2you_articles','fan_votes_eu'];
 // The public edition publishes no Kleinanzeigen figures: drop that row.
 const shown=counts.map((k,i)=>[k,i]).filter(([k])=>!(window.DASHBOARD.meta.edition==='public'&&k==='kleinanzeigen_ads'));
 $('active-identity').innerHTML=`<div class="identity-top"><span>${de?'Rang':'Rank'} ${c.rank} · ${de?'Charaktere':'Characters'}</span><span>${de?'Top 6 Kandidaten':'Top 6 shortlist'}</span></div><h2>${c.name}</h2>`;
 $('character-metrics').innerHTML=`<div class="metric-summary"><div><span>${de?'Evidenzindex':'Evidence index'}</span><strong>${f(c.index)}<small> / 100</small></strong></div><div class="lens-ranks">${[['shoppers',de?'Handel':'Shoppers'],['watching',de?'Interesse':'Watching'],['votes',de?'Stimmen':'Votes']].map(([k,label])=>`<div><b>${c.lens_ranks?.[k]==null?'–':'#'+f(c.lens_ranks[k])}</b><span>${label}</span></div>`).join('')}</div></div><div class="metric-sources"><h3>${de?'Die Zahlen dahinter':'The numbers behind the character'}</h3>${shown.map(([k,i])=>`<div class="metric-row"><span>${labels[i]}</span><b>${c.counts[k]!=null&&c.counts[k]===Math.max(...window.DASHBOARD.characters.filter(x=>x.role==='candidate').map(x=>x.counts[k]??0))?`<small class="source-leader">${de?'Höchster Wert':'Highest'}</small> `:''}${f(c.counts[k])}</b></div>`).join('')}</div><p class="metric-note">${de?'Momentaufnahme vom 22. Oktober 2026. Quellen separat vergleichen.':'Snapshot 22 Oct 2026. Compare each source separately.'}</p>`;
 document.documentElement.lang=de?'de':'en';
 root.style.setProperty('--character',({sasuke:'#B99AFA',itachi:'#F47488',kakashi:'#64C7B7',madara:'#E69A79',minato:'#E8C65B',hinata:'#B0B7E8'})[item.id]);
 formatCharacterNames(root);reportSize();
}
function reportSize(){requestAnimationFrame(()=>parent.postMessage({type:'naruto-carousel-height',height:Math.ceil(document.body.scrollHeight)},'*'));}
new ResizeObserver(reportSize).observe(root);
addEventListener('message',e=>{if((e.origin!==location.origin&&e.origin!=='null')||e.source!==parent)return;const m=e.data;if(m.type==='naruto-config'){root.dataset.layout=m.layout;setTheme(m.theme);reportSize();}});

observeCharacterNames(root);formatCharacterNames(root);

if(isGerman){
 $('gc-prev').setAttribute('aria-label','Vorheriger Charakter');$('gc-next').setAttribute('aria-label','Nächster Charakter');
 $('gc-play').setAttribute('aria-label','Automatischen Wechsel starten');$('gc-dclose').setAttribute('aria-label','Charakterdetails schließen');
 $('gc-hint').textContent='Ziehen oder die Pfeiltasten verwenden';$('gc-source').textContent='Bildquelle ↗';
 const descriptions={sasuke:['Ein eigener Weg','Entschlossen und ruhig geht Sasuke seinen eigenen Weg. Der bekannte violette Gürtel prägt seine Silhouette.'],itachi:['Hinter den roten Wolken','Ein ruhiger Blick unter dem Akatsuki-Mantel. Itachis Geschichte handelt von Opfern, Geheimnissen und der Verbundenheit mit seinem Bruder.'],kakashi:['Der Kopierninja','Entspannt, aber aufmerksam. Hinter der Maske steht ein Lehrer, der seine Kameraden immer an die erste Stelle setzt.'],madara:['Die Uchiha-Legende','Eine eindrucksvolle Erscheinung in roter Rüstung. Madara verkörpert die Stärke, den Stolz und den Ehrgeiz der Uchiha.'],minato:['Der gelbe Blitz','Ruhige Entschlossenheit unter dem weißen Mantel. Minato ist bereit, die Menschen zu beschützen, die ihm wichtig sind.'],hinata:['Leiser Mut','Sanft im Auftreten und stark im Willen. Hinata steht mit stillem Mut für die Menschen ein, die ihr wichtig sind.']};
 ITEMS.forEach(item=>{item.subtitle=descriptions[item.id][0];item.desc=descriptions[item.id][1];});
 formatCharacterNames(root);reportSize();
}
