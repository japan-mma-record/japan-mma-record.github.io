"""WARDOG公式サイト（wardog-cf.jp）の大会ページから、新しい大会の結果を取り込む。
大会の一覧は https://wardog-cf.jp/wp-json/wp/v2/event （サイトの仕組みが出している一覧）を使う。
各大会ページの
  第N試合 / 階級 / 選手A / 所属 / VS / 選手B / 所属 / 試合結果 / 勝者X / 敗者Y / 2R 4分7秒 パウンドアウト
の形を読む。ジュニア大会や、ジュニア・アマチュアの試合は取り込まない。
"""
import json, os, re
from common import fetch, text_lines, known_sources, is_known, append, is_out_of_scope, read_tsv, DATA

PROMO = 'wardog_cage_fight'
API = 'https://wardog-cf.jp/wp-json/wp/v2/event?per_page=20&_fields=link,date,title'


def method_of(s):
    m = re.match(r'^(?:(\d)R\s*)?(?:(?:(\d+)分)?\s*(\d+)秒)?\s*(.*)$', s.strip())
    rnd, kind = m.group(1) or '', m.group(4).strip()
    tm = f'{int(m.group(2) or 0)}:{int(m.group(3)):02d}' if m.group(3) else ''
    sc = re.match(r'^判定\s*(\d)\s*-\s*(\d)', kind)
    if sc:
        a, b = sorted([int(sc.group(1)), int(sc.group(2))], reverse=True)
        return rnd, '', f'判定{a}-{b}'
    if re.match(r'^(T?KO|パウンドアウト)', kind):
        return rnd, tm, 'TKO' + ('（パウンド）' if 'パウンド' in kind else '') if not kind.startswith('KO') else 'KO'
    if kind:
        return rnd, tm, f'一本（{kind}）' if re.search(r'RNC|チョーク|アームバー|ロック|絞|固め|スリーパー|三角|ギロチン|ホールド', kind) else kind
    return rnd, tm, ''


def parse(lines, url):
    L = [l for l in lines if l]
    name = date = venue = ''
    for l in L:
        if not date and (m := re.match(r'^開催日\s*[：:]\s*(\d{4})年(\d{1,2})月(\d{1,2})日', l)):
            date = f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
        if not venue and (m := re.match(r'^会場\s*[：:]\s*(.+)$', l)):
            venue = m.group(1).strip()
    name = next((l for l in L if re.fullmatch(r'WARDOG\.\s*\d+(\s*-?\s*CAGE FIGHT\s*-?)?', l)), '')
    if not date or not name:
        return None, []
    bouts = []
    for k, l in enumerate(L):
        h = re.match(r'^第\s*(\d+)\s*試合$', l)
        if not h:
            continue
        end = next((j for j in range(k + 1, min(k + 25, len(L))) if re.match(r'^第\s*\d+\s*試合$', L[j]) or L[j] in ('メインイベント', 'セミファイナル')), min(k + 25, len(L)))
        blk = L[k + 1:end]
        if 'VS' not in blk or '試合結果' not in blk:
            continue
        label, a = blk[0], blk[1]
        v = blk.index('VS'); b = blk[v + 1]
        r = blk.index('試合結果')
        res = blk[r + 1:r + 4]
        win = next((x[2:].strip() for x in res if x.startswith('勝者')), '')
        lose = next((x[2:].strip() for x in res if x.startswith('敗者')), '')
        meth = next((x for x in res if not x.startswith(('勝者', '敗者'))), '')
        if is_out_of_scope(label) or re.search(r'アマチュア', ' '.join(blk)) or re.search(r'5分1R$', label):   # 1ラウンドの試合はアマチュア・若年層の試合のことがあるので取り込まない
            continue
        if win == a and lose == b:
            w = '1'
        elif win == b and lose == a:
            w = '2'
        elif re.search(r'引き分け|ドロー', meth):
            w = 'draw'
        else:
            continue   # 勝者の名前が対戦カードと合わないときは推測せず取り込まない
        rnd, tm, mth = method_of(meth)
        bouts.append({'match_no': int(h.group(1)), 'fighter1': a, 'fighter2': b, 'winner': w, 'method': mth, 'round': rnd, 'time': tm, 'weight': label})
    # メインイベント・セミファイナルは「第N試合」の見出しがないので、ページの一番上の2試合として読む
    for title, no in (('メインイベント', 999), ('セミファイナル', 998)):
        if title in L:
            k = L.index(title)
            blk = L[k + 1:k + 25]
            if 'VS' in blk and '試合結果' in blk:
                label, a = blk[0], blk[1]
                b = blk[blk.index('VS') + 1]
                res = blk[blk.index('試合結果') + 1:blk.index('試合結果') + 4]
                win = next((x[2:].strip() for x in res if x.startswith('勝者')), '')
                meth = next((x for x in res if not x.startswith(('勝者', '敗者'))), '')
                w = '1' if win == a else '2' if win == b else ''
                if w and not is_out_of_scope(label):
                    rnd, tm, mth = method_of(meth)
                    bouts.append({'match_no': no, 'fighter1': a, 'fighter2': b, 'winner': w, 'method': mth, 'round': rnd, 'time': tm, 'weight': label})
    bouts.sort(key=lambda b: b['match_no'])
    n = max([b['match_no'] for b in bouts if b['match_no'] < 900] or [0])
    for b in bouts:
        if b['match_no'] == 998: b['match_no'] = n + 1
        if b['match_no'] == 999: b['match_no'] = n + 2
    return {'promotion': PROMO, 'date': date, 'name': name, 'venue': venue, 'sources': url}, bouts


def run(dry=False):
    known = known_sources()
    kd = {r.get('date') for f in (os.path.join(DATA, 'core', 'events.tsv'), os.path.join(DATA, 'auto', 'events.tsv')) for r in read_tsv(f) if r.get('promotion') in (PROMO, 'wardog')}
    added = 0
    for it in json.loads(fetch(API)):
        u, title = it.get('link', ''), (it.get('title') or {}).get('rendered', '')
        if not re.search(r'(?i)wardog[.\-\s]*(cagefight[-\s]*)?\d+', title) or re.search(r'(?i)junior|ジュニア|amateur|アマ', title) or is_known(u, known):
            continue
        ev, bouts = parse(text_lines(fetch(u)), u)
        if not ev or not bouts or ev['date'] in kd:
            continue
        ev['event_id'] = 'a-wardog-' + ev['date'].replace('-', '') + '-' + re.sub(r'\D', '', ev['name'])
        for b in bouts:
            b['event_id'] = ev['event_id']
        if not dry:
            append(ev, bouts)
        added += 1
        print(f'[WARDOG] 追加: {ev["date"]} {ev["name"]}（{len(bouts)}試合）')
    return added
