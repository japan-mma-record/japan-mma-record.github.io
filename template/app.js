(function(){
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n.toLocaleString('ja-JP');
const D = {}; let ready = false; let byFighter = null; let query = '';
const MARKS = {1989:'修斗 旗揚げ',1993:'パンクラス 旗揚げ',1997:'PRIDE.1',2001:'DEEP 旗揚げ',2015:'RIZIN 旗揚げ'};

function pl(p){ return (D.meta && D.meta.plabel[p]) || p; }
function pkey(p){ return 'p-' + p.replace(/_/g,'-'); }
function dshort(d){ return d ? d.slice(5).replace('-','.') : ''; }
function dlong(d){ if(!d) return ''; const [y,m,dd]=d.split('-'); const w='日月火水木金土'[new Date(+y,+m-1,+dd).getDay()]; return `${y}年${+m}月${+dd}日（${w}）`; }
function fname(id, fallback){ const f = id && D.fighters[id]; return f ? (f[0] || f[1]) : (fallback || ''); }
function flink(id, name){ return id && D.fighters[id] ? `<a class="u nb" href="#f-${esc(id)}">${esc(name)}</a>` : `<span class="nb">${esc(name)}</span>`; }
function mainBout(k){ const bs = D.bouts[k] || []; return bs.length ? bs[bs.length-1] : null; }
function winnerLine(b){
  if(!b) return '';
  const u = b[10] ? '<span class="unc">未確定</span>' : '';
  if(b[5]===1 || b[5]===2){ const w = b[5]===1 ? [b[1],b[2]] : [b[3],b[4]], l = b[5]===1 ? [b[3],b[4]] : [b[1],b[2]];
    return `<span class="win">WIN</span><strong>${esc(w[1])}</strong><span class="def">　def.　</span>${esc(l[1])}${u}`; }
  const t = b[5]==='d' ? '引き分け' : b[5]==='nc' ? '無効試合' : '勝敗不明';
  return `${esc(b[2])}<span class="def">　vs　</span>${esc(b[4])}<span class="def">　${t}</span>${u}`;
}
function teamTbl(k){ const ts=(D.meta.teams||{})[k]; if(!ts||!ts.length) return '';
  return `<h2 class="sec">出場チーム</h2><div class="tbl"><table><thead><tr><th>チーム</th><th>メンバー</th><th>成績</th></tr></thead><tbody>${ts.map(t=>`<tr><td>${esc(t[0])}</td><td>${esc(t[1])}</td><td>${esc(t[2])}</td></tr>`).join('')}</tbody></table></div>`; }
function rtag(b){ return b[11] ? `<span class="unc">${esc(b[11])}・戦績に数えない</span>` : ''; }
function rt(b){ const r = b[7] ? (/R$/i.test(b[7]) ? b[7] : b[7]+'R') : ''; return [r, b[8]].filter(Boolean).join(' '); }

function buildIndex(){
  if(byFighter) return;
  byFighter = {};
  for(const e of D.events){ const bs = D.bouts[e[0]] || []; bs.forEach((b,i)=>{
    if(b[1]) (byFighter[b[1]] = byFighter[b[1]] || []).push([e,b,1]);
    if(b[3]) (byFighter[b[3]] = byFighter[b[3]] || []).push([e,b,2]);
  }); }
}

/* ---------- 画面 ---------- */
function vTop(){
  const today = new Date().toISOString().slice(0,10);
  const past = D.events.filter(e => e[1] <= today);
  const latest = past.slice(-8).reverse();
  const nb = D.events.reduce((s,e)=>s+e[6],0);
  const yrs = {}; D.events.forEach(e=>{ const y=+e[1].slice(0,4); yrs[y]=(yrs[y]||0)+1; });
  const y0 = 1989, y1 = new Date().getFullYear(); const max = Math.max(...Object.values(yrs));
  let bars='', lbl='';
  for(let y=y0;y<=y1;y++){ const c=yrs[y]||0, h=Math.round(c/max*100), mk=MARKS[y];
    bars += `<div class="c${mk?' mk':''}"><div class="b" style="height:${h}%"></div>${mk?`<span class="lab" style="bottom:calc(${h}% + 10px)">${esc(mk)}</span>`:''}<span class="tip">${y}年 ${c}大会</span></div>`;
    lbl += `<span style="visibility:${(y%5===0||y===y0||y===y1)?'visible':'hidden'}">${y}</span>`; }
  const LS = new Set(D.meta.listed || []); const P = promoStats().filter(p=>!LS.size||LS.has(p.k)).sort((a,b)=>b.n-a.n).slice(0,16).sort((a,b)=>a.a-b.a || b.n-a.n);
  const span1 = y1+1;
  const gantt = P.map(p=>{ const on = p.b>=y1-1; const L=(p.a-y0)/(span1-y0)*100, W=(p.b+1-p.a)/(span1-y0)*100;
    return `<a class="g row" href="#${pkey(p.k)}"><span class="n">${esc(pl(p.k))}</span><span class="t"><span class="${on?'on':''}" style="left:${L.toFixed(2)}%;width:${W.toFixed(2)}%"></span></span><span class="c">${p.a}–${on?'':p.b}　${fmt(p.n)}大会</span></a>`; }).join('');
  const ticks = [1989,1995,2000,2005,2010,2015,2020,y1].map(y=>{ const L=((y===y1?y+1:y)-y0)/(span1-y0)*100; const tx = y===y0?'0':y===y1?'-100%':'-50%';
    return `<span style="left:${L.toFixed(2)}%;transform:translateX(${tx})">${y}</span>`; }).join('');
  const up = D.upcoming.filter(u=>u.d>=today);
  const nf = up.find(u=>u.m);
  const upc = up.filter(u=>u!==nf).slice(0,4);
  return `
  <section class="hero"><p class="bgnum" aria-hidden="true">1989—${y1}</p><div class="wrap">
    <p class="eyebrow">EVERY FIGHT SINCE 1989</p>
    <h1>日本の総合格闘技、<br><em>全試合。</em></h1>
    <p class="lead">修斗の旗揚げから今週末の大会まで。勝敗・決まり手・時間を、公式記録と当時の報道で確かめ、出典つきで一試合ずつ残しています。</p>
    <form class="bigsearch" id="bform" role="search"><label for="bq" style="position:absolute;left:-9999px">選手名・大会名で検索</label>
      <input id="bq" type="search" placeholder="選手名・大会名で検索　例：桜庭和志、PRIDE.1" autocomplete="off"><button type="submit">検索</button></form>
    <div class="stats">
      <div><p class="v">${fmt(D.events.length)}</p><p class="l">興行</p></div>
      <div><p class="v">${fmt(nb)}</p><p class="l">試合</p></div>
      <div><p class="v">${fmt(Object.keys(D.fighters).length)}</p><p class="l">選手</p></div>
    </div></div></section>
  ${nf ? `<section class="band"><div class="wrap">
    <div class="nf-head"><p class="nf-tag"><span class="live"></span>NEXT FIGHT</p><p style="color:var(--fg2);font-size:14px">${esc(dlong(nf.d))}　${esc(nf.n)}　${esc(nf.v)}</p></div>
    ${nf.m.l?`<p class="nf-title">${esc(nf.m.l)}</p>`:''}
    <div class="vs"><div class="s"><p class="nm">${esc(nf.m.f1)}</p><p class="gy">${esc(nf.m.g1)}</p></div><p class="x">VS</p><div class="s"><p class="nm">${esc(nf.m.f2)}</p><p class="gy">${esc(nf.m.g2)}</p></div></div>
    ${upc.length?`<div class="cards">${upc.map(u=>`<a href="#upcoming"><p class="d">${esc(dshort(u.d))}</p><p class="n">${esc(u.n)}</p><p class="m">${u.m?esc(u.m.f1+' vs '+u.m.f2):esc(u.v)}</p></a>`).join('')}</div>`:''}
  </div></section>`:''}
  <main class="wrap">
    <section class="sec"><div class="sh"><h2>最新の結果</h2><a class="aside lnk" href="#events">すべての大会 →</a></div>
      ${latest.map(e=>{ const b=mainBout(e[0]); return `<a class="res row" href="#e-${esc(e[0])}"><span class="dt">${esc(e[1].replace(/-/g,'.'))}</span><span class="ev"><small>${esc(pl(e[2]))}</small><b>${esc(e[3])}</b></span><span class="mb">${winnerLine(b)}</span><span class="mt">${esc(b?[b[6],rt(b)].filter(Boolean).join(' '):'')}</span></a>`; }).join('')}
    </section>
    <section class="sec"><div class="sh"><h2>${y1-y0+1}年の歩み</h2><span class="aside" style="font-weight:500">年ごとの大会数</span></div>
      <div class="chart"><div class="in"><div class="bars">${bars}</div><div class="yrs">${lbl}</div></div></div></section>
    <section class="sec"><div class="sh"><h2>団体の系譜</h2><a class="aside lnk" href="#promotions">すべての団体 →</a></div>
      <div class="gantt"><div class="in">${gantt}<div class="axis"><span style="width:128px"></span><span class="t">${ticks}</span><span style="width:170px"></span></div></div></div></section>
  </main>`;
}
function promoStats(){
  const m = {}; D.events.forEach(e=>{ const p=m[e[2]]||(m[e[2]]={k:e[2],n:0,b:0,a:9999,z:0}); p.n++; p.b+=0; const y=+e[1].slice(0,4); p.a=Math.min(p.a,y); p.z=Math.max(p.z,y); p.bo=(p.bo||0)+e[6]; });
  return Object.values(m).map(p=>({k:p.k,n:p.n,a:p.a,b:p.z,bo:p.bo}));
}
function vEvent(k){
  const e = D.events.find(x=>x[0]===k); if(!e) return notFound();
  const bs = D.bouts[k] || [];
  const mb = bs.filter(b=>!b[11]); const ko = mb.filter(b=>/^T?KO/.test(b[6])).length, sub = mb.filter(b=>/^一本|^Submission/.test(b[6])).length, dec = mb.filter(b=>/^判定/.test(b[6])).length;
  const rows = bs.map(b=>{
    let A=[b[1],b[2]], B=[b[3],b[4]], r='<span class="rs o">—</span>';
    if(b[5]===2){ [A,B]=[B,A]; }
    if(b[5]===1||b[5]===2) r='<span class="rs w">WIN</span>'; else if(b[5]==='d') r='<span class="rs o">引分</span>'; else if(b[5]==='nc') r='<span class="rs o">無効</span>';
    return `<tr><td class="num">${b[0]||''}</td><td>${r}</td><td>${flink(A[0],A[1])}</td><td><span class="def">${(b[5]===1||b[5]===2)?'def.':'vs'}</span> ${flink(B[0],B[1])}${b[10]?'<span class="unc">未確定</span>':''}</td><td>${esc(b[6])}${rtag(b)}</td><td class="num">${esc(rt(b))}</td><td>${esc(b[9])}</td></tr>`; }).join('');
  return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a>　›　${esc(e[1].slice(0,4))}年</p>
    <div class="ph"><div><a class="badge" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a><h1>${esc(e[3])}</h1><p class="sub">${esc(dlong(e[1]))}${e[4]?'　'+esc(e[4]):''}</p></div>
    <div class="kpis"><div><p class="k">試合</p><p class="v">${mb.length}</p></div><div><p class="k">KO・TKO</p><p class="v r">${ko}</p></div><div><p class="k">一本</p><p class="v">${sub}</p></div><div><p class="k">判定</p><p class="v">${dec}</p></div></div></div>
    <div class="tbl"><table><thead><tr><th class="num">No.</th><th>結果</th><th>勝者</th><th>対戦相手</th><th>決まり手</th><th class="num">R・時間</th><th>階級・ルール</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${teamTbl(k)}<p class="src">出典：${e[5].length?e[5].map(u=>/^https?:/.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc((()=>{try{return decodeURIComponent(u)}catch(e){return u}})().replace(/^https?:\/\//,'').slice(0,70))}</a>`:esc(u)).join('　'):''}</p></main>`;
}
function vFighter(id){
  const f = D.fighters[id]; if(!f) return notFound(); buildIndex();
  const list = (byFighter[id]||[]).slice().sort((a,b)=> b[0][1].localeCompare(a[0][1]) || b[1][0]-a[1][0]);
  let w=0,l=0,d=0,nc=0; const pr = new Set();
  const rows = list.map(([e,b,side])=>{ pr.add(e[2]);
    const opp = side===1 ? [b[3],b[4]] : [b[1],b[2]];
    let r='<span class="rs o">—</span>';
    const cnt = !b[11];
    if(b[5]===side){cnt&&w++; r='<span class="rs w">勝</span>';} else if(b[5]===1||b[5]===2){cnt&&l++; r='<span class="rs l">負</span>';} else if(b[5]==='d'){cnt&&d++; r='<span class="rs o">分</span>';} else if(b[5]==='nc'){cnt&&nc++; r='<span class="rs o">無効</span>';}
    return `<tr data-d="${esc(e[1])}"><td>${r}</td><td>${flink(opp[0],opp[1])}</td><td><a class="u" href="#e-${esc(e[0])}">${esc(e[3])}</a></td><td class="num">${esc(e[1].replace(/-/g,'.'))}</td><td>${esc(b[6])}${rtag(b)}${b[10]?'<span class="unc">未確定</span>':''}</td><td class="num">${esc(rt(b))}</td></tr>`; }).join('');
  const nm = f[0] || f[1];
  const span = list.length ? `${list[list.length-1][0][1].slice(0,4)}年〜${list[0][0][1].slice(0,4)}年` : '';
  const st = '';
  return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#fighters">選手</a></p>
    <div class="ph"><div>${f[0]?`<p class="sub" style="margin:0;letter-spacing:.08em">${esc(f[1])}</p>`:''}<h1>${esc(nm)}</h1><p class="sub">${esc([...pr].map(pl).join('・'))}</p></div>
    <div class="kpis" id="fk"><div><p class="k">勝</p><p class="v r">${w}</p></div><div><p class="k">敗</p><p class="v">${l}</p></div><div><p class="k">分</p><p class="v">${d}</p></div>${nc?`<div><p class="k">無効</p><p class="v">${nc}</p></div>`:''}</div></div>
    <p class="sub" id="fnote" style="font-size:13px;color:var(--fg3)">収録${list.length}試合（${esc(span)}）　${esc(st)}　※日本で開かれた大会・日本の団体の大会と、世界の主要団体（UFC・ONE・PFL・Bellatorなど）での試合の戦績です。そのほかの海外の大会での試合は含みません</p>
    <div class="tbl"><table><thead><tr><th>結果</th><th>対戦相手</th><th>大会</th><th class="num">日付</th><th>決まり手</th><th class="num">R・時間</th></tr></thead><tbody id="fb">${rows}</tbody></table></div></main>`;
}
function enhanceFighter(id){
  fetch('w/'+encodeURIComponent(id)+'.json').then(r=>r.ok?r.json():null).then(w=>{
    if(!w || location.hash!=='#f-'+id) return;
    const k=document.getElementById('fk'), n=document.getElementById('fnote'), tb=document.getElementById('fb'); if(!k||!tb) return;
    const [W,L,Dr,NC]=w.rec;
    k.innerHTML=`<div><p class="k">通算 勝</p><p class="v r">${W}</p></div><div><p class="k">敗</p><p class="v">${L}</p></div><div><p class="k">分</p><p class="v">${Dr}</p></div>${NC?`<div><p class="k">無効</p><p class="v">${NC}</p></div>`:''}`;
    n.innerHTML=`通算戦績はWikipedia「<a class="u" href="${esc(w.u)}" target="_blank" rel="noopener">${esc(w.t)}</a>」の戦績表によります（海外の試合を含む全${W+L+Dr+NC}試合）。印のついた試合はWikipediaからの記録です。`;
    const rs={win:'<span class="rs w">勝</span>',loss:'<span class="rs l">負</span>',draw:'<span class="rs o">分</span>',nc:'<span class="rs o">無効</span>'};
    let h='';
    w.x.forEach(x=>{ h+=`<tr data-d="${esc(x[0])}"><td>${rs[x[1]]||'—'}</td><td><span class="nb">${esc(x[2])}</span></td><td>${esc(x[4])}<span class="unc">Wikipedia</span></td><td class="num">${esc((x[0]||'').replace(/-/g,'.'))}</td><td>${esc(x[3])}</td><td class="num"></td></tr>`; });
    tb.insertAdjacentHTML('beforeend',h);
    [...tb.querySelectorAll('tr')].sort((a,b)=>(b.dataset.d||'').localeCompare(a.dataset.d||'')).forEach(tr=>tb.appendChild(tr));
  }).catch(()=>{});
}
let evYear = null;
function vEvents(){
  const years = [...new Set(D.events.map(e=>e[1].slice(0,4)))].sort();
  if(!evYear) evYear = years[years.length-1];
  const ev = D.events.filter(e=>e[1].startsWith(evYear)).slice().reverse();
  let cur='', out='';
  ev.forEach(e=>{ const m=+e[1].slice(5,7); if(m!==cur){ cur=m; out+=`<p class="mo">${m}月</p>`; }
    out += `<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].slice(5).replace('-','.'))}</span><span class="p">${esc(pl(e[2]))}</span><span class="n">${esc(e[3])}</span><span class="c">${e[6]}試合</span></a>`; });
  return `<main class="wrap"><div class="sh"><h1>大会</h1><span class="aside" style="font-weight:500">${esc(evYear)}年　${ev.length}大会</span></div>
    <div class="chips" id="ychips">${years.map(y=>`<button type="button" data-y="${y}" aria-pressed="${y===evYear}">${y}</button>`).join('')}</div>
    <div class="list">${out}</div></main>`;
}
function vPromotions(){
  const P = promoStats().sort((a,b)=>b.n-a.n);
  return `<main class="wrap"><div class="sh"><h1>団体</h1><span class="aside" style="font-weight:500">${P.length}団体</span></div>
    <div class="pgrid">${P.map(p=>`<a href="#${pkey(p.k)}"><b>${esc(pl(p.k))}</b><span>${p.a}–${p.b}年　${fmt(p.n)}大会・${fmt(p.bo)}試合</span></a>`).join('')}</div></main>`;
}
function vPromotion(key){
  const p = Object.keys(D.meta.plabel).find(k=>k.replace(/_/g,'-')===key); if(!p) return notFound();
  const ev = D.events.filter(e=>e[2]===p).slice().reverse();
  let cur='', out='';
  ev.forEach(e=>{ const y=e[1].slice(0,4); if(y!==cur){ cur=y; out+=`<p class="mo">${y}</p>`; }
    out += `<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].slice(5).replace('-','.'))}</span><span class="n">${esc(e[3])}</span><span class="c">${e[6]}試合</span></a>`; });
  const nb = ev.reduce((s,e)=>s+e[6],0);
  return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#promotions">団体</a></p>
    <div class="ph"><div><h1>${esc(pl(p))}</h1><p class="sub">${esc(ev.length?ev[ev.length-1][1].slice(0,4)+'年〜'+ev[0][1].slice(0,4)+'年':'')}</p></div>
    <div class="kpis"><div><p class="k">大会</p><p class="v r">${fmt(ev.length)}</p></div><div><p class="k">試合</p><p class="v">${fmt(nb)}</p></div></div></div>
    <div class="list">${out}</div></main>`;
}
function topFighters(){ buildIndex(); return Object.keys(byFighter).sort((a,b)=>byFighter[b].length-byFighter[a].length); }
function vFighters(){
  const ids = topFighters().slice(0,120);
  return `<main class="wrap"><div class="sh"><h1>選手</h1><span class="aside" style="font-weight:500">${fmt(Object.keys(D.fighters).length)}人</span></div>
    <form class="fsearch" id="fform" role="search"><label for="fq" style="position:absolute;left:-9999px">選手名で探す</label><input id="fq" type="search" placeholder="選手名で探す（日本語・英語）" autocomplete="off"></form>
    <div class="pgrid" id="flist">${fcards(ids)}</div></main>`;
}
function fcards(ids){ buildIndex(); return ids.map(id=>{ const f=D.fighters[id]; return `<a href="#f-${esc(id)}"><b>${esc(f[0]||f[1])}</b><span>${f[0]?esc(f[1])+'　':''}${(byFighter[id]||[]).length}試合</span></a>`; }).join('') || '<p class="note" style="background:var(--bg);margin:0;padding:16px">見つかりませんでした。</p>'; }
const norm = s => String(s||'').toLowerCase().replace(/[\s・･．.　\-]/g,'').replace(/[ぁ-ゖ]/g, c=>String.fromCharCode(c.charCodeAt(0)+0x60));
function searchFighters(q){ const n=norm(q); if(!n) return []; buildIndex();
  return Object.keys(D.fighters).filter(id=>{ const f=D.fighters[id]; return norm(f[0]).includes(n)||norm(f[1]).includes(n); })
    .sort((a,b)=>(byFighter[b]||[]).length-(byFighter[a]||[]).length).slice(0,60); }
