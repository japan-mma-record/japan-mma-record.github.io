#!/usr/bin/env python3
"""日本MMA戦績録：data/ の記録から公開サイト（_site/）を作るプログラム。

Pythonの標準機能だけで動きます（追加のインストールは不要）。
使い方:  python3 build.py
  → _site/ フォルダに、そのまま公開できるサイト一式ができます。

データの置き場所:
  data/core/   … 確かめ済みの記録（大会・試合・選手）。手で直すときもここ。
  data/auto/   … 公式サイトから自動で取り込んだ新しい大会（fetch.py が書き込む）。
  data/fixes.tsv … 個別の訂正（任意）。event_id・match_no・列名・正しい値。
  data/promotions.tsv … 団体の表示名。
  data/site.json … サイトの住所など。
"""
import csv, json, os, re, shutil, html, datetime, collections, urllib.parse, unicodedata, hashlib
import methods

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(ROOT, '_site')
TPL = os.path.join(ROOT, 'template')


def read_tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as fp:
        return list(csv.DictReader(fp, delimiter='\t'))


def norm(s):
    return re.sub(r'[\s・･　]', '', s or '')


def load():
    site = json.load(open(os.path.join(DATA, 'site.json'), encoding='utf-8'))
    promos = {r['promotion']: r for r in read_tsv(os.path.join(DATA, 'promotions.tsv'))}
    events = {r['event_id']: r for r in read_tsv(os.path.join(DATA, 'core', 'events.tsv'))}
    for r in events.values():
        r['name'] = methods.event_name(r.get('name'))
        r['sources'] = methods.clean_sources(r.get('sources'))
    bouts = collections.defaultdict(list)
    for r in read_tsv(os.path.join(DATA, 'core', 'bouts.tsv')):
        bouts[r['event_id']].append(r)
    fighters = {r['fighter_id']: r['name'] for r in read_tsv(os.path.join(DATA, 'core', 'fighters.tsv'))}
    renamed = {}
    for r in read_tsv(os.path.join(DATA, 'names.tsv')):   # 選手名の訂正・日本語表記（出典つき）
        if r.get('fighter_id') in fighters and r.get('name'):
            fighters[r['fighter_id']] = renamed[r['fighter_id']] = r['name']

    # 自動取り込み分：同じ団体・同じ日の大会が core にあれば core を優先
    have = {(e['promotion'], e['date']) for e in events.values()}
    by_name = collections.defaultdict(list)
    for fid, n in fighters.items():
        by_name[norm(n)].append(fid)
    auto_ev = read_tsv(os.path.join(DATA, 'auto', 'events.tsv'))
    auto_b = collections.defaultdict(list)
    for r in read_tsv(os.path.join(DATA, 'auto', 'bouts.tsv')):
        auto_b[r['event_id']].append(r)
    for e in auto_ev:
        if (e['promotion'], e['date']) in have:
            continue
        e['name'] = methods.event_name(e.get('name'))
        e['sources'] = methods.clean_sources(e.get('sources'))
        events[e['event_id']] = e
        for b in auto_b.get(e['event_id'], []):
            for k in ('1', '2'):
                if not b.get(f'fighter{k}_id'):
                    hit = by_name.get(norm(b[f'fighter{k}']), [])
                    if len(hit) == 1:          # 同じ名前の選手が一人だけなら同一人物として結ぶ
                        b[f'fighter{k}_id'] = hit[0]
            bouts[e['event_id']].append(b)

    # 個別の訂正
    for f in read_tsv(os.path.join(DATA, 'fixes.tsv')):
        for b in bouts.get(f['event_id'], []):
            if str(b.get('match_no')) == str(f['match_no']) and f['field'] in b:
                b[f['field']] = f['value']
    # 同じ団体・同じ日の大会で、出典が同じもの、または「海外の記録サイト」だけが出典のものは、1つの大会にまとめる（同じ試合は重ねない）
    byday = collections.defaultdict(list)
    for e in events.values():
        byday[(e['promotion'], e['date'])].append(e)
    for evs in byday.values():
        if len(evs) < 2:
            continue
        def src(e):
            return {t for t in (e.get('sources') or '').split() if t.startswith('http')}
        def jname(e):   # 日本の資料の名前（「ROMAN - …」のような海外式の名前でないもの）を優先
            return (not methods.headline(e['name']), len(e['name'].strip()) > 4, bool(re.search(r'[ぁ-んァ-ヶ一-龥]', e['name'])), ' - ' not in e['name'], len(src(e)))
        main = max(evs, key=jname)
        for o in evs:
            if o is main:
                continue
            if not (src(o) & src(main)) and src(o) and ' - ' not in o['name'] + main['name'] and not methods.headline(o['name']) and len(o['name'].strip()) > 4:
                continue
            main_id = main['event_id']
            have = {frozenset((norm(x['fighter1']), norm(x['fighter2']))) for x in bouts[main_id]}
            have |= {frozenset((x.get('fighter1_id'), x.get('fighter2_id'))) for x in bouts[main_id] if x.get('fighter1_id') and x.get('fighter2_id')}
            for x in bouts.pop(o['event_id'], []):
                k1 = frozenset((norm(x['fighter1']), norm(x['fighter2'])))
                k2 = frozenset((x.get('fighter1_id'), x.get('fighter2_id')))
                if k1 in have or (x.get('fighter1_id') and x.get('fighter2_id') and k2 in have):
                    continue
                x['event_id'] = main_id
                bouts[main_id].append(x)
                have.add(k1)
            toks = (main.get('sources') or '').split()
            for t in (o.get('sources') or '').split():
                if t not in toks:
                    toks.append(t)
            main['sources'] = ' '.join(toks)
            if not main.get('venue'):
                main['venue'] = o.get('venue', '')
            events.pop(o['event_id'], None)
    # 同じ団体・同じ名前で、日付が3日以内の大会（2日間開催など）は1つにまとめる（初日の日付にする）
    byname = collections.defaultdict(list)
    for e in events.values():
        if bouts.get(e['event_id']):
            byname[(e['promotion'], e['name'])].append(e)
    for evs in byname.values():
        if len(evs) < 2:
            continue
        evs.sort(key=lambda e: e['date'])
        main = evs[0]
        for o in evs[1:]:
            try:
                gap = (datetime.date.fromisoformat(o['date']) - datetime.date.fromisoformat(main['date'])).days
            except ValueError:
                continue
            if gap > 3:
                main = o
                continue
            n0 = len(bouts[main['event_id']])
            for i, x in enumerate(bouts.pop(o['event_id'], [])):
                x['event_id'] = main['event_id']
                if str(x.get('match_no') or '').isdigit():
                    x['match_no'] = str(n0 + i + 1)
                bouts[main['event_id']].append(x)
            for t in (o.get('sources') or '').split():
                if t not in (main.get('sources') or '').split():
                    main['sources'] = ((main.get('sources') or '') + ' ' + t).strip()
            events.pop(o['event_id'], None)
    # 柔術・グラップリング・エキシビションだけの大会は載せない（MMAの記録なので）
    gp = set(site.get('grappling_promotions') or []) | set(site.get('bjj_promotions') or [])   # QUINTET などグラップリングの団体は、そのまま載せる
    for k in list(bouts):
        if bouts[k] and all(b.get('rule') for b in bouts[k]) and (events.get(k) or {}).get('promotion') not in gp:
            del bouts[k]
    # 載せない大会・試合（data/exclude.tsv：event_id, fighter1, fighter2, reason。選手名が空なら大会ごと）…未成年の試合など
    for x in read_tsv(os.path.join(DATA, 'exclude.tsv')):
        k = x['event_id']
        if not (x.get('fighter1') or '').strip():
            bouts.pop(k, None)
            events.pop(k, None)
        elif k in bouts:
            pair = frozenset((norm(x['fighter1']), norm(x['fighter2'])))
            bouts[k] = [b for b in bouts[k] if frozenset((norm(b['fighter1']), norm(b['fighter2']))) != pair]
    # 空欄だったラウンド・時間・階級を、資料で確かめた値で埋める（data/fills.tsv：promotion, date, fighter1_ja, fighter2_ja, field, value）
    fills = {}
    for f in read_tsv(os.path.join(DATA, 'fills.tsv')):
        fills[(f['date'], frozenset((norm(f['fighter1_ja']), norm(f['fighter2_ja']))), f['field'])] = f['value']
    if fills:
        for k in bouts:
            e = events.get(k) or {}
            for b in bouts[k]:
                pair = frozenset((norm(b['fighter1']), norm(b['fighter2'])))
                for fld in ('round', 'time', 'weight'):
                    v = fills.get((e.get('date'), pair, fld))
                    if v and not (b.get(fld) or '').strip():
                        b[fld] = v
    for k in bouts:
        for b in bouts[k]:
            b['method'] = methods.tidy(b.get('method'))   # 決まり手の書き方をそろえる（methods.py）
            b['weight'] = methods.weight(b.get('weight'))  # 階級の書き方をそろえる
        bouts[k].sort(key=lambda b: int(b['match_no']) if str(b.get('match_no') or '').isdigit() else 999)
    merge_fighters(events, bouts, fighters)
    for bl in bouts.values():
        for b in bl:
            for k in ('1', '2'):
                if b.get(f'fighter{k}_id') in renamed:
                    b[f'fighter{k}'] = renamed[b[f'fighter{k}_id']]
    # 柔術などの表彰台（data/podium.tsv：promotion, date, event_name_ja, division, place, name_ja, name_en, team, source_url）
    global PODIUM
    PODIUM = collections.defaultdict(list)
    key2id = {(e['promotion'], e['date'], methods.event_name(e['name'])): k for k, e in events.items()}
    for r in read_tsv(os.path.join(DATA, 'podium.tsv')):
        pr, d, nm = r.get('promotion') or 'jbjjf', r.get('date', ''), methods.event_name(r.get('event_name_ja'))
        k = key2id.get((pr, d, nm))
        if not k:
            k = 'j' + hashlib.md5(f'{pr}|{d}|{nm}'.encode()).hexdigest()[:8]
            events[k] = {'event_id': k, 'promotion': pr, 'date': d, 'name': nm, 'venue': r.get('venue', ''), 'sources': ''}
            key2id[(pr, d, nm)] = k
        e = events[k]
        u = r.get('source_url') or ''
        if u and u not in (e.get('sources') or '').split():
            e['sources'] = ((e.get('sources') or '') + ' ' + u).strip()
        PODIUM[k].append([r.get('division', ''), r.get('place', ''), r.get('name_ja') or r.get('name_en', ''), r.get('team', '')])
    return site, promos, events, bouts, fighters


