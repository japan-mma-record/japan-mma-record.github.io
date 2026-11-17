"""RIZIN公式サイト（jp.rizinff.com）の「試合結果一覧」記事から、新しい大会を取り込む。
一覧: https://jp.rizinff.com/_tags/試合結果
各試合の行は「（WIN）選手A vs. 選手B（LOSE）」の形で、勝敗がはっきり書かれている。
大会の日付が本文に「YYYY年M月D日」で書かれていない記事は、日付を確かめられないので取り込まない。
"""
import re, urllib.parse, html as H
from common import fetch, text_lines, known_sources, is_known, append, is_out_of_scope

PROMO = 'rizin'
LIST = 'https://jp.rizinff.com/_tags/' + urllib.parse.quote('試合結果')
VS = re.compile(r'^（(WIN|LOSE|DRAW|-|－)）\s*(.+?)\s+vs\.?\s+(.+?)\s*（(WIN|LOSE|DRAW|-|－)）$')
HEAD = re.compile(r'^(OPENING FIGHT\s*)?第\s*(\d+)\s*試合／')
RES = re.compile(r'^(\d+)R\s*(?:(\d+)分(\d+)秒)?\s*(.*)$')


def parse(page, url):
    L = [l for l in text_lines(page) if l]
    name = ''
    for l in L:
        m = re.match(r'^『?(.+?)』?\s*試合結果一覧$', l)
        if m:
            name = m.group(1).strip('『』 ')
            break
    date = ''
    for l in L:
        m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日', l)
        if m:
            date = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            break
    if not name or not date:
        return None, []
    bouts, cur = [], None
    for l in L:
        h = HEAD.match(l)
        if h:
            cur = {'open': bool(h.group(1)), 'no': int(h.group(2)), 'rule': '', 'vs': None, 'res': ''}
            continue
        if cur is None:
            continue
        if 'ルール' in l and not cur['rule']:
            cur['rule'] = l
        v = VS.match(l)
        if v:
            cur['vs'] = v.groups()
            continue
        if cur['vs'] and not cur['res']:
            r = RES.match(l)
            if r:
                cur['res'] = r
                a, n1, n2, b = cur['vs']
                rule = cur['rule']
                if 'MMA' in rule and not is_out_of_scope(rule):
                    win = '1' if a == 'WIN' else '2' if b == 'WIN' else 'draw' if a == b == 'DRAW' else ''
                    meth = r.group(4).strip()
                    if 'ノーコンテスト' in meth or '無効' in meth:
                        win = 'nc'
                    meth = re.sub(r'^SUB', '一本', meth)
                    meth = re.sub(r'^（(.*)）$', r'\1', meth)
                    t = f'{int(r.group(2))}:{r.group(3)}' if r.group(2) else ''
                    no = cur['no'] if not cur['open'] else 0
                    bouts.append({'match_no': no, 'fighter1': n1, 'fighter2': n2, 'winner': win, 'method': meth,
                                  'round': r.group(1), 'time': t,
                                  'weight': ('オープニングファイト ' if cur['open'] else '') + rule.replace('RIZIN MMAルール：', '')})
                cur = None
    # オープニングファイトは本戦より前の番号にする
    for b in bouts:
        if b['match_no'] == 0:
            b['match_no'] = ''   # オープニングファイトは番号なし（階級欄に「オープニングファイト」と書く）
    return {'promotion': PROMO, 'date': date, 'name': name, 'venue': '', 'sources': url}, bouts


def run(limit=10, dry=False):
    known = known_sources()
    idx = fetch(LIST)
    pages = []
    for m in re.finditer(r'<a[^>]+href="([^"]*/_ct/(\d+))[^"]*"[^>]*>(.*?)</a>', idx, re.S):
        text = re.sub(r'<[^>]+>', '', H.unescape(m.group(3)))
        if '試合結果一覧' in text:
            u = 'https://jp.rizinff.com/_ct/' + m.group(2)
            if u not in pages:
                pages.append(u)
    added = 0
    for u in pages[:limit]:
        if is_known(u, known):
            continue
        try:
            ev, bouts = parse(fetch(u), u)
        except Exception as e:
            print(f'[RIZIN] 読み取り失敗 {u}: {e}'); continue
        if not ev or not bouts:
            print(f'[RIZIN] 取り込まず（日付が書かれていない・結果なし・ページの形が変わった可能性）: {u}'); continue
        ev['event_id'] = 'a-rizin-' + re.sub(r'\D', '', ev['date']) + '-' + u.rsplit('/', 1)[-1]
        for b in bouts:
            b['event_id'] = ev['event_id']
        if not dry:
            append(ev, bouts)
        added += 1
        print(f'[RIZIN] 追加: {ev["date"]} {ev["name"]}（{len(bouts)}試合）')
    return added


if __name__ == '__main__':
    run()
