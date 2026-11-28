"""アルファベット表記の入賞者（ASJJF・IBJJF など）を、日本語名の選手につなぐ表を作る。

決まり（同じ人とみなすのは、次の2つがどちらも合うときだけ）:
1. フルネームが同じ … JBJJF の公式結果に「日本語名＋ローマ字」で載った選手のローマ字と、
   姓・名の順番の違い、大文字小文字、空白、アクセント記号の違いを除いて一致する。
   同じローマ字の日本語名が2人以上いるときは、どちらか決められないのでつながない。
2. 所属が同じ … その選手が JBJJF で載ったどれかの所属と、読みを比べて同じ
   （「Paraestra Chiba」と「パラエストラ千葉」のように。ローマ字にして子音の並びを比べる）。

使い方: pip install pykakasi && python3 fetchers/en_links.py
  → data/en_links.tsv（promotion, name_en, team, name_ja, team_ja）を作り直す。
build.py はこの表を見て、アルファベット表記の入賞を日本語名の選手ページにつなぐ（表示はもとのアルファベットのまま）。
"""
import csv, collections, difflib, os, re, sys, unicodedata

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(HERE, 'data')


def name_key(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return ' '.join(sorted(re.findall(r'[a-z]+', s)))


_K = None
def rom(s):
    global _K
    if _K is None:
        import pykakasi
        _K = pykakasi.kakasi()
    s = unicodedata.normalize('NFKC', s or '')
    return ''.join(x['hepburn'] for x in _K.convert(s)).lower()


WORDS = [(r'brazilian|burajirian', 'B'), (r'jiu-?jitsu|juu?ju?tsu|jiujitsu|juujitsu|jiujutsu', 'J'),
         (r'academy|akademii|akademi', 'A'), (r'doujou|dojo|doujyou', 'D'), (r'gracie|gureishii', 'G'),
         (r'barra|bahha|baha', 'b'), (r'team|chiimu', 'T'), (r'gym|jimu', 'M'), (r'club|kurabu', 'K'),
         (r'japan|japon|nippon|nihon', '')]


def team_key(s):
    """所属の読みの骨組み（子音の並び）"""
    s = re.sub(r'[^a-z]', '', rom(s))
    for a, b in WORDS:
        s = re.sub(a, b, s)
    s = s.replace('tch', 'C').replace('ch', 'C').replace('sh', 'S')
    s = re.sub(r'c(?=[eiy])', 's', s)
    for a, b in (('ck', 'k'), ('c', 'k'), ('l', 'r'), ('v', 'b'), ('ph', 'f'), ('th', 's'), ('x', 'ks'), ('q', 'k'),
                 ('tsu', 'ts'), ('si', 'shi'), ('z', 's'), ('j', 'd')):
        s = s.replace(a, b)
    s = re.sub(r'(?<=[a-z])h', '', s)
    s = re.sub(r'[aeiou]', '', s)
    return re.sub(r'(.)\1+', r'\1', s)


_TK = {}
def same_team(a, b):
    x = _TK.setdefault(a, team_key(a)); y = _TK.setdefault(b, team_key(b))
    if not x or not y:
        return False
    return x == y or difflib.SequenceMatcher(None, x, y).ratio() >= 0.85


def main():
    rows = list(csv.DictReader(open(os.path.join(DATA, 'podium.tsv'), encoding='utf-8'), delimiter='\t'))
    jp = collections.defaultdict(lambda: {'ja': set(), 'teams': set()})
    for r in rows:
        if r.get('name_ja') and r.get('name_en'):
            k = name_key(r['name_en'])
            if k:
                jp[k]['ja'].add(re.sub(r'[\s　]', '', r['name_ja']))
                if r.get('team'):
                    jp[k]['teams'].add(r['team'].strip())
    out = {}
    st = collections.Counter()
    for r in rows:
        if r.get('name_ja') or not r.get('name_en'):
            continue
        k = name_key(r['name_en']); c = jp.get(k)
        if not c:
            st['日本語名の記録なし'] += 1; continue
        if len(c['ja']) != 1:
            st['同じローマ字が2人以上'] += 1; continue
        hit = next((t for t in sorted(c['teams']) if same_team(r.get('team', ''), t)), None)
        if not hit:
            st['所属が違う'] += 1; continue
        st['つないだ'] += 1
        out[(r['promotion'], r['name_en'].strip(), r.get('team', '').strip())] = (next(iter(c['ja'])), hit)
    with open(os.path.join(DATA, 'en_links.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['promotion', 'name_en', 'team', 'name_ja', 'team_ja'])
        for (p, n, t), (ja, tj) in sorted(out.items()):
            w.writerow([p, n, t, ja, tj])
    print(dict(st), '→', len(out), '通りの表記を data/en_links.tsv に書いた')


if __name__ == '__main__':
    main()