PODIUM = {}
MERGED = {}   # 消えた選手番号 → まとめ先の選手番号（Wikipediaの記録の付け替えに使う）


def merge_fighters(events, bouts, fighters):
    """同じ選手が2つの番号に分かれているものをまとめ、番号のない名前を選手につなぐ。
    推測で別人をまとめないよう、次のときだけまとめる：
      ・名前が4文字以上（「アキラ」「豪」のようなリングネームは別人の可能性があるので除く）
      ・同じ日に両方の番号が試合をしていない
      ・同じ団体で試合をしていて、活動した年が重なるか5年以内に続いている"""
    dates = collections.defaultdict(set)
    proms = collections.defaultdict(set)
    for eid, bl in bouts.items():
        d = (events.get(eid) or {}).get('date', '')
        pr = (events.get(eid) or {}).get('promotion', '')
        for b in bl:
            for k in ('1', '2'):
                if b.get(f'fighter{k}_id'):
                    dates[b[f'fighter{k}_id']].add(d)
                    proms[b[f'fighter{k}_id']].add(pr)
    def key(n):
        return re.sub(r'[\s・･=＝.．　]', '', unicodedata.normalize('NFKC', n or '')).lower()
    groups = collections.defaultdict(list)
    for fid, n in fighters.items():
        if dates.get(fid):
            groups[key(n)].append(fid)
    for k, ids in groups.items():
        if len(ids) < 2 or len(k) < 4 or re.match(r'(?:キム|イ|パク|チェ|チョン|カン|リー|リ|ユン|ハン)[・･]', fighters[ids[0]]):
            continue   # 同じ名前の多い韓国・中国系の名前はまとめない
        ids.sort(key=lambda i: -len(dates[i]))
        main = ids[0]
        for o in ids[1:]:
            a, b = dates[main], dates[o]
            if a & b or not (proms[main] & proms[o]):
                continue
            ya = [int(x[:4]) for x in a if x[:4].isdigit()]; yb = [int(x[:4]) for x in b if x[:4].isdigit()]
            if not ya or not yb or min(yb) > max(ya) + 5 or min(ya) > max(yb) + 5:
                continue
            MERGED[o] = main
            dates[main] |= b
            proms[main] |= proms[o]
    uniq = {k: ids[0] for k, ids in groups.items() if len(k) >= 4 and len({MERGED.get(i, i) for i in ids}) == 1}
    for eid, bl in bouts.items():
        pr = (events.get(eid) or {}).get('promotion', '')
        for b in bl:
            for k in ('1', '2'):
                f = b.get(f'fighter{k}_id')
                if f in MERGED:
                    b[f'fighter{k}_id'] = MERGED[f]
                elif not f:
                    hit = uniq.get(key(b.get(f'fighter{k}')))
                    if hit and pr in proms[MERGED.get(hit, hit)]:   # 同じ団体に出ている同じ名前の選手だけにつなぐ
                        b[f'fighter{k}_id'] = MERGED.get(hit, hit)


