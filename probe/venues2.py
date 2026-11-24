import json,re,time,urllib.request,html
items=json.load(open('probe/vurls.json'))
out=open('probe/venues5.tsv','w')
import urllib.parse
def text(u):
    u=urllib.parse.quote(u,safe=':/?&=%#+~@!$,;')
    req=urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0','Accept-Language':'ja'})
    raw=urllib.request.urlopen(req,timeout=40).read()
    m=re.search(rb'charset=["\']?([\w-]+)',raw[:4000],re.I); cs=(m.group(1).decode() if m else 'utf-8').lower()
    cs={'shift_jis':'cp932','x-sjis':'cp932','sjis':'cp932','euc-jp':'euc_jp'}.get(cs,cs)
    t=raw.decode(cs,'replace')
    t=re.sub(r'(?is)<(script|style)[^>]*>.*?</\1>',' ',t); t=re.sub(r'(?i)<br\s*/?>|</(p|div|li|h\d|tr|td)>','\n',t); t=re.sub(r'<[^>]+>',' ',t)
    return [re.sub(r'[ \t　]+',' ',html.unescape(l)).strip() for l in t.split('\n') if l.strip()]
for it in items:
    y,mo,d=it['date'].split('-'); mo=int(mo); d=int(d)
    found=[]
    for u in it['urls']:
        try: L=text(u)
        except Exception as e: found.append('ERR '+str(e)[:60]); continue
        for i,l in enumerate(L):
            if re.search(r'(会\s*場|場\s*所)\s*[：:］】]', l) and len(l)<120: found.append(l)
            if re.fullmatch(r'[［【]?(会\s*場|開催場所|場所)[］】]?', l) and i+1<len(L): found.append('会場：'+L[i+1][:80])
            if re.search(rf'{y}年\s*0?{mo}月\s*0?{d}日', l) and len(l)<140: found.append(l+' || '+(L[i+1] if i+1<len(L) else '')[:80])
        if found: break
        time.sleep(1)
    out.write(it['id']+'\t'+it['date']+'\t'+it['name']+'\t'+' ## '.join(dict.fromkeys(found))[:600]+'\n'); out.flush()
    time.sleep(1)
