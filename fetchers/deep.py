"""DEEP公式サイト（deep2001.com）の試合結果から、新しい大会を取り込む。
一覧: https://www.deep2001.com/result/  各大会ページの【試合結果】の部分を読む。
"""
import re
from common import fetch, text_lines, links, known_sources, is_known, append, is_out_of_scope

PROMO = 'deep'
LIST = 'https://www.deep2001.com/result/'
HEAD = re.compile(r'第\s*(\d+)\s*試合\s*(.*)$')
MARK = '○●△×'


def clean_name(s):
    return re.split(r'[（(]', s, maxsplit=1)[0].strip()


def parse(lines, url):
    lines = [l for l in lines if l]
    if not lines:
        return None, []
    if '【試合結果】' not in lines:
        return None, []
    top = lines.index('【試合結果】')
    name = date = venue = ''
    for k in range(top - 1, max(-1, top - 6), -1):
        m = re.match(r'^(\d{4})年(\d{1,2})月(\d{1,2})日(?:[（(][^）)]*[）)])?\s*(.*)$', lines[k])
        if m:
            date = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
            venue = m.group(4).strip()
            name = lines[k - 1] if k else ''
            break
    if not date:
        return None, []
    ls = lines[lines.index('【試合結果】') + 1:]
    bouts, i = [], 0
    while i < len(ls):
        h = HEAD.search(ls[i])
        if not h:
            if ls[i].startswith('【') or re.match(r'^\d{4}年\d{1,2}月', ls[i]):
                break
            i += 1
            continue
        if i + 2 >= len(ls) or not ls[i + 1][:1] in MARK or not ls[i + 2][:1] in MARK:
            i += 1
            continue
        a, b = ls[i + 1], ls[i + 2]
        res = ls[i + 3] if i + 3 < len(ls) and not HEAD.search(ls[i + 3]) else ''
        i += 4 if res else 3
        if is_out_of_scope(ls[i - (4 if res else 3)]):
            continue
        win = '1' if a[0] == '○' else '2' if b[0] == '○' else 'draw' if a[0] == b[0] == '△' else ''
        rnd = tm = ''
        meth = res
        m = re.match(r'^(\d+)R\s*(\d+)[’\'′:](\d+)[”"″]?\s*(.*)$', res)
        if m:
            rnd, tm, meth = m.group(1), f'{int(m.group(2))}:{m.group(3)}', m.group(4).strip()
        if re.search(r'ノーコンテスト|無効', meth):
            win = 'nc'
        rule = h.group(2).strip()
        bouts.append({'match_no': int(h.group(1)), 'fighter1': clean_name(a[1:]), 'fighter2': clean_name(b[1:]),
                      'winner': win, 'method': meth, 'round': rnd, 'time': tm, 'weight': rule})
    return {'promotion': PROMO, 'date': date, 'name': name, 'venue': venue, 'sources': url}, bouts


def run(limit=20, dry=False):
    known = known_sources()
    idx = fetch(LIST)
    seen, pages = set(), []
    for u in links(idx, LIST):
        if re.match(r'^https?://(www\.)?deep2001\.com/[^/?#.]+/?$', u) and re.search(r'deep|jewels|impact|kobudo|fight', u.rsplit('/', 2)[-2] if u.endswith('/') else u.rsplit('/', 1)[-1]) and not re.search(r'/(result|news|schedule|champ|champion|fighters?|panf|pamphlet|ticket|contact|future|past-[a-z-]+|category|tag|feed|wp-json)/?$', u):
            if u not in seen:
                seen.add(u); pages.append(u)
    added = 0
    for u in pages[:limit]:   # 一覧の上（新しい順）から見る
        if is_known(u, known):
            continue
        try:
            ev, bouts = parse(text_lines(fetch(u)), u)
        except Exception as e:
            print(f'[DEEP] 読み取り失敗 {u}: {e}'); continue
        if not ev or not bouts:
            print(f'[DEEP] 結果なし（まだ未掲載か、ページの形が変わった可能性）: {u}'); continue
        slug = u.rstrip('/').rsplit('/', 1)[-1][:40]
        ev['event_id'] = 'a-deep-' + re.sub(r'\D', '', ev['date']) + '-' + re.sub(r'[^a-z0-9-]', '', slug.lower())
        for b in bouts:
            b['event_id'] = ev['event_id']
        if not dry:
            append(ev, bouts)
        added += 1
        print(f'[DEEP] 追加: {ev["date"]} {ev["name"]}（{len(bouts)}試合）')
    return added


if __name__ == '__main__':
    import sys, os, json
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        here = os.path.dirname(os.path.abspath(__file__))
        ev, bouts = parse(open(os.path.join(here, 'tests', 'deep_133.txt'), encoding='utf-8').read().split('\n'), 'https://www.deep2001.com/deep-133-impact/')
        print(json.dumps(ev, ensure_ascii=False))
        for b in bouts: print(json.dumps(b, ensure_ascii=False))
    else:
        run()