def podium_html(ps):
    if not ps:
        return ''
    PL = {'1': '優勝', '2': '準優勝', '3': '3位'}
    rows = ''.join(f'<tr><td>{html.escape(p[0])}</td><td>{PL.get(str(p[1]), html.escape(str(p[1])))}</td><td>{html.escape(p[2])}</td><td>{html.escape(p[3])}</td></tr>' for p in ps)
    return f'<h2 class="sec">入賞者</h2><div class="tbl"><table><thead><tr><th>階級</th><th>順位</th><th>選手</th><th>所属</th></tr></thead><tbody>{rows}</tbody></table></div>'


def team_html(ts):
    if not ts:
        return ''
    rows = ''.join(f'<tr><td>{html.escape(t[0])}</td><td>{html.escape(t[1])}</td><td>{html.escape(t[2])}</td></tr>' for t in ts)
    return f'<h2 class="sec">出場チーム</h2><div class="tbl"><table><thead><tr><th>チーム</th><th>メンバー</th><th>成績</th></tr></thead><tbody>{rows}</tbody></table></div>'


def pname(promos, p):
    r = promos.get(p)
    return r['name'] if r and r.get('name') else p.replace('_', ' ').upper()


def write_json(name, obj):
    with open(os.path.join(OUT, 'data', name), 'w', encoding='utf-8') as fp:
        json.dump(obj, fp, ensure_ascii=False, separators=(',', ':'))