function vSearch(){
  const n = norm(query);
  const fs = searchFighters(query);
  const es = n ? D.events.filter(e=>norm(e[3]).includes(n)).slice(-60).reverse() : [];
  return `<main class="wrap"><div class="sh"><h1>「${esc(query)}」の検索結果</h1><span class="aside" style="font-weight:500">選手${fs.length}・大会${es.length}${fs.length>=60||es.length>=60?'（上位のみ）':''}</span></div>
    <h2 class="mo" style="margin-top:28px">選手</h2><div class="pgrid">${fs.length?fcards(fs):'<p class="note" style="background:var(--bg);margin:0;padding:16px">該当する選手はいません。</p>'}</div>
    <h2 class="mo" style="margin-top:36px">大会</h2><div class="list">${es.map(e=>`<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].replace(/-/g,'.').slice(2))}</span><span class="p">${esc(pl(e[2]))}</span><span class="n">${esc(e[3])}</span><span class="c">${e[6]}試合</span></a>`).join('')||'<p class="note">該当する大会はありません。</p>'}</div></main>`;
}
function vUpcoming(){
  const today = new Date().toISOString().slice(0,10);
  const up = D.upcoming.filter(u=>u.d>=today);
  return `<main class="wrap"><div class="sh"><h1>今後の予定</h1><span class="aside" style="font-weight:500">${up.length}大会　毎日更新</span></div>
    ${up.map(u=>`<section class="ucard"><div class="h"><span class="d">${esc(u.d.replace(/-/g,'.'))}</span><b>${esc(u.n)}</b><small>${esc(u.v)}</small></div>
      ${u.c.length?`<ol>${u.c.map(c=>`<li><strong>${esc(c[0])}</strong><span>vs</span><strong>${esc(c[1])}</strong>${c[2]?`<span>${esc(c[2])}</span>`:''}</li>`).join('')}</ol>`:'<p class="note" style="padding:0 18px 14px;margin:12px 0 0">対戦カードは未発表です。</p>'}
      ${u.src&&u.src.length?`<p class="src" style="margin:0;padding:0 18px 14px">出典：${u.src.slice(0,3).map(s=>`<a href="${esc(s)}" target="_blank" rel="noopener">${esc(s.replace(/^https?:\/\//,'').slice(0,60))}</a>`).join('　')}</p>`:''}</section>`).join('')}</main>`;
}
function vAbout(){
  return `<main class="wrap"><div class="sh"><h1>このサイトについて</h1></div><div class="prose">
    <p>日本MMA戦績録は、1989年の修斗から現在まで、日本で行われた総合格闘技（MMA）の大会と試合の記録をまとめたデータベースです。無料で誰でも見ることができます。</p>
    <h2>記録の決め方</h2>
    <p>記録の元にしているのは、各団体の公式記録（パンクラス公式サイトの試合結果データベース、修斗の公式記録など）と、当時の報道（ゴング格闘技、BOUT REVIEW、eFight など）です。どの大会も、ページの下に出典を載せています。</p>
    <p>推測では埋めません。勝敗がはっきり書かれた資料がない試合は「勝敗不明」のままにしています。資料の書き方があいまいな試合には「未確定」の印をつけています。</p>
    <p>日本の資料がまだ見つかっていない試合は、海外の記録サイトの記録を日本語に直して載せています。出典欄に「海外の記録サイト」とある大会がそれです。日本の資料で確かめられたものから、順に置き換えていきます。</p>
    <h2>選手名</h2>
    <p>選手名は、出典の公式記録や報道に書かれている表記を使っています。</p>
    <h2>収録範囲</h2>
    <p>MMAの試合だけを収録しています。グラップリングだけ、キックボクシングだけ、プロレスだけの試合は含めていません。</p>
    <h2>出典</h2>
    <p>各大会ページの下に、その大会の記録の出典を載せています。</p>
    <h2>間違いを見つけたら</h2>
    <p>記録の訂正は、出典（公式サイトや当時の記事など）を添えてお知らせください。確かめたうえで直します。</p>
    <p style="color:var(--fg3);font-size:13px">データ更新日：${esc(D.meta.built)}</p></div></main>`;
}
function notFound(){ return `<main class="wrap"><div class="sh"><h1>ページが見つかりません</h1></div><p class="note" style="margin-top:20px">リンクが古いか、まだ収録していない記録です。<a class="u" href="#top" style="color:var(--red2)">トップに戻る</a></p></main>`; }

function ticker(){
  const today = new Date().toISOString().slice(0,10);
  const ev = D.events.filter(e=>e[1]<=today).slice(-10).reverse();
  const items = ev.map(e=>{ const b=mainBout(e[0]); if(!b) return ''; const t = (b[5]===1||b[5]===2) ? `${b[5]===1?b[2]:b[4]} def. ${b[5]===1?b[4]:b[2]}` : `${b[2]} vs ${b[4]}`;
    return `<a href="#e-${esc(e[0])}"><i>${esc(dshort(e[1]))}</i>${esc(e[3])}　${esc(t)}${b[6]?'（'+esc(b[6])+'）':''}</a>`; }).join('');
  $('#ticker').innerHTML = `<div class="track">${items}${items}</div>`;
}

function route(){
  if(!ready){ $('#view').innerHTML = `<main class="wrap"><p class="loading">記録を読み込んでいます…</p></main>`; return; }
  const h = decodeURIComponent(location.hash.slice(1));
  let html, nav='';
  if(!h || h==='top') html = vTop();
  else if(h.startsWith('e-')) html = vEvent(h.slice(2));
  else if(h.startsWith('f-')) html = vFighter(h.slice(2));
  else if(h.startsWith('p-')) { html = vPromotion(h.slice(2)); nav='promotions'; }
  else if(h==='events'){ html = vEvents(); nav='events'; }
  else if(h==='fighters'){ html = vFighters(); nav='fighters'; }
  else if(h==='promotions'){ html = vPromotions(); nav='promotions'; }
  else if(h==='upcoming'){ html = vUpcoming(); nav='upcoming'; }
  else if(h==='about'){ html = vAbout(); nav='about'; }
  else if(h==='search'){ html = query ? vSearch() : vFighters(); }
  else html = notFound();
  if(h.startsWith('e-')) nav='events'; if(h.startsWith('f-')) nav='fighters';
  $('#view').innerHTML = html;
  if(h.startsWith('f-')) enhanceFighter(h.slice(2));
  document.querySelectorAll('[data-nav]').forEach(a=>{ if(a.dataset.nav===nav) a.setAttribute('aria-current','page'); else a.removeAttribute('aria-current'); });
  window.scrollTo(0,0);
}
function doSearch(q){ query = q.trim(); if(!query) return; if(location.hash==='#search') route(); else location.hash='search'; }
document.addEventListener('submit', ev=>{
  const f = ev.target; ev.preventDefault();
  if(f.id==='hform') doSearch($('#hq').value);
  if(f.id==='bform') doSearch($('#bq').value);
});
document.addEventListener('click', ev=>{
  const b = ev.target.closest('#ychips button'); if(b){ evYear = b.dataset.y; route(); }
});
let ft; document.addEventListener('input', ev=>{
  if(ev.target.id==='fq'){ clearTimeout(ft); const v=ev.target.value; ft=setTimeout(()=>{ $('#flist').innerHTML = v.trim()? fcards(searchFighters(v)) : fcards(topFighters().slice(0,120)); },180); }
});
window.addEventListener('hashchange', route);
route();
Promise.all(['events','bouts','fighters','meta','upcoming'].map(n=>fetch('data/'+n+'.json').then(r=>{ if(!r.ok) throw new Error(n); return r.json(); })))
  .then(([events,bouts,fighters,meta,upcoming])=>{ Object.assign(D,{events,bouts,fighters,meta,upcoming}); ready=true;
    $('#ftinfo').textContent = `${fmt(events.length)}興行・${fmt(events.reduce((s,e)=>s+e[6],0))}試合を収録　データ更新日 ${meta.built}　記録の出典は各大会ページに記載`;
    ticker();
    let q0 = ''; try { q0 = new URLSearchParams(location.search).get('q') || ''; } catch(e) {}
    if (q0) { query = q0.trim(); if (location.hash !== '#search') { location.hash = 'search'; return; } }
    route(); })
  .catch(()=>{ $('#view').innerHTML = `<main class="wrap"><p class="loading">記録を読み込めませんでした。ページを再読み込みしてください。</p></main>`; });
})();
