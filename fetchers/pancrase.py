"""パンクラス公式サイトの試合結果データベースから、新しい大会を取り込む。
対象: https://pancrase.co.jp/data/result/<年>/
"""
import re, datetime
from common import fetch, text_lines, links, known_sources, is_known, append, is_out_of_scope

PROMO = 'pancrase'
BASE = 'https://pancrase.co.jp/data/result/{y}/'
HEAD = re.compile(r'^(メインイベント|コーメイン|セミメイン|セミファイナル|第\s*\d+\s*試合)\S*\s*(.*)$')
RES = re.compile(r'^(?:(\d+)R\s*)?(\d{1,2}:\d{2})?\s*[、,]\s*(.+)$')
NUM = {'①': 1, '②': 2, '③': 3, '④': 4, '⑤': 5, '⑥': 6, '⑦': 7, '⑧': 8, '⑨': 9, '⑩': 10, '⑪': 11, '⑫': 12, '⑬': 13, '⑭': 14, '⑮': 15, '⑯': 16, '⑰': 17, '⑱': 18, '⑲': 19, '⑳': 20}
MARK = '○●×△'


def parse(lines, url):
    lines = [l for l in lines if l]
    date = venue = name = ''
    for i, l in enumerate(lines):
        m = re.match(r'^(\d{4})\.(\d{1,2})\.(\d{1,2})\s*(.*)$', l)
        if m:
            date = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            venue = m.group(4).strip()
            name = lines[i - 1] if i else ''
            break
    if not date:
        return None, []
    blocks, cur = [], None
    for l in lines:
        h = HEAD.match(l)
        if h:
            cur = {'head': l, 'weight': h.group(2), 'lines': []}
            blocks.append(cur)
        elif cur is not None:
            if l.startswith('PANCRASE OFFICIAL RANKING'):
                break
            cur['lines'].append(l)
    bouts = []
    for n, b in enumerate(blocks, 1):
        if is_out_of_scope(b['head']):
            continue
        no = None
        m = re.search(r'第\s*(\d+)\s*試合', b['head'])
        if m:
            no = int(m.group(1))
        else:
            for ch, v in NUM.items():
                if ch in b['head']:
                    no = v
        ls = b['lines']
        if 'vs' not in ls:
            continue
        vi = ls.index('vs')
        left = next((l for l in ls[:vi] if l[0] in MARK), '')
        right = next((l for l in ls[vi + 1:] if l[-1] in MARK), '')
        if not left or not right:
            continue
        f1, m1 = left[1:].strip(), left[0]
        f2, m2 = right[:-1].strip(), right[-1]
        rnd = tm = meth = ''
        for l in ls[vi + 1:]:
            r = RES.match(l)
            if r and (r.group(1) or r.group(2)):
                rnd, tm, meth = r.group(1) or '', r.group(2) or '', r.group(3).strip()
                break
        win = ''
        if m1 == '○' and m2 in '×●':
            win = '1'
        elif m2 == '○' and m1 in '×●':
            win = '2'
        elif m1 == '△' and m2 == '△':
            win = 'draw'
        if re.search(r'ノーコンテスト|無効試合', meth):
            win = 'nc'
        bouts.append({'match_no': no or n, 'fighter1': f1, 'fighter2': f2, 'winner': win, 'method': meth,
                      'round': rnd, 'time': tm, 'weight': b['weight']})
    return {'promotion': PROMO, 'date': date, 'name': name, 'venue': venue, 'sources': url}, bouts


def run(years=None, dry=False):
    y = datetime.date.today().year
    years = years or [y - 1, y]
    known = known_sources()
    added = 0
    for yy in years:
        idx_url = BASE.format(y=yy)
        try:
            idx = fetch(idx_url)
        except Exception as e:
            print(f'[パンクラス] {yy}年の一覧が読めません: {e}')
            continue
        pages = sorted({u for u in links(idx, idx_url) if re.search(rf'/data/result/{yy}/\d{{4}}[a-z]?\.html$', u)})
        for u in pages:
            if is_known(u, known):
                continue
            try:
                ev, bouts = parse(text_lines(fetch(u)), u)
            except Exception as e:
                print(f'[パンクラス] 読み取り失敗 {u}: {e}')
                continue
            if not ev or not bouts:
                print(f'[パンクラス] 結果なし（まだ未掲載か、ページの形が変わった可能性）: {u}')
                continue
            ev['event_id'] = 'a-pancrase-' + re.sub(r'\D', '', ev['date']) + '-' + re.search(r'(\d{4}[a-z]?)\.html$', u).group(1)
            for b in bouts:
                b['event_id'] = ev['event_id']
            if not dry:
                append(ev, bouts)
            added += 1
            print(f'[パンクラス] 追加: {ev["date"]} {ev["name"]}（{len(bouts)}試合）')
    return added


if __name__ == '__main__':
    import sys, os, json
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        here = os.path.dirname(os.path.abspath(__file__))
        lines = open(os.path.join(here, 'tests', 'pancrase_368.txt'), encoding='utf-8').read().split('\n')
        ev, bouts = parse(lines, 'https://pancrase.co.jp/data/result/2026/1108.html')
        print(json.dumps(ev, ensure_ascii=False))
        for b in bouts:
            print(json.dumps(b, ensure_ascii=False))
    else:
        run()
