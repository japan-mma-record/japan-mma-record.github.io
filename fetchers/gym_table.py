"""表の形の結果ページから、試合ごとの所属を読み取り、data/gyms.tsv に足す行を作る。

使い方: python3 build.py のあと、python3 fetchers/gym_table.py DIR [DIR...] >> data/gyms.tsv
  DIR は probe-web ブランチの probe/ と同じ形（index.txt と out/N.html）のフォルダ。
  index.txt の URL が _site/data/events.json の出典URLに入っている大会の試合だけを見る。
読める形:
  ・修斗の古い結果ページ（hirashima-igs.com/shooto/）：1試合ごとの表に、左右の選手名と
    「ランク」「戦績」「出身」「所属」の行がある。「所属」の行の左右をそれぞれの選手の所属とする。
    文字コードは Shift_JIS（ページに charset が書かれていない）。
決まり:
  ・表の2人の名前（空白は無視）が、その大会の試合の2人と同じときだけ入れる。
  ・「フリー」「無所属」、空欄、国名は入れない（fetchers/gym_paren.py の clean_gym と同じ）。
  ・すでに所属が入っている試合は出さない。
"""
import re, html, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gym_paren as gp  # noqa: E402


def decode(raw):
    for enc in ('utf-8', 'cp932', 'euc_jp'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            pass
    return raw.decode('cp932', errors='replace')


def cell(s):
    s = re.sub(r'(?i)<br\s*/?>', ' ', s)
    s = re.sub(r'<[^>]+>', '', s)
    return re.sub(r'\s+', ' ', html.unescape(s).replace('　', ' ')).strip()


def hirashima_bouts(t):
    """[(名前1, 名前2, 所属1, 所属2)]"""
    out = []
    for tb in re.findall(r'(?is)<table\b.*?</table>', t):
        if '所属' not in tb:
            continue
        ths = re.findall(r'(?is)<th\b[^>]*>(.*?)</th>', tb)
        names = []
        for th in ths:
            m = re.findall(r'(?is)<font[^>]*size\s*=\s*"?5"?[^>]*>(.*?)</font>', th)
            if m:
                names.append(cell(m[-1]))
        m = re.search(r'(?is)<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<th[^>]*>\s*所属\s*</th>\s*<td[^>]*>(.*?)</td>', tb)
        if len(names) == 2 and m:
            out.append((names[0], names[1], cell(m.group(1)), cell(m.group(2))))
    return out


def run(dirs):
    seen = set()
    for d in dirs:
        for line in open(os.path.join(d, 'index.txt'), encoding='utf-8'):
            p = line.split()
            if len(p) < 4 or p[1] != '200':
                continue
            n, url = p[0], p[3]
            path = os.path.join(d, 'out', f'{n}.html')
            if not os.path.exists(path) or 'hirashima-igs.com' not in url:
                continue
            t = decode(open(path, 'rb').read())
            tb = hirashima_bouts(t)
            for eid in gp.url2ev.get(url, []):
                for b in gp.bouts.get(eid, []):
                    no = str(b[0]) if b[0] else ''
                    n1, n2 = gp.nz(b[2]), gp.nz(b[4])
                    if not n1 or not n2:
                        continue
                    hits = [x for x in tb if {gp.nz(x[0]), gp.nz(x[1])} == {n1, n2}]
                    if len(hits) != 1:
                        continue
                    a, c, ga, gc = hits[0]
                    gm = {gp.nz(a): ga, gp.nz(c): gc}
                    for nm, orig, cur in ((n1, b[2], b[16]), (n2, b[4], b[17])):
                        g = gp.clean_gym(gm.get(nm, ''))
                        if not g or cur or g in ('-', '－', '?', '？', '無', 'なし', '不明'):
                            continue
                        if (eid, no, nm) in gp.have or (eid, '', nm) in gp.have:
                            continue
                        k = (eid, no, nm)
                        if k in seen:
                            continue
                        seen.add(k)
                        print('\t'.join((eid, no, orig, g, url)))


if __name__ == '__main__':
    run(sys.argv[1:])
