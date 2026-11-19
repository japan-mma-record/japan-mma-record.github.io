"""GRACHAN公式サイト（grachan.jp）の試合結果から、新しい大会を取り込む。
一覧: https://grachan.jp/result/  各記事（GRACHAN86 試合結果 など）の
  ▼第N試合 階級 / ◯(勝者)または✕(敗者) 選手A / [ 2R 1:09 / TKO ]※詳細 / ◯または✕ 選手B
の形を読む。GRACHANチャレンジ（アマチュア）やアマチュア大会は取り込まない。
"""
import re
from common import fetch, text_lines, known_sources, is_known, append, is_out_of_scope, read_tsv, DATA
import os

PROMO = 'grachan'
LIST = 'https://grachan.jp/result/'
WIN, LOSE, DRAW = '◯○〇', '✕×xX', '△'


def clean(s):
    s = re.sub(r'^[◯○〇✕×△]\s*', '', s)
    s = re.split(r'\s*[（(]', s, maxsplit=1)[0]
    return re.sub(r'[：:]\s*[\d.]+\s*kg.*$', '', s).strip()


def method_of(res, detail):
    m = re.match(r'^\[\s*(?:(\d)R\s*)?([\d:]+)?\s*/\s*(.+?)\s*\]', res)
    if not m:
        return '', '', res
    rnd, tm, kind = m.group(1) or '', m.group(2) or '', m.group(3).strip()
    detail = (detail or '').strip('※ ')
    if re.match(r'^判定', kind):
        sc = re.search(r'(\d)\s*-\s*(\d)', kind)
        a, b = (sorted([int(sc.group(1)), int(sc.group(2))], reverse=True) if sc else (None, None))
        return rnd, '', '判定' + (f'{a}-{b}' if sc else '')
    if kind in ('TKO', 'KO'):
        return rnd, tm, kind + (f'（{detail}）' if detail else '')
    if kind in ('TS', 'TO', 'SUB', '一本', 'タップ'):
        return rnd, tm, '一本' + (f'（{detail}）' if detail else '')
    if re.search(r'ロック|絞|固め|チョーク|アームバー|ホールド|スリーパー', kind):
        return rnd, tm, f'一本（{kind}）'
    return rnd, tm, kind + (f'（{detail}）' if detail else '')


def parse(lines, url):
    L = [l for l in lines if l]
    name = next((l.replace('試合結果', '').strip() for l in L if re.match(r'^GRACHAN\s*\d+\s*試合結果$', l)), '')
    if not name:
        return None, []
    bouts, i = [], 0
    while i < len(L):
        h = re.match(r'^▼?\s*第\s*(\d+)\s*試合\s*(.*)$', L[i])
        if h and i + 3 < len(L) and L[i + 1][:1] in WIN + LOSE + DRAW and L[i + 2].startswith('[') and L[i + 3][:1] in WIN + LOSE + DRAW:
            a, res, b = L[i + 1], L[i + 2], L[i + 3]
            detail = res.split(']', 1)[1] if ']' in res else ''
            rnd, tm, meth = method_of(res, detail)
            win = '1' if a[0] in WIN else '2' if b[0] in WIN else 'draw' if a[0] in DRAW and b[0] in DRAW else ''
            if not is_out_of_scope(h.group(2)) and win:
                bouts.append({'match_no': int(h.group(1)), 'fighter1': clean(a), 'fighter2': clean(b), 'winner': win,
                              'method': meth, 'round': rnd, 'time': tm, 'weight': h.group(2).strip()})
            i += 4
            continue
        i += 1
    bouts.sort(key=lambda b: b['match_no'])
    return {'promotion': PROMO, 'name': name, 'sources': url}, bouts


def list_items(page):
    """結果一覧から（記事URL, 日付, 見出し）を取り出す。"""
    out = []
    for m in re.finditer(r'<a href="(https://grachan\.jp/[^"]+)">\s*<time[^>]*datetime="(\d{4}-\d{2}-\d{2})"[^>]*>.*?</time>\s*<h3[^>]*>(.*?)</h3>', page, re.S):
        out.append((m.group(1), m.group(2), re.sub(r'<[^>]+>', '', m.group(3)).strip()))
    return out


def known_dates():
    s = set()
    for f in (os.path.join(DATA, 'core', 'events.tsv'), os.path.join(DATA, 'auto', 'events.tsv')):
        for r in read_tsv(f):
            if r.get('promotion') == PROMO:
                s.add(r.get('date'))
    return s


def venue_of(name):
    """大会ページ（grachan.jp/schedule/grachanNN/）の会場。"""
    n = re.search(r'\d+', name)
    if not n:
        return ''
    try:
        L = [l for l in text_lines(fetch(f'https://grachan.jp/schedule/grachan{n.group(0)}/')) if l]
        return next((L[k + 1] for k in range(len(L) - 1) if L[k] == '会場'), '')
    except Exception:
        return ''


def run(dry=False):
    known, kd = known_sources(), known_dates()
    added = 0
    for u, d, title in list_items(fetch(LIST))[:10]:
        if not re.match(r'^GRACHAN\s*\d+\s*試合結果', title) or is_known(u, known) or d in kd:
            continue
        ev, bouts = parse(text_lines(fetch(u)), u)
        if not ev or not bouts:
            print(f'[GRACHAN] 結果なし（ページの形が変わった可能性）: {u}'); continue
        ev['date'] = d
        ev['venue'] = venue_of(ev['name'])
        ev['event_id'] = 'a-grachan-' + d.replace('-', '') + '-' + re.sub(r'\D', '', ev['name'])
        for b in bouts:
            b['event_id'] = ev['event_id']
        if not dry:
            append(ev, bouts)
        added += 1
        print(f'[GRACHAN] 追加: {d} {ev["name"]}（{len(bouts)}試合）')
    return added