WIN = {'1': 1, '2': 2, 'draw': 'd', 'nc': 'nc'}


def head(site, title, desc, path, css_prefix=''):
    url = site['base_url'].rstrip('/') + '/' + path
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{html.escape(url)}">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{html.escape(url)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Dela+Gothic+One&family=Noto+Sans+JP:wght@400;500;700;900&display=swap">
<link rel="stylesheet" href="{css_prefix}style.css">
</head><body>'''


def static_header(pre):
    return f'''<header class="top"><div class="wrap">
<a class="logo" href="{pre}index.html"><b>日本MMA戦績録</b><span>JAPAN MMA RECORD</span></a>
<nav class="main" aria-label="メニュー"><a class="lnk" href="{pre}index.html#events">大会</a><a class="lnk" href="{pre}index.html#fighters">選手</a><a class="lnk" href="{pre}index.html#promotions">団体</a><a class="lnk" href="{pre}index.html#upcoming">今後の予定</a><a class="lnk" href="{pre}index.html#about">このサイトについて</a></nav>
<form class="hsearch" role="search" action="{pre}index.html" method="get"><label for="hq" style="position:absolute;left:-9999px">選手名・大会名で検索</label><input id="hq" name="q" type="search" placeholder="選手名・大会名で検索"><button type="submit">検索</button></form>
</div></header>'''


def foot(site, n_ev, n_b):
    return f'''<footer class="ft"><div class="wrap"><b>日本MMA戦績録</b><span>{n_ev:,}興行・{n_b:,}試合を収録　データ更新日 {site["built"]}　記録の出典は各大会ページに記載</span></div></footer></body></html>'''


def rt(b):
    r = b.get('round') or ''
    if r and not r.upper().endswith('R'):
        r += 'R'
    return ' '.join(x for x in (r, b.get('time') or '') if x)


def main():
    site, promos, events, bouts, fighters = load()
    site['built'] = datetime.date.today().isoformat()
    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, 'data'))
    os.makedirs(os.path.join(OUT, 'e'))
    os.makedirs(os.path.join(OUT, 'f'))

    ev = sorted((e for e in events.values() if bouts.get(e['event_id']) or PODIUM.get(e['event_id'])), key=lambda e: (e['date'], e['event_id']))
    for e in ev:
        bouts.setdefault(e['event_id'], [])
    ev_list = [[e['event_id'], e['date'], e['promotion'], e['name'], e.get('venue', ''),
                [s for s in (e.get('sources') or '').split(' ') if s], len(bouts[e['event_id']])] for e in ev]
    # 世界の団体・グラップリングの大会には、出場した日本人選手の名前を添える（一覧で見つけやすくするため）
    abroad = set(site.get('world_promotions') or []) | set(site.get('grappling_promotions') or []) | set(site.get('bjj_promotions') or [])
    in_jp = set()
    for e in ev:
        if e['promotion'] not in abroad:
            for b in bouts[e['event_id']]:
                in_jp.update(x for x in (b.get('fighter1_id'), b.get('fighter2_id')) if x)
    def is_jp(fid, n):
        if re.search(r'[ぁ-ん一-龥々]', n or '') and not re.match(r'(?:キム|イ|パク|チェ|チョン|カン|リー|リ|ソン|ワン|チャン|ジャン|リウ|リュウ)[・･]', n):
            return True
        return bool(fid and fid in in_jp and re.fullmatch(r'[A-Z0-9.\-"“” ]{2,}', n or ''))
    for row, e in zip(ev_list, ev):
        if e['promotion'] in abroad:
            names = []
            for b in bouts[e['event_id']]:
                for k in ('1', '2'):
                    n = b[f'fighter{k}']
                    if is_jp(b.get(f'fighter{k}_id'), n) and n not in names:
                        names.append(n)
            row.append(names)
        else:
            row.append([])
    # 団体公式のYouTube動画（data/videos.tsv：promotion, date, fighter1, fighter2, url, title, channel）
    vids = {}
    for r in read_tsv(os.path.join(DATA, 'videos.tsv')):
        u = r.get('url') or ''
        if not re.match(r'https://(www\.)?(youtube\.com|youtu\.be)/', u):
            continue
        vids[(r.get('date', ''), frozenset((norm(r.get('fighter1')), norm(r.get('fighter2')))))] = u
    for e in ev:
        for b in bouts[e['event_id']]:
            b['video'] = vids.get((e['date'], frozenset((norm(b['fighter1']), norm(b['fighter2'])))), '')
    bout_out = {}
    used = set()
    for e in ev:
        rows = []
        for b in bouts[e['event_id']]:
            rows.append([int(b['match_no']) if str(b.get('match_no') or '').isdigit() else 0,
                         b.get('fighter1_id') or '', b['fighter1'], b.get('fighter2_id') or '', b['fighter2'],
                         WIN.get(b.get('winner') or '', ''), b.get('method') or '', b.get('round') or '',
                         b.get('time') or '', b.get('weight') or '', 1 if (b.get('note') or '') == 'uncertain' else 0, b.get('rule') or '', b.get('video') or ''])
            used.update(x for x in (b.get('fighter1_id'), b.get('fighter2_id')) if x)
        bout_out[e['event_id']] = rows
    fout = {i: [fighters.get(i, ''), '', 1] for i in used if fighters.get(i)}
    meta = {'built': site['built'], 'plabel': {p: pname(promos, p) for p in {e['promotion'] for e in ev}},
            'listed': [p for p, r in promos.items() if r.get('main')],
            'world': site.get('world_promotions') or [], 'grappling': site.get('grappling_promotions') or [], 'bjj': site.get('bjj_promotions') or [], 'first': site.get('first_promotions') or []}
    # 団体戦のチームとメンバー（data/teams.tsv）
    teams = collections.defaultdict(list)
    by_dn = {}
    for e in ev:
        by_dn.setdefault((e['date'], methods.event_name(e['name'])), e['event_id'])
        by_dn.setdefault(('', methods.event_name(e['name'])), e['event_id'])
    for r in read_tsv(os.path.join(DATA, 'teams.tsv')):
        nm = methods.event_name(r.get('event_name_ja'))
        eid = by_dn.get((r.get('date', ''), nm)) or by_dn.get(('', nm))
        if eid:
            teams[eid].append([r.get('team', ''), r.get('members', ''), r.get('result', '')])
    meta['teams'] = teams
    upcoming = []
    up_path = os.path.join(DATA, 'upcoming.json')
    if os.path.exists(up_path):
        today = site['built']
        upcoming = [u for u in json.load(open(up_path, encoding='utf-8')) if (u.get('d') or '') >= today]
    write_json('events.json', ev_list)
    write_json('bouts.json', bout_out)
    write_json('fighters.json', fout)
    meta['pd'] = sorted(k for k in PODIUM if k in {e['event_id'] for e in ev})
    os.makedirs(os.path.join(OUT, 'pd'), exist_ok=True)
    for k in meta['pd']:
        with open(os.path.join(OUT, 'pd', f'{k}.json'), 'w', encoding='utf-8') as fp:
            json.dump(PODIUM[k], fp, ensure_ascii=False, separators=(',', ':'))
    write_json('meta.json', meta)
    write_json('upcoming.json', upcoming)

    n_b = sum(len(v) for v in bout_out.values())
    # トップ（検索・一覧つきのページ）
    shutil.copy(os.path.join(TPL, 'style.css'), os.path.join(OUT, 'style.css'))
    shutil.copy(os.path.join(TPL, 'app.js'), os.path.join(OUT, 'app.js'))
    body = open(os.path.join(TPL, 'body.html'), encoding='utf-8').read()
    desc = f'1989年の修斗から最新の大会まで、日本の総合格闘技（MMA）{len(ev_list):,}興行・{n_b:,}試合の記録を出典つきで検索できるデータベース。'
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as fp:
        fp.write(head(site, '日本MMA戦績録', desc, '') + body + '<script src="app.js"></script></body></html>')

    # 大会ごとの静的ページ（検索エンジン用・リンク共有用）
    e_by = collections.defaultdict(list)
    for e in ev:
        for b in bouts[e['event_id']]:
            for k in ('1', '2'):
                if b.get(f'fighter{k}_id'):
                    e_by[b[f'fighter{k}_id']].append((e, b, int(k)))
    urls = ['']
    for e in ev:
        eid = e['event_id']
        rows = []
        for b in bouts[eid]:
            w = b.get('winner') or ''
            a, c = ('1', '2') if w != '2' else ('2', '1')
            res = 'WIN' if w in ('1', '2') else {'draw': '引分', 'nc': '無効'}.get(w, '—')
            def fl(k):
                fid = b.get(f'fighter{k}_id')
                n = html.escape(b[f'fighter{k}'])
                return f'<a class="u nb" href="../f/{fid}.html">{n}</a>' if fid and fid in fout else f'<span class="nb">{n}</span>'
            unc = '<span class="unc">未確定</span>' if b.get('note') == 'uncertain' else ''
            rtag = f'<span class="unc">{html.escape(b["rule"])}・戦績に数えない</span>' if b.get('rule') else ''
            if b.get('video'):
                rtag += f' <a class="vid" href="{html.escape(b["video"])}" target="_blank" rel="noopener">▶ 公式動画</a>'
            rows.append(f'<tr><td class="num">{html.escape(str(b.get("match_no") or ""))}</td><td><span class="rs {"w" if res == "WIN" else "o"}">{res}</span></td>'
                        f'<td>{fl(a)}</td><td><span class="def">{"def." if res == "WIN" else "vs"}</span> {fl(c)}{unc}</td>'
                        f'<td>{html.escape(b.get("method") or "")}{rtag}</td><td class="num">{html.escape(rt(b))}</td><td>{html.escape(b.get("weight") or "")}</td></tr>')
        srcs = [s for s in (e.get('sources') or '').split(' ') if s]
        src_html = '　'.join(f'<a href="{html.escape(s)}" rel="noopener">{html.escape(re.sub("^https?://", "", urllib.parse.unquote(s))[:70])}</a>' if s.startswith('http') else html.escape(s) for s in srcs)
        pn = pname(promos, e['promotion'])
        title = f'{e["name"]}（{e["date"]}）｜日本MMA戦績録'
        page = (head(site, title, f'{pn} {e["name"]} {e["date"]} の全試合結果（{len(bouts[eid])}試合）', f'e/{eid}.html', '../') + static_header('../') +
                f'<main class="wrap"><p class="crumb"><a class="lnk" href="../index.html">トップ</a>　›　<a class="lnk" href="../index.html#p-{e["promotion"].replace("_", "-")}">{html.escape(pn)}</a></p>'
                f'<div class="ph"><div><span class="badge">{html.escape(pn)}</span><h1>{html.escape(e["name"])}</h1><p class="sub">{html.escape(e["date"])}　{html.escape(e.get("venue") or "")}</p></div></div>'
                f'<div class="tbl"><table><thead><tr><th class="num">No.</th><th>結果</th><th>勝者</th><th>対戦相手</th><th>決まり手</th><th class="num">R・時間</th><th>階級・ルール</th></tr></thead><tbody>{"".join(rows)}</tbody></table></div>'
                + team_html(teams.get(eid)) + podium_html(PODIUM.get(eid)) +
                f'<p class="src">出典：{src_html}</p></main>' + foot(site, len(ev_list), n_b))
        with open(os.path.join(OUT, 'e', f'{eid}.html'), 'w', encoding='utf-8') as fp:
            fp.write(page)
        urls.append(f'e/{eid}.html')

    # Wikipediaの通算戦績（wiki_fetch.py が取り込んだもの）
    os.makedirs(os.path.join(OUT, 'w'), exist_ok=True)
    wrec = {}
    for r in read_tsv(os.path.join(DATA, 'wiki', 'records.tsv')):
        r['fighter_id'] = MERGED.get(r['fighter_id'], r['fighter_id'])
        wrec.setdefault(r['fighter_id'], r)
    wb = collections.defaultdict(list)
    for r in read_tsv(os.path.join(DATA, 'wiki', 'bouts.tsv')):
        wb[MERGED.get(r['fighter_id'], r['fighter_id'])].append(r)
    wextra = {}
    for fid, r in wrec.items():
        if fid not in fout:
            continue
        have = set()
        for e, b, side in e_by.get(fid, []):
            o = b['fighter2'] if side == 1 else b['fighter1']
            have.add((e['date'], norm(o)))
        dates = {e['date'] for e, b, side in e_by.get(fid, [])}
        x = [[w['date'], w['result'], w['opponent'], methods.tidy(w['method']), w['event']] for w in wb.get(fid, [])
             if (w['date'], norm(w['opponent'])) not in have and w['date'] not in dates]
        wextra[fid] = x
        with open(os.path.join(OUT, 'w', f'{fid}.json'), 'w', encoding='utf-8') as fp:
            json.dump({'t': r['wiki_title'], 'u': r['source_url'],
                       'rec': [int(r['wins']), int(r['losses']), int(r['draws']), int(r['no_contests'])], 'x': x}, fp, ensure_ascii=False, separators=(',', ':'))

    # 選手ごとの静的ページ
    for fid, _v in fout.items():
        name = _v[0]
        lst = sorted(e_by.get(fid, []), key=lambda x: x[0]['date'], reverse=True)
        w = l = d = nc = 0
        rows = []
        for e, b, side in lst:
            win = b.get('winner') or ''
            ok = 'o'
            c1 = 0 if b.get('rule') else 1          # 柔術・グラップリング・エキシビションは戦績に数えない
            if win == str(side): w += c1; r = '勝'; ok = 'w'
            elif win in ('1', '2'): l += c1; r = '負'; ok = 'l'
            elif win == 'draw': d += c1; r = '分'
            elif win == 'nc': nc += c1; r = '無効'
            else: r = '—'
            rtag = f'<span class="unc">{html.escape(b["rule"])}・戦績に数えない</span>' if b.get('rule') else ''
            ok2 = '2' if side == 1 else '1'
            oid = b.get(f'fighter{ok2}_id'); on = html.escape(b[f'fighter{ok2}'])
            opp = f'<a class="u nb" href="{oid}.html">{on}</a>' if oid and oid in fout else f'<span class="nb">{on}</span>'
            rows.append((e['date'], f'<tr><td><span class="rs {ok}">{r}</span></td><td>{opp}</td><td><a class="u" href="../e/{e["event_id"]}.html">{html.escape(e["name"])}</a></td>'
                        f'<td class="num">{html.escape(e["date"])}</td><td>{html.escape(b.get("method") or "")}{rtag}</td><td class="num">{html.escape(rt(b))}</td></tr>'))
        rec = f'{w}勝{l}敗{d}分' + (f'{nc}無効試合' if nc else '')
        note = '※日本で開かれた大会・日本の団体の大会と、世界の主要団体（UFC・ONE・PFL・Bellatorなど）での試合の戦績です。そのほかの海外の大会での試合は含みません'
        if fid in wrec:
            r0 = wrec[fid]
            rec = f'通算 {r0["wins"]}勝{r0["losses"]}敗{r0["draws"]}分' + (f'{r0["no_contests"]}無効試合' if r0['no_contests'] not in ('0', '') else '')
            note = f'通算戦績はWikipedia「<a class="u" href="{html.escape(r0["source_url"])}">{html.escape(r0["wiki_title"])}</a>」の戦績表によります（海外の試合を含む）。印のついた試合はWikipediaからの記録です。'
            RS = {'win': ('w', '勝'), 'loss': ('l', '負'), 'draw': ('o', '分'), 'nc': ('o', '無効')}
            for x in wextra.get(fid, []):
                c, t = RS.get(x[1], ('o', '—'))
                rows.append((x[0], f'<tr><td><span class="rs {c}">{t}</span></td><td><span class="nb">{html.escape(x[2])}</span></td><td>{html.escape(x[4])}<span class="unc">Wikipedia</span></td>'
                                   f'<td class="num">{html.escape(x[0])}</td><td>{html.escape(x[3])}</td><td class="num"></td></tr>'))
        page = (head(site, f'{name}の戦績｜日本MMA戦績録', f'{name}（総合格闘技）の戦績 {rec}。全{len(lst)}試合の結果と出典。', f'f/{fid}.html', '../') + static_header('../') +
                f'<main class="wrap"><p class="crumb"><a class="lnk" href="../index.html">トップ</a>　›　<a class="lnk" href="../index.html#fighters">選手</a></p>'
                f'<div class="ph"><div><h1>{html.escape(name)}</h1><p class="sub">{rec}</p><p class="sub" style="font-size:13px;color:var(--fg3)">{note}</p></div></div>'
                f'<div class="tbl"><table><thead><tr><th>結果</th><th>対戦相手</th><th>大会</th><th class="num">日付</th><th>決まり手</th><th class="num">R・時間</th></tr></thead><tbody>{"".join(h for d, h in sorted(rows, key=lambda t: t[0], reverse=True))}</tbody></table></div></main>'
                + foot(site, len(ev_list), n_b))
        with open(os.path.join(OUT, 'f', f'{fid}.html'), 'w', encoding='utf-8') as fp:
            fp.write(page)
        urls.append(f'f/{fid}.html')

    # 検索エンジン向け
    base = site['base_url'].rstrip('/') + '/'
    chunk = 40000
    maps = []
    for i in range(0, len(urls), chunk):
        name = f'sitemap-{i // chunk + 1}.xml'
        with open(os.path.join(OUT, name), 'w', encoding='utf-8') as fp:
            fp.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for u in urls[i:i + chunk]:
                fp.write(f'<url><loc>{html.escape(base + u)}</loc></url>\n')
            fp.write('</urlset>\n')
        maps.append(name)
    with open(os.path.join(OUT, 'sitemap.xml'), 'w', encoding='utf-8') as fp:
        fp.write('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for m in maps:
            fp.write(f'<sitemap><loc>{html.escape(base + m)}</loc></sitemap>\n')
        fp.write('</sitemapindex>\n')
    with open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8') as fp:
        fp.write(f'User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n')
    with open(os.path.join(OUT, '.nojekyll'), 'w') as fp:
        fp.write('')
    if site.get('custom_domain'):
        with open(os.path.join(OUT, 'CNAME'), 'w') as fp:
            fp.write(site['custom_domain'].strip() + '\n')
    # 404
    with open(os.path.join(OUT, '404.html'), 'w', encoding='utf-8') as fp:
        fp.write(head(site, 'ページが見つかりません｜日本MMA戦績録', 'ページが見つかりません', '404.html', '/') + static_header('/') +
                 '<main class="wrap"><div class="sh"><h1>ページが見つかりません</h1></div><p class="note" style="margin-top:20px"><a class="u" href="/">トップに戻る</a></p></main>' + foot(site, len(ev_list), n_b))
    print(f'完成: {len(ev_list):,}興行・{n_b:,}試合・{len(fout):,}選手、ページ数 {len(urls):,} → {OUT}')


if __name__ == '__main__':
    main()
