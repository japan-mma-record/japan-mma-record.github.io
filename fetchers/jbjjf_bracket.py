"""JBJJF のトーナメント表（Google スプレッドシートの CSV）から試合と勝者を読み取る。

表の形:
- 区分の見出し行: [区分名, 体重, , 試合時間, , "N 人", ...]
- 1回戦の選手は 0 列目（名前の行の次の行が所属）
- 試合番号は 3 列目（1回戦）、7, 11, 15 ...列目（2回戦以降）
- 勝ち上がった選手は「試合番号の列+1」に 1 か 2（1=上の選手、2=下の選手）、その右に名前
勝者は、次の列に勝ち上がった選手の名前と 1/2 の印が一致したときだけ採用する（推測しない）。

使い方: 公開シートの各マットのタブを CSV で取る
  https://docs.google.com/spreadsheets/d/e/<ID>/pub?gid=<GID>&single=true&output=csv
タブの名前（「１マット」など）と gid は .../pubhtml のページの items.push({name: ..., gid: ...}) にある。
注意: 3人の区分は総当たり・敗者復活で表の形が違うので使わない。「欠場」「棄権」「失格」の付いた試合も使わない。
決勝の勝者は表彰台（data/podium.tsv）と照らし合わせてから入れる（2,860件中2件で食い違いがあった）。
ジュブナイル（16・17歳）の区分は、これまで表彰台も試合も載せていない。
"""
import csv, re, sys


def jname(s):
    s = re.sub(r'^[※\s]+', '', (s or '').strip())
    if re.search(r'[぀-ヿ一-鿿]', s):
        # 「中村圭太 Keita Nakamura」→「中村圭太」
        toks = s.split()
        out = []
        for t in toks:
            if re.fullmatch(r"[A-Za-z.'\-]+", t):
                break
            out.append(t)
        return ''.join(out) if out else s
    return re.sub(r'\s+', ' ', s)


def weight_label(w):
    w = (w or '').strip()
    m = re.fullmatch(r'(-?)(\d+(?:\.\d+)?)kg(～?)', w)
    if m:
        num = m.group(2)
        if '.' in num:
            num = num.rstrip('0').rstrip('.')
        return f'{m.group(1)}{num}kg{m.group(3)}'
    return w


def parse(path):
    rows = list(csv.reader(open(path, encoding='utf-8')))
    W = max(len(r) for r in rows) if rows else 0
    grid = [r + [''] * (W - len(r)) for r in rows]
    # 区分の見出し
    heads = [i for i, r in enumerate(grid) if len(r) > 5 and re.fullmatch(r'\d+\s*人', r[5].strip() or 'x') and r[0].strip()]
    out = []
    for hi, h in enumerate(heads):
        end = heads[hi + 1] if hi + 1 < len(heads) else len(grid)
        div, wt, n = grid[h][0].strip(), grid[h][1].strip(), int(re.match(r'\d+', grid[h][5].strip()).group())
        # 表彰台の行の後から
        start = h + 1
        for i in range(h + 1, end):
            if grid[i][0].strip() in ('優勝', '準優勝', '3位'):
                start = i + 1
        sub = [(i, grid[i]) for i in range(start, end)]
        cell = lambda i, j: grid[i][j].strip() if 0 <= i < len(grid) and j < W else ''
        # 1回戦の選手: 0 列目の連続した2行（名前・所属）の1行目
        entrants = {0: []}
        i = start
        while i < end:
            if cell(i, 0):
                entrants[0].append((i, cell(i, 0)))
                i += 2
                continue
            i += 1
        # 2回戦以降の選手: 印(1/2)の右の名前
        def ents(col):
            if col == 0:
                return entrants[0]
            xs = [(i, cell(i, col)) for i in range(start, end) if re.fullmatch(r'[12]{1,2}', cell(i, col - 1)) and cell(i, col)]
            rowsx = {i for i, _ in xs}
            return [(i, v) for i, v in xs if (i - 1) not in rowsx]   # 名前の次の行（所属）に印が付いたものは除く
        bouts = []
        rounds = []
        m = 3
        while m < W:
            ncol = 0 if m == 3 else m - 2
            names = ents(ncol)
            nxt = ents(m + 2)
            ms = [(i, cell(i, m)) for i in range(start, end) if re.fullmatch(r'\d{1,3}', cell(i, m))]
            # 1回戦の試合番号の列（3）には時刻の行の数字も入らない（時刻は "12:05" の形）
            if not ms and not names:
                break
            used = set()
            rb = []
            for r, no in ms:
                up = [x for x in names if x[0] <= r]
                dn = [x for x in names if x[0] > r]
                if not up or not dn:
                    continue
                a, b = up[-1], dn[0]
                if a[0] in used or b[0] in used:
                    continue
                # 勝者: 次の列の、この試合の行に近い名前
                cand = sorted(nxt, key=lambda x: abs(x[0] - r))
                w = None
                if cand and abs(cand[0][0] - r) <= 4:
                    wi, wn = cand[0]
                    flag = cell(wi, m + 1)
                    if flag == '1' and wn == a[1]:
                        w = '1'
                    elif flag == '2' and wn == b[1]:
                        w = '2'
                used |= {a[0], b[0]}
                rb.append((no, a[1], b[1], w))
            if rb:
                rounds.append(rb)
            m += 4
        nr = len(rounds)
        for k, rb in enumerate(rounds):
            left = nr - k
            lab = {1: '決勝', 2: '準決勝', 3: '準々決勝'}.get(left) or f'{k + 1}回戦'
            if left > 3 and k == 0:
                lab = '1回戦'
            for no, a, b, w in rb:
                out.append({'division': div, 'weight': weight_label(wt), 'n': n, 'match_no': no,
                            'f1': jname(a), 'f2': jname(b), 'winner': w or '', 'round': lab})
    return out


def usable(bouts):
    """記録に使える試合だけを返す（3人の区分・欠場/棄権/失格・同じ組み合わせが2回ある区分の試合・勝者が読めない試合を除く）。"""
    import collections
    by = collections.defaultdict(list)
    for b in bouts:
        by[b['division']].append(b)
    out = []
    for d, l in by.items():
        if l[0]['n'] <= 3:
            continue
        pairs = collections.Counter(frozenset((b['f1'], b['f2'])) for b in l)
        for b in l:
            if b['winner'] and not re.search('欠場|棄権|不戦|失格', b['f1'] + b['f2']) and pairs[frozenset((b['f1'], b['f2']))] == 1:
                out.append(b)
    return out


if __name__ == '__main__':
    for p in sys.argv[1:]:
        for b in parse(p):
            print(b)
