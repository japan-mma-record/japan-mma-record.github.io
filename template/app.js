(function(){
const $ = s => document.querySelector(s);
const esc = s => String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmt = n => n.toLocaleString('ja-JP');
const D = {}; let ready = false; let byFighter = null; let query = '';
const MARKS = {1989:'修斗 旗揚げ',1993:'パンクラス 旗揚げ',1997:'PRIDE.1',2001:'DEEP 旗揚げ',2015:'RIZIN 旗揚げ'};

function pl(p){ return (D.meta && D.meta.plabel[p]) || p; }
function pkey(p){ return 'p-' + p.replace(/_/g,'-'); }
function dshort(d){ return d ? d.slice(5).replace('-','.') : ''; }
function dlong(d){ if(!d) return ''; if(!/^\d{4}-\d{2}-\d{2}$/.test(d)) return /^\d{4}$/.test(d) ? `${d}年（日付不明）` : d; const [y,m,dd]=d.split('-'); const w='日月火水木金土'[new Date(+y,+m-1,+dd).getDay()]; return `${y}年${+m}月${+dd}日（${w}）`; }
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
function loadPodium(k){ if(!(D.meta.pd||[]).includes(k)) return;
  fetch('pd/'+encodeURIComponent(k)+'.json').then(r=>r.ok?r.json():null).then(ps=>{ const b=document.getElementById('pdbox'); if(!ps||!b) return;
    const PL={'1':'優勝','2':'準優勝','3':'3位'};
    b.innerHTML=`<h2 class="sec">入賞者</h2><div class="tbl"><table><thead><tr><th>階級</th><th>順位</th><th>選手</th><th>所属</th></tr></thead><tbody>${ps.map(p=>`<tr><td>${esc(p[0])}</td><td>${PL[p[1]]||esc(p[1])}</td><td>${esc(p[2])}</td><td>${esc(p[3])}</td></tr>`).join('')}</tbody></table></div>`; }); }
function teamTbl(k){ const ts=(D.meta.teams||{})[k]; if(!ts||!ts.length) return '';
  return `<h2 class="sec">出場チーム</h2><div class="tbl"><table><thead><tr><th>チーム</th><th>メンバー</th><th>成績</th></tr></thead><tbody>${ts.map(t=>`<tr><td>${esc(t[0])}</td><td>${esc(t[1])}</td><td>${esc(t[2])}</td></tr>`).join('')}</tbody></table></div>`; }
function mainCard(e){ if((D.meta.bjj||[]).includes(e[2])||((D.meta.teams||{})[e[0]]||[]).length) return '';
  const bs=D.bouts[e[0]]||[]; if(!bs.length) return '';
  const pool0=bs.filter(b=>!b[11]).length?bs.filter(b=>!b[11]):bs;
  const pool=pool0.map((b,i)=>[b,i]).sort((x,y)=>((x[0][0]||0)-(y[0][0]||0))||(x[1]-y[1])).map(x=>x[0]);
  const m=pool[pool.length-1], se=pool.length>2?pool[pool.length-2]:null;
  const t=pool.filter(b=>b!==m&&b!==se&&b[13]&&/タイトル|王座/.test(b[13])).pop();
  const one=b=>{ let A=b[2],B=b[4]; if(b[5]===2)[A,B]=[B,A]; return `${esc(A)} ${b[5]===1||b[5]===2?'def.':'vs'} ${esc(B)}${b[13]?`（${esc(b[13])}）`:''}`; };
  return `<span class="mc">メイン：${one(m)}${se?`<br>セミ：${one(se)}`:''}${t?`<br>${one(t)}`:''}</span>`; }
function vshort(v){ return (v||'').replace(/\s*[（(][^（）()]*[）)]\s*$/,'').replace(/^(?:東京都|北海道|(?:京都|大阪)府|.{2,3}県)\s*[・･]?\s*/,'').trim(); }
function evn(e){ const n=e[3]||'', v=vshort(e[4]); if(!v||(D.meta.world||[]).includes(e[2])||(D.meta.grappling||[]).includes(e[2])) return n;
  if(n.includes(v)||/[（(][^（）()]*[）)]$/.test(n)&&v.slice(0,2)&&n.includes(v.slice(0,2))) return n; return `${n}（${v}）`; }
function jpn(e){ if((D.meta.bjj||[]).includes(e[2])||!(e[7]&&e[7].length)) return ''; const a=e[7]; return `<span class="jp">（${a.slice(0,6).map(esc).join('、')}${a.length>6?`ほか${a.length-6}人`:''}）</span>`; }
function ttag(b){ return b[13] ? `<span class="ttl">${esc(b[13])}</span>${b[14]?`<span class="tnote">${esc(b[14])}</span>`:''}` : ''; }
function rtag(b,e){ return (b[11] && !(e&&(D.meta.standup||[]).includes(e[2])) ? `<span class="unc">${esc(b[11])}・戦績に数えない</span>` : '') + (b[12] ? ` <a class="vid" href="${esc(b[12])}" target="_blank" rel="noopener">▶ 公式動画</a>` : ''); }
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
      ${latest.map(e=>{ const bj=(D.meta.bjj||[]).includes(e[2]); const b=bj?null:mainBout(e[0]); return `<a class="res row" href="#e-${esc(e[0])}"><span class="dt">${esc(e[1].replace(/-/g,'.'))}</span><span class="ev"><small>${esc(pl(e[2]))}</small><b>${esc(evn(e))}</b></span><span class="mb">${bj?'':winnerLine(b)}</span><span class="mt">${esc(b?[b[6],rt(b)].filter(Boolean).join(' '):'')}</span></a>`; }).join('')}
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
/* 柔術の大会：トーナメント（カテゴリー・階級）ごとにまとめて見せる */
const BELTS=['白','灰','黄','オレンジ','緑','青','紫','茶','黒'];
const WTS=['ルースター','ライトフェザー','フェザー','ライト','ミドル','ミディアムヘビー','ヘビー','スーパーヘビー','ウルトラヘビー','オープンクラス','オープン','無差別','アブソルート'];
function bjjSplit(s){ s=(s||'').trim(); const m=s.match(new RegExp('^(.*?)((?:'+WTS.join('|')+')(?:級)?)$')); return m?[m[1].trim(),m[2]]:[s,'']; }
function bjjKey(cat,w){ return (cat+' '+w).trim(); }
function bjjOrd(cat,w){ const bi=BELTS.findIndex(x=>cat.includes(x+'帯')); const wi=WTS.findIndex(x=>w.startsWith(x)); return [/女子|女性|ウィメン/.test(cat)?1:0, bi<0?99:bi, cat, wi<0?99:wi]; }
function cmpArr(a,b){ for(let i=0;i<a.length;i++){ if(a[i]<b[i]) return -1; if(a[i]>b[i]) return 1; } return 0; }
function bjjView(k){
  const box=document.getElementById('bjjbox'); if(!box) return;
  const bs=D.bouts[k]||[];
  const go=ps=>{
    const div=new Map(); const known=new Set();
    const get=(cat,w)=>{ const key=bjjKey(cat,w); if(!div.has(key)) div.set(key,{cat,w,pd:[],bo:[]}); return div.get(key); };
    bs.forEach(b=>{ const raw=(b[9]||'').split('・')[0]; const kg=(raw.match(/（([^）]*kg[^）]*)）/)||[])[1]||''; const [cat,w]=bjjSplit(raw.replace(/（[^）]*）/g,'')); const d=get(cat,w); if(kg&&!d.kg) d.kg=kg; d.bo.push(b); });
    (ps||[]).forEach(p=>{ let cat,w; [cat,w]=bjjSplit((p[0]||'').replace(/（[^）]*）/g,'')); get(cat,w).pd.push(p); });
    const list=[...div.values()].sort((a,b)=>cmpArr(bjjOrd(a.cat,a.w),bjjOrd(b.cat,b.w)));
    const belts=[...new Set(list.map(d=>{const x=BELTS.find(x=>d.cat.includes(x+'帯'));return x||'その他';}))];
    const PL={'1':'優勝','2':'準優勝','3':'3位'};
    const card=d=>{ const b=BELTS.find(x=>d.cat.includes(x+'帯'))||'その他';
      const top=d.pd.filter(p=>p[1]==='1').map(p=>p[2]).join('・');
      const pod=d.pd.length?`<ol class="pod">${d.pd.map(p=>`<li><span class="pl p${esc(p[1])}">${PL[p[1]]||esc(p[1])}</span>${esc(p[2])}<span class="tm">${esc(p[3]||'')}</span></li>`).join('')}</ol>`:'';
      const mk=x=>{const m=(x[15]||'').match(/MAT(\d+)-(\d+)/);return m?[+m[1],+m[2]]:[99,x[0]||0];}; d.bo.sort((a,b)=>cmpArr(mk(a),mk(b)));
      const bo=d.bo.length?`<ul class="bres">${d.bo.map(x=>{ let A=[x[1],x[2]],B=[x[3],x[4]]; if(x[5]===2)[A,B]=[B,A]; const dec=(x[5]===1||x[5]===2);
        const ml=(x[15]||'').split('・'); return `<li>${ml[0]?`<span class="mn">${esc(ml[0])}</span>`:''}${dec?'<span class="rs w">WIN</span> ':''}${flink(A[0],A[1])} <span class="def">${dec?'def.':'vs'}</span> ${flink(B[0],B[1])}${x[6]?`<span class="bm">${esc(x[6])}</span>`:''}${ml[1]?`<span class="bm">${esc(ml[1])}</span>`:''}</li>`; }).join('')}</ul>`:'';
      const names=[...d.pd.map(p=>p[2]+' '+(p[3]||'')),...d.bo.map(x=>x[2]+' '+x[4])].join(' ');
      return `<details class="div" data-belt="${esc(b)}" data-q="${esc((d.cat+' '+d.w+' '+names).toLowerCase())}"><summary><span class="dn">${esc(d.cat)} <b>${esc(d.w)}</b>${d.kg?`<small>（${esc(d.kg)}）</small>`:''}</span><span class="dm">${top?'優勝 '+esc(top):''}${d.bo.length?`　${d.bo.length}試合`:''}</span></summary>${pod}${bo}</details>`; };
    box.innerHTML=`<h2 class="sec">トーナメント（${list.length}）</h2>
      <div class="bjjf"><input type="search" id="bjjq" placeholder="選手名・所属・階級で探す" aria-label="選手名・所属・階級で探す">
      <div class="chips" id="bjjb"><button type="button" data-b="" aria-pressed="true">すべての帯</button>${belts.map(b=>`<button type="button" data-b="${esc(b)}" aria-pressed="false">${esc(b)}${b==='その他'?'':'帯'}</button>`).join('')}</div>
      <button type="button" class="lnk" id="bjjall">すべて開く</button></div>
      <div id="bjjlist">${list.map(card).join('')}</div>`;
    let fb='';
    const apply=()=>{ const q=(document.getElementById('bjjq').value||'').trim().toLowerCase();
      document.querySelectorAll('#bjjlist details').forEach(el=>{ const ok=(!fb||el.dataset.belt===fb)&&(!q||el.dataset.q.includes(q)); el.hidden=!ok; if(q&&ok) el.open=true; }); };
    document.getElementById('bjjq').addEventListener('input',apply);
    document.getElementById('bjjb').addEventListener('click',ev=>{ const t=ev.target.closest('button'); if(!t) return; fb=t.dataset.b; document.querySelectorAll('#bjjb button').forEach(x=>x.setAttribute('aria-pressed',String(x===t))); apply(); });
    document.getElementById('bjjall').addEventListener('click',ev=>{ const els=[...document.querySelectorAll('#bjjlist details:not([hidden])')]; const open=!els.every(x=>x.open); els.forEach(x=>x.open=open); ev.target.textContent=open?'すべて閉じる':'すべて開く'; });
  };
  if((D.meta.pd||[]).includes(k)) fetch('pd/'+encodeURIComponent(k)+'.json').then(r=>r.ok?r.json():null).then(go).catch(()=>go(null)); else go(null);
}
/* 団体戦（QUINTETなど）：チームごとの対戦にまとめ、勝ち抜きの流れが見えるようにする */
const POS=['先鋒','次鋒','中堅','副将','大将','補欠'];
function qn(s){ return (s||'').replace(/[\s　・･“”"'’]/g,'').toLowerCase(); }
function teamView(k){
  const ts=(D.meta.teams||{})[k]; if(!ts||!ts.length) return '';
  const bs=D.bouts[k]||[];
  const teams=ts.map(t=>{ const raw=(t[1]||'').replace(/（[^）]*オーダー[^）]*）/g,''); const mem=[]; const re=new RegExp('('+POS.join('|')+')','g'); const parts=raw.split(re); for(let i=1;i<parts.length;i+=2){ const n=(parts[i+1]||'').replace(/^[・\s]+|[・\s]+$/g,''); if(n) mem.push([parts[i],n]); } return {name:t[0],res:t[2]||'',mem}; });
  const who=new Map(); teams.forEach((t,i)=>t.mem.forEach(m=>who.set(qn(m[1]),i)));
  const tOf=n=>{ const q=qn(n); if(who.has(q)) return who.get(q); for(const [key,i] of who){ if(key.length>2&&(q.includes(key)||key.includes(q))) return i; } return -1; };
  const indiv=[], groups=[];
  bs.forEach(b=>{ if(/個人戦|ワンマッチ|スーパーファイト/.test(b[9]||'')){ indiv.push(b); return; }
    let a=tOf(b[2]), c=tOf(b[4]); const g=groups[groups.length-1];
    if(g&&((a<0&&c<0)||((a<0||g.t.includes(a))&&(c<0||g.t.includes(c))))){ g.b.push(b); return; }
    if(a<0||c<0||a===c){ if(g){ g.b.push(b); return; } }
    groups.push({t:[a,c],b:[b]}); });
  const n=groups.length, stage=i=> n===3?(i<2?'1回戦':'決勝'): n===7?(i<4?'1回戦':i<6?'準決勝':'決勝'): n===1?'決勝':`第${i+1}試合`;
  const ord=['優勝','準優勝','3位','1回戦敗退'];
  const rank=t=>{const i=ord.findIndex(x=>t.res.startsWith(x)); return i<0?9:i;};
  const tcards=teams.slice().sort((a,b)=>rank(a)-rank(b)).map(t=>`<div class="tcard"><p class="tn"><b>${esc(t.name)}</b>${t.res?`<span class="tr r${rank(t)}">${esc(t.res)}</span>`:''}</p><ol>${t.mem.map(m=>`<li><span class="ps">${esc(m[0])}</span>${esc(m[1])}</li>`).join('')}</ol></div>`).join('');
  const side=(b,ti)=>{ const a=tOf(b[2]); return (a===ti||(a<0&&tOf(b[4])!==ti))?1:2; };
  const gtbl=(g,i)=>{ const [L,R]=g.t; const LN=teams[L]?teams[L].name:'', RN=teams[R]?teams[R].name:'';
    const last=g.b[g.b.length-1]; let win='';
    if(last&&(last[5]===1||last[5]===2)){ const ws=last[5]===1?tOf(last[2]):tOf(last[4]); if(ws>=0) win=teams[ws].name; }
    if(!win){ const st=stage(i); const adv=[L,R].filter(x=>teams[x]&&(st==='決勝'?/^優勝/.test(teams[x].res):!/敗退/.test(teams[x].res))); if(adv.length===1) win=teams[adv[0]].name; }
    const rows=g.b.map((b,j)=>{ const s1=side(b,L); const lf=s1===1?[b[1],b[2]]:[b[3],b[4]], rf=s1===1?[b[3],b[4]]:[b[1],b[2]]; const lw=(b[5]===1&&s1===1)||(b[5]===2&&s1===2), rw=(b[5]===1&&s1===2)||(b[5]===2&&s1===1);
      const mk=w=>w?'<span class="rs w">勝</span>':(b[5]==='d'?'<span class="rs o">分</span>':(b[5]===1||b[5]===2)?'<span class="rs l">負</span>':'');
      return `<tr><td class="num">${j+1}</td><td class="ql">${flink(lf[0],lf[1])} ${mk(lw)}</td><td class="qm">${esc(b[6]||'')}${b[8]?`<br><small>${esc(b[8])}</small>`:''}</td><td class="qr">${mk(rw)} ${flink(rf[0],rf[1])}</td></tr>`; }).join('');
    return `<div class="qmatch"><p class="qh"><span class="qs">${esc(stage(i))}</span><b>${esc(LN)}</b> <span class="def">vs</span> <b>${esc(RN)}</b>${win?`<span class="qw">${stage(i)==='決勝'?'優勝':'勝ち上がり'}：${esc(win)}</span>`:''}</p>
      <div class="tbl"><table><thead><tr><th class="num">#</th><th class="ql">${esc(LN)}</th><th class="qm">決まり手・時間</th><th class="qr">${esc(RN)}</th></tr></thead><tbody>${rows}</tbody></table></div></div>`; };
  const ind=indiv.length?`<h2 class="sec">個人戦・ワンマッチ</h2><div class="tbl"><table><thead><tr><th>勝者</th><th>相手</th><th>決まり手</th><th class="num">時間</th></tr></thead><tbody>${indiv.map(b=>{ let A=[b[1],b[2]],B=[b[3],b[4]]; if(b[5]===2)[A,B]=[B,A]; return `<tr><td>${flink(A[0],A[1])}${b[5]==='d'?' <span class="def">vs</span>':''}</td><td>${flink(B[0],B[1])}</td><td>${esc(b[6]||'')}</td><td class="num">${esc(b[8]||'')}</td></tr>`; }).join('')}</tbody></table></div>`:'';
  return `<h2 class="sec">出場チーム</h2><p class="sub" style="font-size:13px;margin:0 0 10px">5人ずつの勝ち抜き戦。引き分けは両者とも退場です（オーダーは初戦のもの）</p><div class="tgrid">${tcards}</div>
    <h2 class="sec">団体戦</h2>${groups.map(gtbl).join('')}${ind}`;
}
/* 階級別トーナメントの大会（アマチュア修斗など）：階級ごとにまとめる */
function tourView(k){
  const bs=D.bouts[k]||[]; const g=new Map();
  bs.forEach(b=>{ const w=((b[9]||'').split('・')[0]||'').trim()||'階級の記録なし'; if(!g.has(w)) g.set(w,[]); g.get(w).push(b); });
  // 階級の記録がない試合は、対戦でつながっている選手のまとまり（＝1つのトーナメント）ごとに分ける
  const un=g.get('階級の記録なし');
  if(un){ g.delete('階級の記録なし'); const par={}; const f=x=>{ while(par[x]!==x){ par[x]=par[par[x]]; x=par[x]; } return x; };
    un.forEach(b=>{ for(const n of [b[2],b[4]]) if(!(n in par)) par[n]=n; par[f(b[2])]=f(b[4]); });
    const comp=new Map(); un.forEach(b=>{ const r=f(b[2]); if(!comp.has(r)) comp.set(r,[]); comp.get(r).push(b); });
    let i=0; [...comp.values()].sort((a,b)=>b.length-a.length).forEach(bl=>{ i++; g.set(bl.length>1?`トーナメント${i}（階級の記録なし）`:`ワンマッチ${i}（階級の記録なし）`, bl); }); }
  const CL=['ミニマム','アトム','スーパーアトム','ストロー','フライ','バンタム','フェザー','ライト','ウェルター','ミドル','ライトヘビー','クルーザー','ヘビー','無差別'];
  const ord=w=>{ const t=w.replace(/^女子/,''); let i=-1,L=0; CL.forEach((x,j)=>{ if(t.startsWith(x)&&x.length>L){i=j;L=x.length;} }); return [/女子/.test(w)?1:0, i<0?(/階級の記録なし/.test(w)?999:98):i, /トーナメント(\d+)/.test(w)?+w.match(/トーナメント(\d+)/)[1]:/ワンマッチ/.test(w)?1000:0, w]; };
  const list=[...g.entries()].sort((a,b)=>cmpArr(ord(a[0]),ord(b[0])));
  const card=([w,bl])=>{ bl=bl.slice().sort((a,b)=>(a[0]||0)-(b[0]||0)); let champ=''; if(bl.length>1){ const W={},L={}; bl.forEach(x=>{ if(x[5]===1||x[5]===2){ const a=x[5]===1?x[2]:x[4], b=x[5]===1?x[4]:x[2]; W[a]=(W[a]||0)+1; L[b]=1; } });
      const c=Object.entries(W).filter(([n])=>!L[n]).sort((a,b)=>b[1]-a[1]); if(c.length===1||(c.length>1&&c[0][1]>c[1][1])) champ=c[0][0]; }
    const names=bl.map(x=>x[2]+' '+x[4]).join(' ');
    return `<details class="div" data-belt="" data-q="${esc((w+' '+names).toLowerCase())}"><summary><span class="dn"><b>${esc(w)}</b></span><span class="dm">${champ?'優勝 '+esc(champ)+'　':''}${bl.length}試合</span></summary><ul class="bres">${bl.map(x=>{ let A=[x[1],x[2]],B=[x[3],x[4]]; if(x[5]===2)[A,B]=[B,A]; const dec=(x[5]===1||x[5]===2);
      return `<li>${x[0]?`<span class="mn">第${x[0]}試合</span>`:''}${dec?'<span class="rs w">WIN</span> ':''}${flink(A[0],A[1])} <span class="def">${dec?'def.':'vs'}</span> ${flink(B[0],B[1])}${x[6]?`<span class="bm">${esc(x[6])}</span>`:''}${rt(x)?`<span class="bm">${esc(rt(x))}</span>`:''}</li>`; }).join('')}</ul></details>`; };
  return `<h2 class="sec">階級別トーナメント（${list.length}）</h2><div class="bjjf"><input type="search" id="tq" placeholder="選手名・階級で探す" aria-label="選手名・階級で探す" oninput="const q=this.value.trim().toLowerCase();document.querySelectorAll('#tlist details').forEach(el=>{const ok=!q||el.dataset.q.includes(q);el.hidden=!ok;if(q&&ok)el.open=true;})"><button type="button" class="lnk" onclick="const els=[...document.querySelectorAll('#tlist details:not([hidden])')];const o=!els.every(x=>x.open);els.forEach(x=>x.open=o);this.textContent=o?'すべて閉じる':'すべて開く'">すべて開く</button></div><div id="tlist">${list.map(card).join('')}</div>`;
}
function vEvent(k){
  const e = D.events.find(x=>x[0]===k); if(!e) return notFound();
  if((D.meta.amateur||[]).includes(e[2])&&/選手権|トーナメント|大会/.test(e[3])&&(D.bouts[k]||[]).length>=12) return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a>　›　${esc(e[1].slice(0,4))}年</p>
    <div class="ph"><div><a class="badge" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a><h1>${esc(e[3])}</h1><p class="sub">${esc(dlong(e[1]))}${e[4]?'　'+esc(e[4]):''}</p></div></div>
    ${tourView(k)}<p class="src">出典：${[...new Set(e[5])].map(u=>/^https?:/.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,'').slice(0,70))}</a>`:esc(u)).join('　')}</p></main>`;
  if(((D.meta.teams||{})[k]||[]).length) return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a>　›　${esc(e[1].slice(0,4))}年</p>
    <div class="ph"><div><a class="badge" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a><h1>${esc(e[3])}</h1><p class="sub">${esc(dlong(e[1]))}${e[4]?'　'+esc(e[4]):''}</p></div></div>
    ${teamView(k)}<p class="src">出典：${[...new Set(e[5])].map(u=>/^https?:/.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,'').slice(0,70))}</a>`:esc(u)).join('　')}</p></main>`;
  if((D.meta.bjj||[]).includes(e[2])) return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a>　›　${esc(e[1].slice(0,4))}年</p>
    <div class="ph"><div><a class="badge" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a><h1>${esc(e[3])}</h1><p class="sub">${esc(dlong(e[1]))}${e[4]?'　'+esc(e[4]):''}</p></div></div>
    <div id="bjjbox"><p class="sub">読み込み中…</p></div><p class="src">出典：${[...new Set(e[5])].map(u=>/^https?:/.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc(u.replace(/^https?:\/\//,'').slice(0,70))}</a>`:esc(u)).join('　')}</p></main>`;
  const bs = D.bouts[k] || [];
  const su=(D.meta.standup||[]).includes(e[2]); const mb = su ? bs : bs.filter(b=>!b[11]); const ko = mb.filter(b=>/^T?KO/.test(b[6])).length, sub = mb.filter(b=>/^一本|^Submission/.test(b[6])).length, dec = mb.filter(b=>/^判定/.test(b[6])).length;
  const rows = bs.map(b=>{
    let A=[b[1],b[2]], B=[b[3],b[4]], r='<span class="rs o">—</span>';
    if(b[5]===2){ [A,B]=[B,A]; }
    if(b[5]===1||b[5]===2) r='<span class="rs w">WIN</span>'; else if(b[5]==='d') r='<span class="rs o">引分</span>'; else if(b[5]==='nc') r='<span class="rs o">無効</span>';
    return `<tr><td class="num">${b[0]||''}</td><td>${r}</td><td>${flink(A[0],A[1])}</td><td><span class="def">${(b[5]===1||b[5]===2)?'def.':'vs'}</span> ${flink(B[0],B[1])}${b[10]?'<span class="unc">未確定</span>':''}</td><td>${esc(b[6])}${rtag(b,e)}</td><td class="num">${esc(rt(b))}</td><td>${ttag(b)}${esc(b[9])}</td></tr>`; }).join('');
  return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a>　›　${esc(e[1].slice(0,4))}年</p>
    <div class="ph"><div><a class="badge" href="#${pkey(e[2])}">${esc(pl(e[2]))}</a><h1>${esc(e[3])}</h1><p class="sub">${esc(dlong(e[1]))}${e[4]?'　'+esc(e[4]):''}</p></div>
    <div class="kpis"><div><p class="k">試合</p><p class="v">${mb.length}</p></div><div><p class="k">KO・TKO</p><p class="v r">${ko}</p></div><div><p class="k">一本</p><p class="v">${sub}</p></div><div><p class="k">判定</p><p class="v">${dec}</p></div></div></div>
    <div class="tbl"><table><thead><tr><th class="num">No.</th><th>結果</th><th>勝者</th><th>対戦相手</th><th>決まり手</th><th class="num">R・時間</th><th>階級・ルール</th></tr></thead><tbody>${rows}</tbody></table></div>
    ${teamTbl(k)}<div id="pdbox"></div><p class="src">出典：${e[5].length?e[5].map(u=>/^https?:/.test(u)?`<a href="${esc(u)}" target="_blank" rel="noopener">${esc((()=>{try{return decodeURIComponent(u)}catch(e){return u}})().replace(/^https?:\/\//,'').slice(0,70))}</a>`:esc(u)).join('　'):''}</p></main>`;
}
function kickRows(id,list){ const o=((D.meta.other||{})[id]||[]).filter(r=>/キック|ムエタイ|シュートボクシング|K-1/.test(r[7]));
  const s=(list||[]).filter(([e,b])=>/キック|ムエタイ|ボクシング/.test(b[11]||'')&&!/^ボクシング$/.test(b[11]||'')); return {o,s}; }
function kickBox(id,list){ const {o,s}=kickRows(id,list); if(!o.length&&!s.length) return ''; let w=0,l=0,d=0;
  o.forEach(r=>{ if(r[3]==='勝')w++; else if(r[3]==='敗')l++; else if(r[3]==='分')d++; });
  s.forEach(([e,b,side])=>{ if(b[5]===side)w++; else if(b[5]===1||b[5]===2)l++; else if(b[5]==='d')d++; });
  return `<div class="kbox"><p class="kh">キック戦績</p><div class="kpis"><div><p class="k">勝</p><p class="v r">${w}</p></div><div><p class="k">敗</p><p class="v">${l}</p></div><div><p class="k">分</p><p class="v">${d}</p></div></div></div>`; }
function kickTbl(id){ const o=((D.meta.other||{})[id]||[]); if(!o.length) return '';
  return `<h2 class="sec">キックの試合（このサイトの大会以外）</h2><div class="tbl"><table><thead><tr><th>結果</th><th>対戦相手</th><th>大会</th><th class="num">日付</th><th>決まり手</th></tr></thead><tbody>${o.map(r=>`<tr><td>${r[3]==='勝'?'<span class="rs w">勝</span>':r[3]==='敗'?'<span class="rs l">負</span>':`<span class="rs o">${esc(r[3])}</span>`}</td><td>${esc(r[2])}</td><td>${r[8]?`<a class="u" href="${esc(r[8])}" target="_blank" rel="noopener">${esc(r[1])}</a>`:esc(r[1])}</td><td class="num">${esc(r[0].replace(/-/g,'.'))}</td><td>${esc(r[4])}${r[5]?` ${esc(r[5])}R`:''}${r[6]?` ${esc(r[6])}`:''}</td></tr>`).join('')}</tbody></table></div><h2 class="sec">全試合</h2>`; }
function vFighter(id){
  const f = D.fighters[id]; if(!f) return notFound(); buildIndex();
  const list = (byFighter[id]||[]).slice().sort((a,b)=> b[0][1].localeCompare(a[0][1]) || b[1][0]-a[1][0]);
  let w=0,l=0,d=0,nc=0; const pr = new Set();
  const rows = list.map(([e,b,side])=>{ pr.add(e[2]);
    const opp = side===1 ? [b[3],b[4]] : [b[1],b[2]];
    let r='<span class="rs o">—</span>';
    const cnt = !b[11];
    if(b[5]===side){cnt&&w++; r='<span class="rs w">勝</span>';} else if(b[5]===1||b[5]===2){cnt&&l++; r='<span class="rs l">負</span>';} else if(b[5]==='d'){cnt&&d++; r='<span class="rs o">分</span>';} else if(b[5]==='nc'){cnt&&nc++; r='<span class="rs o">無効</span>';}
    return `<tr data-d="${esc(e[1])}"><td>${r}</td><td>${flink(opp[0],opp[1])}</td><td><a class="u" href="#e-${esc(e[0])}">${esc(evn(e))}</a></td><td class="num">${esc(e[1].replace(/-/g,'.'))}</td><td>${ttag(b)}${esc(b[6])}${rtag(b)}${b[10]?'<span class="unc">未確定</span>':''}</td><td class="num">${esc(rt(b))}</td></tr>`; }).join('');
  const tl = list.filter(([e,b])=>b[13]).slice().reverse();
  const tbox = tl.length ? `<h2 class="sec">タイトル戦（${tl.length}）</h2><div class="tbl"><table><thead><tr><th>結果</th><th>試合</th><th>対戦相手</th><th>大会</th><th class="num">日付</th></tr></thead><tbody>${tl.map(([e,b,side])=>{ const opp = side===1?[b[3],b[4]]:[b[1],b[2]]; const r = b[5]===side?'<span class="rs w">勝</span>':(b[5]===1||b[5]===2)?'<span class="rs l">負</span>':'<span class="rs o">分</span>';
    return `<tr><td>${r}</td><td>${ttag(b)}</td><td>${flink(opp[0],opp[1])}</td><td><a class="u" href="#e-${esc(e[0])}">${esc(evn(e))}</a></td><td class="num">${esc(e[1].replace(/-/g,'.'))}</td></tr>`; }).join('')}</tbody></table></div><h2 class="sec">全試合</h2>` : '';
  const nm = f[0] || f[1];
  const span = list.length ? `${list[list.length-1][0][1].slice(0,4)}年〜${list[0][0][1].slice(0,4)}年` : '';
  const st = '';
  return `<main class="wrap"><p class="crumb"><a class="lnk" href="#top">トップ</a>　›　<a class="lnk" href="#fighters">選手</a></p>
    <div class="ph"><div>${f[0]?`<p class="sub" style="margin:0;letter-spacing:.08em">${esc(f[1])}</p>`:''}<h1>${esc(nm)}</h1><p class="sub">${esc([...pr].map(pl).join('・'))}</p></div>
    <div class="kboxes">${kickBox(id,list)}<div class="kbox"><p class="kh" id="fkh">MMA戦績</p><div class="kpis" id="fk"><div><p class="k">勝</p><p class="v r">${w}</p></div><div><p class="k">敗</p><p class="v">${l}</p></div><div><p class="k">分</p><p class="v">${d}</p></div>${nc?`<div><p class="k">無効</p><p class="v">${nc}</p></div>`:''}</div></div></div></div>
    <p class="sub" id="fnote" style="font-size:13px;color:var(--fg3)">収録${list.length}試合（${esc(span)}）　${esc(st)}　※日本で開かれた大会・日本の団体の大会と、世界の主要団体（UFC・ONE・PFL・Bellatorなど）での試合の戦績です。そのほかの海外の大会での試合は含みません</p>
    ${tbox}${kickTbl(id)}<div class="tbl"><table><thead><tr><th>結果</th><th>対戦相手</th><th>大会</th><th class="num">日付</th><th>決まり手</th><th class="num">R・時間</th></tr></thead><tbody id="fb">${rows}</tbody></table></div></main>`;
}
function enhanceFighter(id){
  fetch('w/'+encodeURIComponent(id)+'.json').then(r=>r.ok?r.json():null).then(w=>{
    if(!w || location.hash!=='#f-'+id) return;
    const k=document.getElementById('fk'), n=document.getElementById('fnote'), tb=document.getElementById('fb'); if(!k||!tb) return;
    const [W,L,Dr,NC]=w.rec;
    { const h=document.getElementById('fkh'); if(h) h.textContent='MMA戦績（海外を含む通算）'; } k.innerHTML=`<div><p class="k">勝</p><p class="v r">${W}</p></div><div><p class="k">敗</p><p class="v">${L}</p></div><div><p class="k">分</p><p class="v">${Dr}</p></div>${NC?`<div><p class="k">無効</p><p class="v">${NC}</p></div>`:''}`;
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
    out += `<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].length===10?e[1].slice(5).replace('-','.'):'—')}</span><span class="p">${esc(pl(e[2]))}</span><span class="n">${esc(evn(e))}${jpn(e)}${mainCard(e)}</span><span class="c">${e[6]}試合</span></a>`; });
  return `<main class="wrap"><div class="sh"><h1>大会</h1><span class="aside" style="font-weight:500">${esc(evYear)}年　${ev.length}大会</span></div>
    <div class="chips" id="ychips">${years.map(y=>`<button type="button" data-y="${y}" aria-pressed="${y===evYear}">${y}</button>`).join('')}</div>
    <div class="list">${out}</div></main>`;
}
function vPromotions(){
  const all = promoStats(), by = Object.fromEntries(all.map(p=>[p.k,p]));
  const W = (D.meta.world||[]).filter(k=>by[k]), G = (D.meta.grappling||[]).filter(k=>by[k]), F = (D.meta.first||[]).filter(k=>by[k]), B = (D.meta.bjj||[]).filter(k=>by[k]), S = (D.meta.standup||[]).filter(k=>by[k]), A = (D.meta.amateur||[]).filter(k=>by[k]);
  const other = new Set([...W,...G,...F,...B,...S,...A]);
  const JP = [...F.map(k=>by[k]), ...all.filter(p=>!other.has(p.k)).sort((a,b)=>b.n-a.n)];
  const card = p=>`<a href="#${pkey(p.k)}"><b>${esc(pl(p.k))}</b><span>${p.a}–${p.b}年　${fmt(p.n)}大会・${fmt(p.bo)}試合</span></a>`;
  const sec = (t,arr,note)=> arr.length ? `<h2 class="sec">${t}</h2>${note?`<p class="sub" style="font-size:13px;margin:0 0 10px">${note}</p>`:''}<div class="pgrid">${arr.map(card).join('')}</div>` : '';
  return `<main class="wrap"><div class="sh"><h1>団体</h1><span class="aside" style="font-weight:500">${all.length}団体</span></div>
    ${(()=>{ const cy=new Date().getFullYear(); const act=JP.filter(p=>p.b>=cy-1), past=JP.filter(p=>p.b<cy-1).sort((a,b)=>b.b-a.b||b.n-a.n);
      return sec('日本の団体（活動中）', act, `${cy-1}年以降に大会を開いている団体`)+sec('日本の団体（過去の団体）', past, `最後の大会が${cy-2}年以前の団体。最後の大会が新しい順`); })()}
    ${sec('世界の主要団体', W.map(k=>by[k]), '日本人選手が出た試合と、日本で開かれた大会の試合です')}
    ${sec('アマチュア', A.map(k=>by[k]))}
    ${sec('立ち技', S.map(k=>by[k]), 'MMAの戦績には数えません')}
    ${sec('グラップリング', G.map(k=>by[k]), 'MMAの戦績には数えません')}
    ${sec('ブラジリアン柔術', B.map(k=>by[k]), '大人の部の入賞者と、トーナメント表が残っている大会の試合です。MMAの戦績には数えません')}</main>`;
}
function vPromotion(key){
  const p = Object.keys(D.meta.plabel).find(k=>k.replace(/_/g,'-')===key); if(!p) return notFound();
  const ev = D.events.filter(e=>e[2]===p).slice().reverse();
  let cur='', out='';
  ev.forEach(e=>{ const y=e[1].slice(0,4); if(y!==cur){ cur=y; out+=`<p class="mo">${y}</p>`; }
    out += `<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].length===10?e[1].slice(5).replace('-','.'):'—')}</span><span class="n">${esc(evn(e))}${jpn(e)}${mainCard(e)}</span><span class="c">${e[6]}試合</span></a>`; });
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
    <h2 class="mo" style="margin-top:36px">大会</h2><div class="list">${es.map(e=>`<a class="row" href="#e-${esc(e[0])}"><span class="d">${esc(e[1].replace(/-/g,'.').slice(2))}</span><span class="p">${esc(pl(e[2]))}</span><span class="n">${esc(evn(e))}</span><span class="c">${e[6]}試合</span></a>`).join('')||'<p class="note">該当する大会はありません。</p>'}</div></main>`;
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
  const ev = D.events.filter(e=>e[1]<=today&&!(D.meta.bjj||[]).includes(e[2])).slice(-10).reverse();
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
  if(h.startsWith('e-')){ const ek=h.slice(2), ee=D.events.find(x=>x[0]===ek); if(ee&&(D.meta.bjj||[]).includes(ee[2])) bjjView(ek); else loadPodium(ek); }
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
