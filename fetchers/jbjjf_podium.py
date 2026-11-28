"""JBJJF 公式サイトの結果記事（www.jbjjf.com/YYYY/MM/NNNN/）から入賞者を読み取る。

使い方: python3 fetchers/jbjjf_podium.py 保存した記事.html
  → 区分・順位（1/2/3）・名前（日本語）・名前（ローマ字）・所属・参加人数 をタブ区切りで出す。
読める書き方:
- 1998〜2006年:「■白帯アダルト」「・ガロ級/12名参加」「優勝　名前(所属)」（区分名は「白帯アダルト ガロ級」）
- 2007〜2012年:「アダルト白帯ブルーマ級(5人参加)」「優勝　名前 Romaji (所属)」「三位」「３位」
- 2009〜2011年の東京国際:「Adult White Galo」「1st Name(Team)」
- 2013年以降:「優　勝　名前  (所属)」、英語の区分名（「Master1 White … (Total:1)」）は直前の日本語の区分名を使う
アカデミー表彰・団体成績の行、「空位」、名前が空の行は入れない。
公式ページの誤記（括弧の抜け、名前と所属がくっついたもの）はそのまま残ることがあるので、data/podium.tsv に入れる前に目で確かめる。
2026年11月に、1998〜2026年の全結果記事（731件）を data/podium.tsv と突き合わせるのに使った。
"""
import re,unicodedata
PLM=re.compile(r'^※?\s*(優\s*勝|準\s*優\s*勝|(?:第?\s*[3３三]\s*位)|[1-2１２]\s*位)\s*(?:[\(（](不戦勝|不戦|棄権|[^)）]{0,6})[\)）])?[\s　:：]*(.*)$')
JP=re.compile(r'[぀-ヿ一-鿿々]')
def N(s): return unicodedata.normalize('NFKC',s or '')
def split_name(s):
    s=s.strip()
    if JP.search(s):
        toks=re.split(r'(\s+)',s)
        # find first latin token after some JP
        parts=s.split()
        for i,t in enumerate(parts):
            if i>0 and re.fullmatch(r"[A-Za-z][A-Za-z.'\-]*",t) and all(re.fullmatch(r"[A-Za-z][A-Za-z.'\-,]*",x) for x in parts[i:]):
                # keep original spacing of jp part
                jp_part=s[:s.find(t, len(' '.join(parts[:i])) )].rstrip()
                return jp_part,' '.join(parts[i:])
        return s,''
    return '',s

def nt(rest):
    rest=rest.split('\t')[0].strip(' 　')
    if ' – ' in rest and '(' not in rest and '（' not in rest:
        a,b=rest.split(' – ',1); return a.strip(),b.strip()
    mm=re.match(r'^(.*?)[\s　]*[\(（]+([^()（）]*)[\)）]?\s*$',rest)
    if mm and mm.group(1).strip(' 　'):
        return mm.group(1).strip(' 　（('),mm.group(2).strip(' 　')
    m2=re.match(r'^(.*[぀-ヿ一-鿿々].*?\s+[A-Za-z][A-Za-z .\'\-]*[a-z])([^A-Za-z\s.].*?)[)）]$',rest)
    if m2: return m2.group(1).strip(),m2.group(2).strip()
    if '\u3000' in rest:
        left,right=rest.rsplit('\u3000',1)
        if re.search(r'[A-Za-z]$',left.strip()) and right.strip(): return left.strip(),right.strip(' )）')
    return rest.rstrip(')）'),''
