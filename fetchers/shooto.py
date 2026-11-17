"""修斗公式サイト（shooto-mma.com）の試合結果から、新しい大会を取り込む。
一覧: https://shooto-mma.com/result/   各大会: https://shooto-mma.com/result/?id=番号
勝敗: 公式ページでは負けた選手の写真が薄く（opacity:0.3）表示される。片方だけ薄い場合に、もう片方を勝者とする。
"""
import re, html as H
from common import fetch, text_lines, links, known_sources, is_known, append, is_out_of_scope

PROMO = 'shooto'
LIST = 'https://shooto-mma.com/result/'
KIND = {'KO': 'KO', 'TKO': 'TKO', 'TS': '一本', 'S': '一本', 'SUB': '一本'}


def strip(s):
    return re.sub(r'\s+', ' ', H.unescape(re.sub(r'<[^>]+>', ' ', s or ''))).strip()


def parse(page, url):
    date = name = ''
    for l in text_lines(page):
        m = re.match(r'^(\d{4}-\d{2}-\d{2})\s*(.+)$', l)
        if m and m.group(1) != '2000-01-01':
            date, name = m.group(1), m.group(2).strip()
            break
    if not date:
        return None, []
    bouts = []
    for blk in page.split('class="matchmake-box')[1:]:
        title = [strip(p) for p in re.findall(r'<p>(.*?)</p>', blk.split('getitem_matchmake')[0], re.S)]
        title = [t for t in title if t]
        head = ' '.join(title)
        if is_out_of_scope(head):
            continue
        no = re.search(r'第\s*(\d+)\s*試合', head)
        fs = re.findall(r'class="matchmake col-xs-6[^"]*"[^>]*>\s*<div class="center-block" style="([^"]*)".*?<span class="fighter-name">(.*?)</span>', blk, re.S)
        if len(fs) != 2:
            continue
        (s1, n1), (s2, n2) = fs
        g1, g2 = 'opacity:0.3' in s1, 'opacity:0.3' in s2
        res = blk.split('class="getresult"')[1].split('class="note"')[0] if 'class="getresult"' in blk else ''
        rnd = re.search(r'result-round"><b>(\d+)</b>', res)
        tm = re.search(r'result-time">([\d:]+)<', res)
        typ = re.search(r'result-type">\s*<span class="[^"]*">([^<]*)<', res)
        det = re.search(r'result-method">([^<]*)<', res)
        kind = strip(typ.group(1)) if typ else ''
        meth = KIND.get(kind, kind)
        if det and strip(det.group(1)).lstrip('※'):
            meth += '（' + strip(det.group(1)).lstrip('※') + '）'
        if not meth:
            continue   # 結果がまだ載っていない
        win = ''
        if g1 and not g2:
            win = '2'
        elif g2 and not g1:
            win = '1'
        if re.search(r'ドロー|引き分け|引分|DRAW|Draw', meth):
            win = 'draw'
        if re.search(r'ノーコンテスト|無効|NC', meth):
            win = 'nc'
        t = tm.group(1) if tm else ''
        if re.match(r'^0\d:', t):
            t = t[1:]
        bouts.append({'match_no': int(no.group(1)) if no else len(bouts) + 1, 'fighter1': re.sub(r'\s+', ' ', strip(n1)),
                      'fighter2': re.sub(r'\s+', ' ', strip(n2)), 'winner': win, 'method': meth,
                      'round': rnd.group(1) if rnd else '', 'time': t if rnd else '', 'weight': ' '.join(title[1:])})
    return {'promotion': PROMO, 'date': date, 'name': name, 'venue': '', 'sources': url}, bouts


def run(limit=25, dry=False):
    known = known_sources()
    idx = fetch(LIST)
    pages = []
    for u in links(idx, LIST):
        m = re.search(r'shooto-mma\.com/result/\?id=(\d+)$', u)
        if m:
            u = 'https://shooto-mma.com/result/?id=' + m.group(1)
            if u not in pages:
                pages.append(u)
    added = 0
    for u in pages[:limit]:
        if is_known(u, known) or is_known(u.replace('://', '://www.'), known):
            continue
        try:
            ev, bouts = parse(fetch(u), u)
        except Exception as e:
            print(f'[修斗] 読み取り失敗 {u}: {e}'); continue
        if not ev or not bouts:
            print(f'[修斗] 結果なし（まだ未掲載か、ページの形が変わった可能性）: {u}'); continue
        ev['event_id'] = 'a-shooto-' + re.sub(r'\D', '', ev['date']) + '-' + u.rsplit('=', 1)[-1]
        for b in bouts:
            b['event_id'] = ev['event_id']
        if not dry:
            append(ev, bouts)
        added += 1
        print(f'[修斗] 追加: {ev["date"]} {ev["name"]}（{len(bouts)}試合）')
    return added


if __name__ == '__main__':
    run()