def parse(lines):
    L2=[]
    for l in lines:
        L2.extend(x for x in re.split(r'(?<=[)）級])[\s　]*(?=(?:優\s*勝|準\s*優\s*勝|[3３]\s*位))', l) if x.strip())
    lines=L2
    out=[];sec='';div=None;ent='';skip=False;last_was_div=False
    for l in lines:
        prev_div=last_was_div; last_was_div=False
        if l.startswith('修正・訂正'): break
        if l.startswith(('試合動画','大会ギャラリー','大会レポート')): continue
        n=N(l).strip()
        me=re.match(r'^[※*]?\s*(1st|2nd|3rd)\s+(.*)$',n)
        if me:
            if skip or div is None: continue
            rest=re.sub(r'^[※*]?\s*(1st|2nd|3rd)\s+','',l.strip()).split('\t')[0]
            name,team=nt(rest)
            ja,en=split_name(name.lstrip('※*'))
            out.append([div,{'1st':'1','2nd':'2','3rd':'3'}[me.group(1)],ja,en,team,'']); continue
        if re.match(r'^(Adult|Master|Senior\s*\d?|Junior|Juvenile|Juvenil|Teen|Female|Women|Kids?|Infant\w*|Mirim|Pre\w*)\b',n) and re.search(r'(Galo|Pluma|Pena|Leve|Medio|Pesad\w*|Absolut\w*|Rooster|Light|Feather|Middle|Heavy|Open|kg)\s*(\(\d+\)|\(\s*Total\s*:\s*\d+\s*\))?$',n,re.I):
            et=re.search(r'Total\s*:\s*(\d+)',n,re.I)
            if div and JP.search(div) and prev_div:
                ent=et.group(1) if et else ent; continue
            div=l.strip(); skip=False; ent=et.group(1) if et else ''; last_was_div=True; continue
        m=PLM.match(n)
        if m and not n.startswith('団体'):
            if skip or div is None: continue
            pl={'優勝':'1','準優勝':'2','1位':'1','2位':'2'}.get(re.sub(r'\s','',m.group(1)),'3')
            # use original string for name/team
            o=l.strip()
            mo=re.match(r'^※?\s*(?:優\s*勝|準\s*優\s*勝|(?:第?\s*[3３三]\s*位)|[1-2１２]\s*位)\s*(?:[\(（][^)）]{0,6}[\)）])?[\s　:：]*(.*)$',o)
            rest=mo.group(1) if mo else m.group(3)
            rest=rest.split('\t')[0]
            name,team=nt(rest)
            team=team.lstrip("’'‘ ")
            if not name.strip(' 　※') or name.strip(' 　') in ('空位','該当者なし','なし','-'): continue
            name=name.lstrip('※＊* 　')
            ja,en=split_name(name)
            out.append([div,pl,ja,en,team,ent])
            continue
        if re.match(r'(アカデミー表彰|団体成績|団体優勝|団体戦|チーム)',n) or (len(n)<20 and re.search(r'団体成績|アカデミー表彰|団体優勝',n)): skip=True; div=None; continue
        if n.startswith('■') and not re.search(r'級|クラス|kg|アブソルート|無差別|\d+\s*名|名参加',n):
            sec=l.strip().lstrip('■').strip(); div=None; skip=False; continue
        if n.startswith('■'): l=l.strip().lstrip('■'); n=n.lstrip('■')
        if n.startswith('・') and len(n)<70 and not PLM.match(n.lstrip('・')):
            l=l.strip()
            e=re.search(r'(\d+)\s*[名人]',n); ent=e.group(1) if e else ''
            d=re.sub(r'[\s　]*[/／]?\s*[\d０-９]+\s*[名人].*$','',l).strip()
            div=(sec+' '+d.lstrip('・').strip()).strip() if sec else d.lstrip('・').strip(); skip=False; continue
        if re.search(r'トーナメント|選手権|杯|CUP|Cup|Tournament|TOURNAMENT|Championship|CHAMPIONSHIP',n) and not re.search(r'級|帯|kg|KG',n):
            div=None; continue
        if (re.search(r'級|クラス|kg|KG|無差別|アブソルート|オープン|エントリー|名参加',n) or re.search(r'\(\d+\)$',n)) and len(n)<70 and not n.startswith('※'):
            e=re.search(r'(\d+)\s*[名人]\s*参加',n) or re.search(r'エントリー\s*(?:人数)?\s*(\d+)\s*[名人]?',n) or re.search(r'\((\d+)\)$',n)
            ent=e.group(1) if e else ''
            d=l.strip()
            d=re.sub(r'[\s　]*[\(（/／]?\s*[\d０-９一二三四五六七八九十]+\s*[名人]\s*参加[\)）]?','',d).strip()
            d=re.sub(r'[\s　]*エントリー\s*(?:人数)?\s*[\d０-９]+\s*[名人]?','',d).strip()
            d=re.sub(r'[\s　]*[\(（][\d０-９]+[\)）]$','',d).strip()
            e2=re.search(r'[/／]\s*(\d+)\s*名',n)
            if e2 and not ent: ent=e2.group(1)
            d=re.sub(r'[\s　]*[/／]\s*[\d０-９]*\s*[名人].*$','',d).strip()
            d=re.sub(r'[\s　]*[（(][\d０-９]+\s*名欠場[)）]','',d).strip()
            e3=re.search(r'\s(\d+)\s*名$',n)
            if e3 and not ent: ent=e3.group(1)
            d=re.sub(r'[\s　]+[\d０-９]+\s*名$','',d).strip()
            e4=re.search(r'[（(]\s*(\d+)\s*名\s*[)）]',n)
            if e4 and not ent: ent=e4.group(1)
            d=re.sub(r'[\s　]*[（(]\s*[\d０-９]+\s*名\s*[)）]','',d).strip()
            if d.startswith('・'):
                d=(sec+' '+d.lstrip('・').strip()).strip()
            div=d; skip=False; last_was_div=True; continue
    return out


def lines_of(path):
    import html as _h
    t = open(path, encoding='utf-8', errors='replace').read()
    m = re.search(r'<h1>(.*?)</h1>\s*<p class="mtb10 bold">(.*?)</p>(.*?)(?:<div class="pagenavi|<!--/main|<div id="side|$)', t, re.S)
    s = re.sub(r'<br\s*/?>', '\n', m.group(3))
    s = re.sub(r'</p>|</h\d>|</div>|</li>|</tr>', '\n', s)
    s = _h.unescape(re.sub(r'<[^>]+>', '', s))
    return [x.strip() for x in s.split('\n') if x.strip()]


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        for r in parse(lines_of(p)):
            print('\t'.join(r))
