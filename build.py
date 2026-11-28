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


def en_method(m):
    """英語の決まり手（TKO (Punches) など）を日本語の書き方にそろえる。"""
    m = (m or '').strip()
    k = re.match(r'^([A-Za-z./ -]+?)\s*(?:\((.*)\))?$', m)
    if not k:
        return methods.tidy(m)
    head, inner = k.group(1).strip().lower(), (k.group(2) or '').strip()
    if head.startswith('submission') or head.startswith('technical submission'):
        return methods.tidy(f'一本（{inner}）' if inner else '一本')
    if head.startswith('tko') or head.startswith('technical knockout'):
        return 'TKO（ドクターストップ）' if 'doctor' in inner.lower() else 'TKO'
    if head.startswith('ko'):
        return 'KO'
    if head.startswith('decision') or head.startswith('technical decision'):
        il = inner.lower()
        return '判定2-1' if 'split' in il else '判定2-0' if 'majority' in il else '判定3-0' if 'unanimous' in il else '判定'
    if head.startswith('draw'):
        return '引き分け'
    if head.startswith('no contest') or head == 'nc':
        return 'ノーコンテスト'
    if head.startswith('dq') or 'disqualif' in head:
        return '反則'
    return methods.tidy(m)


def title_of(w):
    """階級の欄に書かれたタイトルマッチなどの文字を取り出す（titles.tsv にないもの用）。"""
    for x in (w or '').split('・'):
        if re.search(r'タイトルマッチ|王座|挑戦者決定|選手権試合|GP決勝|グランプリ決勝|トーナメント決勝|防衛戦', x) and len(x) <= 40:
            x = re.sub(r'\s*\d+分\d*R?.*$|\s*\d+分1本勝負.*$', '', x).strip()
            x = re.sub(r'^(?:アマチュア)?(?:キック|ボクシング|MMA)\s*[(（]', '', x).strip(' )）')
            cls = (w or '').split('・')[0]
            if '級' not in x and re.search(r'級$|kg契約$', cls) and not re.search(r'トーナメント|昇格', x):
                x = cls + x
            return x
    return ''


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

    # 同じ人だと資料で確かめた試合を選手につなぐ（data/links.tsv：date, name, fighter_id, source_url）
    links = {(r['date'], norm(r['name'])): r['fighter_id'] for r in read_tsv(os.path.join(DATA, 'links.tsv'))}
    if links:
        for k in bouts:
            e = events.get(k) or {}
            for b in bouts[k]:
                for n in ('1', '2'):
                    fid = links.get((e.get('date'), norm(b[f'fighter{n}'])))
                    if fid and not b.get(f'fighter{n}_id'):
                        b[f'fighter{n}_id'] = fid
                        fighters.setdefault(fid, b[f'fighter{n}'].replace('　', '').replace(' ', ''))   # 記録のない選手は新しく作る
    # 柔術の試合番号（マット番号つき、data/bjj_mats.tsv：date, fighter1, fighter2, label 例「MAT2-33・準々決勝」）
    mats = {}
    for r in read_tsv(os.path.join(DATA, 'bjj_mats.tsv')):
        k0 = (r['date'], frozenset((norm(r['fighter1']), norm(r['fighter2']))), norm((r.get('division') or '').split('・')[0]))
        no = re.match(r'MAT\d+-(\d+)', r['label'])
        mats[k0 + (no.group(1) if no else '',)] = r['label']
        mats.setdefault(k0, r['label'])
    for k in bouts:
        e = events.get(k) or {}
        for b in bouts[k]:
            k0 = (e.get('date'), frozenset((norm(b['fighter1']), norm(b['fighter2']))), norm((b.get('weight') or '').split('・')[0]))
            b['mat'] = mats.get(k0 + (str(b.get('match_no') or ''),)) or mats.get(k0, '')
    # 大会の名前・日付・会場の訂正（data/event_fixes.tsv：event_id, field, value, source）
    for r in read_tsv(os.path.join(DATA, 'event_fixes.tsv')):
        e = events.get(r.get('event_id'))
        if e and r.get('field') in ('name', 'date', 'venue') and (r.get('value') or '').strip():
            e[r['field']] = r['value'].strip()
        elif e and r.get('field') == 'merge' and r.get('value') in events and r['value'] != r['event_id']:
            # 同じ大会が2つに分かれて登録されているとき、試合を1つの大会にまとめる
            tgt = r['value']
            have = {frozenset((b.get('fighter1'), b.get('fighter2'))) for b in bouts.get(tgt, [])}
            mv = [b for b in bouts.pop(r['event_id'], []) if frozenset((b.get('fighter1'), b.get('fighter2'))) not in have]
            used_no = {str(b.get('match_no')) for b in bouts.get(tgt, []) if str(b.get('match_no') or '') not in ('', '0')}
            n = max([int(x) for x in used_no if x.isdigit()] + [int(b['match_no']) for b in mv if str(b.get('match_no') or '').isdigit()] or [0])
            for b in mv:
                no = str(b.get('match_no') or '')
                # 試合番号が付いていて、まとめ先と重ならないときはそのまま使う（同じ大会の別の資料なので番号は共通）
                if no in ('', '0') or no in used_no:
                    n += 1
                    b['match_no'] = n
                used_no.add(str(b['match_no']))
                b['event_id'] = tgt
                bouts.setdefault(tgt, []).append(b)
            for u in (events[r['event_id']].get('sources') or '').split():
                if u not in (events[tgt].get('sources') or '').split():
                    events[tgt]['sources'] = ((events[tgt].get('sources') or '') + ' ' + u).strip()
            events.pop(r['event_id'], None)
    # 会場が空の大会を補う（data/venues.tsv：event_id, promotion, date, name, venue, source_url）
    for r in read_tsv(os.path.join(DATA, 'venues.tsv')):
        e = events.get(r.get('event_id'))
        if e and not (e.get('venue') or '').strip() and (r.get('venue') or '').strip():
            e['venue'] = r['venue'].strip()
            u = (r.get('source_url') or '').strip()
            if u and u not in (e.get('sources') or '').split():
                e['sources'] = ((e.get('sources') or '') + ' ' + u).strip()
    # 大会の試合をまるごと作り直す（data/replace_bouts.tsv：取り込んだ資料の組み合わせが崩れていた大会を、公式の資料から書き直したもの）
    rep = collections.defaultdict(list)
    for r in read_tsv(os.path.join(DATA, 'replace_bouts.tsv')):
        rep[r['event_id']].append(r)
    for eid, rows in rep.items():
        if eid in events:
            # 前の試合データに付いていた選手番号は、名前が同じならそのまま使う
            old = {}
            for x in bouts.get(eid, []):
                for k in ('1', '2'):
                    if x.get(f'fighter{k}_id'):
                        old.setdefault(re.sub(r'[\s　“”"]', '', x.get(f'fighter{k}') or ''), x[f'fighter{k}_id'])
            # 前のデータは組み合わせが崩れていたので、番号の選手名（選手名簿の名前）と一致するときだけ使う
            nn = lambda n: re.sub(r'[\s　“”"]', '', n or '')
            oid = lambda n: old.get(nn(n), '') if nn(fighters.get(old.get(nn(n), ''), '')) == nn(n) else ''
            bouts[eid] = [{'event_id': eid, 'match_no': r['match_no'], 'fighter1': r['fighter1'], 'fighter2': r['fighter2'], 'fighter1_id': r.get('fighter1_id') or oid(r['fighter1']), 'fighter2_id': r.get('fighter2_id') or oid(r['fighter2']),
                           'winner': r['winner'], 'method': r['method'], 'round': r['round'], 'time': r['time'], 'weight': r['weight'], 'note': '', 'rule': ''} for r in rows]
            for u in {r['source'] for r in rows if r.get('source')}:
                if u not in (events[eid].get('sources') or '').split():
                    events[eid]['sources'] = ((events[eid].get('sources') or '') + ' ' + u).strip()
    # 個別の訂正
    for f in read_tsv(os.path.join(DATA, 'fixes.tsv')):
        for b in bouts.get(f['event_id'], []):
            mn = str(f['match_no'])
            hit = (mn[5:] in (b.get('fighter1') or '') + ' ' + (b.get('fighter2') or '')) if mn.startswith('name:') else str(b.get('match_no')) == mn   # 「name:選手名」なら名前で試合を特定する
            if hit and f['field'] in b:
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
            # 柔術は同じ日・同じ会場・同じトーナメント表で別の大会（ノービス選手権など）が行われるので、名前の違う大会はまとめない
            if o['promotion'] in (site.get('bjj_promotions') or []) and methods.event_name(o['name']) != methods.event_name(main['name']):
                continue
            same_su =o['promotion'] in (site.get('standup_promotions') or []) and not (re.search(r'第\d部', o['name']) and re.search(r'第\d部', main['name']))   # 立ち技は同じ日の同じ団体を1大会にまとめる
            if not same_su and not (src(o) & src(main)) and src(o) and ' - ' not in o['name'] + main['name'] and not methods.headline(o['name']) and len(o['name'].strip()) > 4:
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
            # 会場が違うものは、名前が同じでも別の大会（「プロフェッショナル修斗公式戦」のような一般的な名前の別大会がある）
            v1, v2 = re.sub(r'\s', '', main.get('venue') or ''), re.sub(r'\s', '', o.get('venue') or '')
            if gap > 3 or (v1 and v2 and v1 not in v2 and v2 not in v1):
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
    gp = set(site.get('grappling_promotions') or []) | set(site.get('bjj_promotions') or []) | set(site.get('standup_promotions') or []) | set(site.get('keep_promotions') or [])   # QUINTET などグラップリングの団体は、そのまま載せる
    for k in list(bouts):
        if bouts[k] and all(b.get('rule') for b in bouts[k]) and (events.get(k) or {}).get('promotion') not in gp:
            del bouts[k]
    # 立ち技の団体（K-1・SHOOT BOXINGなど）の大会で、MMAルールの試合があったものは名前に（MMAルールあり）と付ける
    su = set(site.get('standup_promotions') or [])
    for k, bl in bouts.items():
        e = events.get(k)
        if e and e.get('promotion') in su and any(not (b.get('rule') or '').strip() for b in bl) and 'MMAルールあり' not in e['name']:
            e['name'] = re.sub(r'（MMAは[^（）]*）', '', e['name']).strip() + '（MMAルールあり）'
    # 試合順が逆に記録されている大会（data/reorder.tsv：event_id, note）は番号を付け直す（メインが最後になるように）
    for x in read_tsv(os.path.join(DATA, 'reorder.tsv')):
        bl = bouts.get(x['event_id']) or []
        bl.sort(key=lambda b: int(b['match_no']) if str(b.get('match_no') or '').isdigit() else 0, reverse=True)
        for i, b in enumerate(bl, 1):
            b['match_no'] = str(i)
    # 載せない大会・試合（data/exclude.tsv：event_id, fighter1, fighter2, reason。選手名が空なら大会ごと）…MMA以外の試合など
    for x in read_tsv(os.path.join(DATA, 'exclude.tsv')):
        k = x['event_id']
        if not (x.get('fighter1') or '').strip():
            bouts.pop(k, None)
            events.pop(k, None)
        elif k in bouts:
            pair = frozenset((norm(x['fighter1']), norm(x['fighter2'])))
            bouts[k] = [b for b in bouts[k] if frozenset((norm(b['fighter1']), norm(b['fighter2']))) != pair]
    # タイトルマッチ・王座決定戦・次期挑戦者決定戦など（data/titles.tsv：promotion, date, fighter1_ja, fighter2_ja, label, source_url）
    titles = {}
    for t in read_tsv(os.path.join(DATA, 'titles.tsv')):
        if (t.get('label') or '').strip():
            titles[(t['date'], frozenset((norm(t['fighter1_ja']), norm(t['fighter2_ja']))))] = (t['label'].strip(), (t.get('note') or '').strip())
    for k in bouts:
        e = events.get(k) or {}
        for b in bouts[k]:
            b['title'], b['tnote'] = titles.get((e.get('date'), frozenset((norm(b['fighter1']), norm(b['fighter2'])))), ('', ''))
    # 空欄だったラウンド・時間・階級を、資料で確かめた値で埋める（data/fills.tsv：promotion, date, fighter1_ja, fighter2_ja, field, value）
    fills = {}
    for f in read_tsv(os.path.join(DATA, 'fills.tsv')):
        fills[(f['date'], frozenset((norm(f['fighter1_ja']), norm(f['fighter2_ja']))), f['field'])] = f['value']
    if fills:
        for k in bouts:
            if k in rep:   # 公式資料から作り直した大会には、ほかの資料からの補いを入れない
                continue
            e = events.get(k) or {}
            for b in bouts[k]:
                pair = frozenset((norm(b['fighter1']), norm(b['fighter2'])))
                for fld in ('round', 'time', 'weight'):
                    v = fills.get((e.get('date'), pair, fld))
                    if v and not (b.get(fld) or '').strip():
                        b[fld] = v
    bjjp = set(site.get('bjj_promotions') or [])
    for k in bouts:
        for b in bouts[k]:
            b['method'], b['round'], b['time'] = methods.split_rt(b.get('method'), b.get('round'), b.get('time'))   # 決まり手の欄に書かれたラウンド・時間を欄に移す
            b['method'] = methods.tidy(b.get('method'))   # 決まり手の書き方をそろえる（methods.py）
            b['time'] = methods.time(b.get('time'))       # 時間の書き方をそろえる（「2分43秒」→「2:43」など）
            if b.get('winner') == 'draw' and (b.get('method') or '').strip() == '時間切れ':
                b['method'] = '引き分け（時間切れ）'
            # 「0ラウンド」「0:00」は資料に記録がないときの埋め草なので空欄（不明）にする
            if str(b.get('round') or '').strip() == '0':
                b['round'] = ''
            if str(b.get('time') or '').strip() in ('0:00', '00:00'):
                b['time'] = ''
            if (events.get(k) or {}).get('promotion') in ('kit', 'art', 'deepx', 'ifpro_gi'):   # プロ柔術・DEEP X：階級だけを書く（ノーギのときだけ「ノーギ」）
                w = re.sub(r'\s*[・/]\s*(柔術\s*[（(]道着[）)]|グラップリング\s*[（(][^）)]*[）)]|グラップリング$)', '', b.get('weight') or '')
                b['weight'] = re.sub(r'\s*[・/]\s*柔術\s*[（(]ノーギ[）)]', '', w).strip()
            elif (events.get(k) or {}).get('promotion') in bjjp:   # 柔術はカテゴリー名をそのまま（ルール名は書かない）
                b['weight'] = re.sub(r'\s*[・/]\s*柔術\s*[（(][^）)]*ルール[）)]|\s*[・/]\s*柔術ルール', '', b.get('weight') or '').strip()
            else:
                b['weight'] = methods.weight(b.get('weight'))  # 階級の書き方をそろえる
        if any(str(b.get('match_no') or '').isdigit() and int(b['match_no']) > 0 for b in bouts[k]):
            bouts[k].sort(key=lambda b: int(b['match_no']) if str(b.get('match_no') or '').isdigit() else 999)
        else:   # 試合番号の記録がない大会は、トーナメントの段階（1回戦→準々決勝→準決勝→決勝）の順に並べる
            def stage(b):
                t = (b.get('weight') or '') + ' ' + (b.get('note') or '')
                for i, kw in enumerate(['オープニング', 'リザーブ', '1回戦', '一回戦', '2回戦', '二回戦', '準々決勝', '準決勝', '決勝']):
                    pass
                if re.search(r'オープニング|プレリミナリー', t): return 0
                if re.search(r'リザーブ', t): return 1
                if re.search(r'準々決勝', t): return 4
                if re.search(r'準決勝', t): return 5
                if re.search(r'決勝', t): return 7
                if re.search(r'[1１一]回戦', t): return 2
                if re.search(r'[2２二]回戦', t): return 3
                return 6
            bouts[k] = [b for _, b in sorted(enumerate(bouts[k]), key=lambda x: (stage(x[1]), x[0]))]
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
        if pr == 'jbjjf' and re.search(r'(?i)Ground\s*Impact|グラウンドインパクト|グランドインパクト|デラヒーバ杯|De\s*La\s*Riva\s*CUP|KBJJA', nm or ''):
            pr = 'groundimpact'   # IF-PROJECT の大会
        k = key2id.get((pr, d, nm)) or key2id.get(('groundimpact', d, nm))
        if not k:
            k = 'j' + hashlib.md5(f'{pr}|{d}|{nm}'.encode()).hexdigest()[:8]
            events[k] = {'event_id': k, 'promotion': pr, 'date': d, 'name': nm, 'venue': r.get('venue', ''), 'sources': ''}
            key2id[(pr, d, nm)] = k
        e = events[k]
        u = r.get('source_url') or ''
        if u and u not in (e.get('sources') or '').split():
            e['sources'] = ((e.get('sources') or '') + ' ' + u).strip()
        PODIUM[k].append([r.get('division', ''), r.get('place', ''), r.get('name_ja') or r.get('name_en', ''), r.get('team', ''), (r.get('entrants') or '').strip()])
    # 公開を保留している団体（site.json の hidden_promotions）は載せない
    hide = set(site.get('hidden_promotions') or [])
    for k in [k for k, e in events.items() if e.get('promotion') in hide]:
        events.pop(k, None); bouts.pop(k, None); PODIUM.pop(k, None)
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
                    if not hit:
                        continue
                    h = MERGED.get(hit, hit)
                    d = (events.get(eid) or {}).get('date', '')
                    ys = [int(x[:4]) for x in dates[h] if x[:4].isdigit()]
                    # 同じ団体に出ている同じ名前の選手につなぐ。別の団体でも、名前が4文字以上で、
                    # その選手の活動期間（前後3年）の中の試合で、同じ日に別の試合をしていなければつなぐ
                    near = d[:4].isdigit() and ys and min(ys) - 3 <= int(d[:4]) <= max(ys) + 3 and d not in dates[h]
                    if pr in proms[h] or near:
                        b[f'fighter{k}_id'] = h


def podium_html(ps):
    if not ps:
        return ''
    PL = {'1': '優勝', '2': '準優勝', '3': '3位'}
    rows = ''.join(f'<tr><td>{html.escape(p[0])}{"（" + p[4] + "人参加）" if len(p) > 4 and p[4] else ""}</td><td>{PL.get(str(p[1]), html.escape(str(p[1])))}</td><td>{html.escape(p[2])}</td><td>{html.escape(p[3])}</td></tr>' for p in ps)
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


def head(site, title, desc, path, css_prefix='', ld=None):
    url = site['base_url'].rstrip('/') + '/' + path
    # 検索エンジン向けの構造化データ（JSON-LD）。</ を含む文字はエスケープする
    ldh = ''.join('<script type="application/ld+json">' + json.dumps(x, ensure_ascii=False, separators=(',', ':')).replace('</', '<\\/') + '</script>\n' for x in (ld or []))
    return f'''<!doctype html>
<html lang="ja"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{html.escape(title)}</title>
<meta name="description" content="{html.escape(desc)}">
<link rel="canonical" href="{html.escape(url)}">
<link rel="alternate" type="application/rss+xml" title="本日の大会・過去のこの日の大会" href="{site['base_url'].rstrip('/')}/onthisday.xml">
<meta property="og:title" content="{html.escape(title)}"><meta property="og:description" content="{html.escape(desc)}">
<meta property="og:type" content="website"><meta property="og:url" content="{html.escape(url)}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Anton&family=Dela+Gothic+One&family=Noto+Sans+JP:wght@400;500;700;900&display=swap">
<link rel="stylesheet" href="{css_prefix}style.css">
{ldh}</head><body>'''


def static_header(pre):
    return f'''<header class="top"><div class="wrap">
<a class="logo" href="{pre}index.html"><b>日本MMA戦績録</b><span>JAPAN MMA RECORD</span></a>
<nav class="main" aria-label="メニュー"><a class="lnk" href="{pre}index.html#events">大会</a><a class="lnk" href="{pre}index.html#fighters">選手</a><a class="lnk" href="{pre}index.html#promotions">団体</a><a class="lnk" href="{pre}index.html#champions">歴代王者</a><a class="lnk" href="{pre}index.html#upcoming">今後の予定</a><a class="lnk" href="{pre}index.html#about">このサイトについて</a></nav>
<form class="hsearch" role="search" action="{pre}index.html" method="get"><label for="hq" style="position:absolute;left:-9999px">選手名・大会名で検索</label><input id="hq" name="q" type="search" placeholder="選手名・大会名で検索"><button type="submit">検索</button></form>
</div></header>'''


def foot(site, n_ev, n_b):
    return f'''<footer class="ft"><div class="wrap"><b>日本MMA戦績録</b><span>{n_ev:,}興行・{n_b:,}試合を収録　データ更新日 {site["built"]}　記録の出典は各大会ページに記載</span><span>お問い合わせ：japan.mma.record@gmail.com</span></div></footer></body></html>'''


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

    # 団体戦の結果（data/teams.tsv）だけがある大会も載せる
    team_keys = {(r.get('date', ''), methods.event_name(r.get('event_name_ja'))) for r in read_tsv(os.path.join(DATA, 'teams.tsv'))}
    ev = sorted((e for e in events.values() if bouts.get(e['event_id']) or PODIUM.get(e['event_id'])
                 or (e['date'], methods.event_name(e['name'])) in team_keys), key=lambda e: (e['date'], e['event_id']))
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
    # 選手番号のない名前にも選手ページを作る（同じ名前の試合を名前だけでまとめる。番号は n＋名前から作る）
    for e in ev:
        for b in bouts[e['event_id']]:
            for k in ('1', '2'):
                if not b.get(f'fighter{k}_id') and norm(b[f'fighter{k}']):
                    nid = 'n' + hashlib.md5(norm(b[f'fighter{k}']).encode()).hexdigest()[:9]
                    b[f'fighter{k}_id'] = nid
                    fighters.setdefault(nid, re.sub(r'[\s　]+', '', b[f'fighter{k}']) if re.search(r'[ぁ-んァ-ヶ一-龥]', b[f'fighter{k}']) else b[f'fighter{k}'].strip())
    # 同じ大会の同じ試合が2回入っているもの（同じ試合番号・同じ2人・同じ勝者）は1つにする。
    # 2つの資料から同じ大会を取り込んだときに起きる。情報の多い方を残す。柔術は同じ2人が階級別と無差別で2回戦うことがあるので対象外。
    # 選手番号の付け間違いの取り消し（data/id_fixes.tsv：その大会で、その名前の選手に付いている番号を外す。別人の選手ページにまとめられないようにする）
    for f in read_tsv(os.path.join(DATA, 'id_fixes.tsv')):
        for b in bouts.get(f['event_id'], []):
            for k in ('1', '2'):
                if b.get(f'fighter{k}_id') == f['wrong_id'] and re.sub(r'[\s　]', '', b.get(f'fighter{k}') or '') == re.sub(r'[\s　]', '', f['name']):
                    # 同じ名前の選手がいればその選手に、いなければ名前だけの選手ページにつなぐ
                    same = [fid for fid, fn in fighters.items() if fid.startswith('f') and fid != f['wrong_id'] and norm(fn) == norm(b[f'fighter{k}'])]
                    nid = same[0] if len(same) == 1 else 'n' + hashlib.md5(norm(b[f'fighter{k}']).encode()).hexdigest()[:9]
                    b[f'fighter{k}_id'] = nid
                    fighters.setdefault(nid, re.sub(r'[\s　]+', '', b[f'fighter{k}']))
    bjj_set = set(site.get('bjj_promotions') or []) | set(site.get('grappling_promotions') or [])
    ndup = 0
    for e in ev:
        if e.get('promotion') in bjj_set:
            continue
        keep, seen = [], {}
        def core(m):   # 決まり手の大まかな種類（判定・KO・TKO・一本・引き分けなど）
            m = re.sub(r'[\s　（）()]', '', m or '')
            for kw in ('引き分け', 'ドロー', 'ノーコンテスト', '無効', '判定', 'ポイント', 'TKO', 'KO', '一本', 'サブミッション', 'タップ', '反則', '失格', '棄権'):
                if kw in m:
                    return {'ドロー': '引き分け', '無効': 'ノーコンテスト', 'タップ': '一本', 'サブミッション': '一本', 'ポイント': '判定'}.get(kw, kw)
            return m[:4]
        for b in bouts[e['event_id']]:
            ids = (b.get('fighter1_id'), b.get('fighter2_id'))
            wid = ids[0] if b.get('winner') == '1' else ids[1] if b.get('winner') == '2' else b.get('winner') or ''
            no = str(b.get('match_no') or '')
            no = '' if no in ('', '0') else no
            k = (frozenset(ids), wid)
            hit = None
            if all(ids):
                for o in seen.get(k, []):
                    ob = keep[o]
                    ono = str(ob.get('match_no') or '')
                    ono = '' if ono in ('', '0') else ono
                    # 試合番号が同じか、どちらかに番号がない。決まり手の種類も食い違わない（片方が空でもよい）
                    same_detail = b.get('method') and b.get('method') == ob.get('method') and (b.get('time') or '') == (ob.get('time') or '') and (b.get('round') or '') == (ob.get('round') or '') and (b.get('time') or b.get('round'))
                    if same_detail or ((no == ono or not no or not ono) and (not b.get('method') or not ob.get('method') or core(b.get('method')) == core(ob.get('method')))):
                        hit = o
                        break
            if hit is not None:
                ob = keep[hit]
                # 試合番号のある方、次に情報の多い方を残す
                if (bool(no), sum(bool(v) for v in b.values())) > (bool(str(ob.get('match_no') or '') not in ('', '0')), sum(bool(v) for v in ob.values())):
                    keep[hit] = b
                ndup += 1
                continue
            seen.setdefault(k, []).append(len(keep))
            keep.append(b)
        bouts[e['event_id']] = keep
    print(f'重複していた試合を1つにまとめた: {ndup}')
    # 所属（data/gyms.tsv：event_id, match_no, name, gym, source）。試合ごとの所属なので、移籍の流れもたどれる
    GYM = {}
    for r in read_tsv(os.path.join(DATA, 'gyms.tsv')):
        g = (r.get('gym') or '').strip()
        if not g or not r.get('event_id') or not r.get('name'):
            continue
        k = re.sub(r'\s', '', r['name'])
        GYM[(r['event_id'], str(r.get('match_no') or '').strip(), k)] = g
        GYM.setdefault((r['event_id'], '', k), g)
    # 柔術の大会は、公式の表彰台に書かれた所属をその大会の試合にも使う（同じ大会・同じ名前のときだけ）
    for k, ps in PODIUM.items():
        for p in ps:
            if p[2] and p[3] and p[3].strip() not in ('-', '－', '無所属', 'なし'):
                GYM.setdefault((k, '', re.sub(r'\s', '', p[2])), p[3].strip())
    def gym_of(eid, no, name):
        k = re.sub(r'\s', '', name or '')
        return GYM.get((eid, str(no or '').strip(), k)) or GYM.get((eid, '', k)) or ''
    ngym = 0
    bout_out = {}
    used = set()
    for e in ev:
        rows = []
        for b in bouts[e['event_id']]:
            g1, g2 = gym_of(e['event_id'], b.get('match_no'), b['fighter1']), gym_of(e['event_id'], b.get('match_no'), b['fighter2'])
            ngym += bool(g1) + bool(g2)
            b['gym1'], b['gym2'] = g1, g2
            rows.append([int(b['match_no']) if str(b.get('match_no') or '').isdigit() else 0,
                         b.get('fighter1_id') or '', b['fighter1'], b.get('fighter2_id') or '', b['fighter2'],
                         WIN.get(b.get('winner') or '', ''), b.get('method') or '', b.get('round') or '',
                         b.get('time') or '', b.get('weight') or '', 1 if (b.get('note') or '') == 'uncertain' else 0, b.get('rule') or '', b.get('video') or '', b.get('title') or title_of(b.get('weight')), b.get('tnote') or '', b.get('mat') or '', g1, g2])
            used.update(x for x in (b.get('fighter1_id'), b.get('fighter2_id')) if x)
        bout_out[e['event_id']] = rows
    print(f'所属が入った選手（試合ごと）: {ngym}')
    fout = {i: [fighters.get(i, ''), '', 1] for i in used if fighters.get(i)}
    # 歴代王者（タイトルマッチ・王座決定戦の勝者を、団体と階級ごとに古い順にたどる）
    champs = collections.defaultdict(list)
    for e in sorted(ev, key=lambda x: x['date']):
        for b in bouts[e['event_id']]:
            lab = b.get('title') or title_of(b.get('weight'))
            if not lab or not re.search(r'タイトルマッチ|王座決定戦|王座統一|防衛戦', lab) or re.search(r'挑戦者|トーナメント', lab):
                continue
            w = WIN.get(b.get('winner') or '', '')
            if w not in (1, 2):
                continue
            interim = '暫定' in lab
            div = re.sub(r'[（(]?(初代|第\d+代|暫定|世界)?(王座決定戦|タイトルマッチ|王座統一戦|防衛戦)[）)]?$', '', lab).replace('暫定', '').strip() or lab
            champs[(e['promotion'], div)].append([e['date'], e['event_id'], b.get(f'fighter{w}_id') or '', b[f'fighter{w}'], b.get(f'fighter{3-w}_id') or '', b[f'fighter{3-w}'], 1 if interim else 0, lab])
    champ_out = []
    for (pr, div), rows in champs.items():
        line = []; cur = None
        for r in rows:
            if r[6]:   # 暫定王者はその行だけ記す
                line.append({'d': r[0], 'e': r[1], 'f': r[2], 'n': r[3], 'o': r[5], 'i': 1, 'def': 0}); continue
            if cur and norm(cur['n']) == norm(r[3]):
                cur['def'] += 1; continue
            cur = {'d': r[0], 'e': r[1], 'f': r[2], 'n': r[3], 'o': r[5], 'i': 0, 'def': 0}; line.append(cur)
        champ_out.append([pr, div, [[c['d'], c['e'], c['f'], c['n'], c['o'], c['i'], c['def']] for c in line]])
    champ_out.sort(key=lambda x: (x[0], x[1]))
    write_json('champs.json', champ_out)
    meta = {'built': site['built'], 'plabel': {p: pname(promos, p) for p in {e['promotion'] for e in ev}},
            'listed': [p for p, r in promos.items() if r.get('main')],
            'world': site.get('world_promotions') or [], 'grappling': site.get('grappling_promotions') or [], 'bjj': site.get('bjj_promotions') or [], 'standup': site.get('standup_promotions') or [], 'amateur': site.get('amateur_promotions') or [], 'first': site.get('first_promotions') or []}
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
    # 選手のほかの競技の試合（data/other_bouts.tsv：fighter_id, date, event, opponent, result(勝/敗/分/無効), method, round, time, rule, source_url）
    other = collections.defaultdict(list)
    for r in read_tsv(os.path.join(DATA, 'other_bouts.tsv')):
        other[MERGED.get(r['fighter_id'], r['fighter_id'])].append([r.get('date', ''), r.get('event', ''), r.get('opponent', ''), r.get('result', ''), r.get('method', ''), r.get('round', ''), r.get('time', ''), r.get('rule', ''), r.get('source_url', '')])
    meta['other'] = {k: sorted(v, reverse=True) for k, v in other.items() if k in fout}
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
    # Buffer の許可（OAuth）を出す1回きりのページ（人の手なしで鍵を新しくし続けるための最初の許可）
    if os.path.exists(os.path.join(TPL, 'buffer-oauth.html')):
        shutil.copy(os.path.join(TPL, 'buffer-oauth.html'), os.path.join(OUT, 'buffer-oauth.html'))
        os.makedirs(os.path.join(OUT, 'data'), exist_ok=True)
        shutil.copy(os.path.join(DATA, 'buffer_oauth.json'), os.path.join(OUT, 'data', 'buffer_oauth.json'))
    body = open(os.path.join(TPL, 'body.html'), encoding='utf-8').read()
    desc = f'1989年の修斗から最新の大会まで、日本の総合格闘技（MMA）{len(ev_list):,}興行・{n_b:,}試合の記録を出典つきで検索できるデータベース。'
    with open(os.path.join(OUT, 'index.html'), 'w', encoding='utf-8') as fp:
        fp.write(head(site, '日本MMA戦績録', desc, '') + body + '<script src="app.js"></script></body></html>')

    # 大会ごとの静的ページ（検索エンジン用・リンク共有用）
    e_by = collections.defaultdict(list)
    for e in ev:
        for b in bouts[e['event_id']]:
            for k in ('1', '2'):
                if b.get(f'fighter{k}_id') and not b[f'fighter{k}_id'].startswith('n'):   # 名前だけの選手は静的ページを作らない
                    e_by[b[f'fighter{k}_id']].append((e, b, int(k)))
    urls = ['']
    p_ev = collections.defaultdict(list)   # 団体ごとの大会（団体ページ用）
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
                g = b.get(f'gym{k}') or ''
                gh = f'<br><small class="gy" style="color:var(--fg3);font-size:12px">{html.escape(g)}</small>' if g else ''
                return (f'<a class="u nb" href="../f/{fid}.html">{n}</a>' if fid and fid in fout else f'<span class="nb">{n}</span>') + gh
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
        base_u = site['base_url'].rstrip('/') + '/'
        ld = [{'@context': 'https://schema.org', '@type': 'SportsEvent', 'name': e['name'], 'startDate': e['date'], 'url': base_u + f'e/{eid}.html',
               'sport': 'Mixed Martial Arts', 'eventStatus': 'https://schema.org/EventScheduled', 'organizer': {'@type': 'Organization', 'name': pn},
               'location': {'@type': 'Place', 'name': e.get('venue') or '不明', 'address': e.get('venue') or '不明'}},
              {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                  {'@type': 'ListItem', 'position': 1, 'name': 'トップ', 'item': base_u},
                  {'@type': 'ListItem', 'position': 2, 'name': pn, 'item': base_u + f'p/{e["promotion"]}.html'},
                  {'@type': 'ListItem', 'position': 3, 'name': e['name'], 'item': base_u + f'e/{eid}.html'}]}]
        p_ev[e['promotion']].append(e)
        page = (head(site, title, f'{pn} {e["name"]} {e["date"]} の全試合結果（{len(bouts[eid])}試合）', f'e/{eid}.html', '../', ld) + static_header('../') +
                f'<main class="wrap"><p class="crumb"><a class="lnk" href="../index.html">トップ</a>　›　<a class="lnk" href="../p/{e["promotion"]}.html">{html.escape(pn)}</a></p>'
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
    # 海外の記録サイトの通算戦績（data/records/records.tsv・bouts.tsv）。あればこちらを優先する（出典名は出さない）
    for r in read_tsv(os.path.join(DATA, 'records', 'records.tsv')):
        f = MERGED.get(r['fighter_id'], r['fighter_id'])
        wrec[f] = {'wiki_title': '', 'source_url': '', 'wins': r['wins'], 'losses': r['losses'], 'draws': r['draws'], 'no_contests': r['no_contests']}
        wb[f] = []
    for r in read_tsv(os.path.join(DATA, 'records', 'bouts.tsv')):
        f = MERGED.get(r['fighter_id'], r['fighter_id'])
        if wrec.get(f, {}).get('wiki_title') == '':
            wb[f].append({'date': r['date'], 'result': r['result'], 'opponent': r['opponent'], 'method': en_method(r['method']), 'event': r['event'],
                          'rt': (f"{r['round']}R {r['time']}" if r.get('round') else '')})
    wextra = {}
    for fid, r in wrec.items():
        if fid not in fout:
            continue
        have = set()
        for e, b, side in e_by.get(fid, []):
            o = b['fighter2'] if side == 1 else b['fighter1']
            have.add((e['date'], norm(o)))
        dates = {e['date'] for e, b, side in e_by.get(fid, [])}
        x = [[w['date'], w['result'], w['opponent'], w['method'] if w.get('rt') is not None else methods.tidy(w['method']), w['event'], w.get('rt', '')] for w in wb.get(fid, [])
             if (w['date'], norm(w['opponent'])) not in have and w['date'] not in dates]
        wextra[fid] = x
        with open(os.path.join(OUT, 'w', f'{fid}.json'), 'w', encoding='utf-8') as fp:
            json.dump({'t': r['wiki_title'], 'u': r['source_url'],
                       'rec': [int(r['wins']), int(r['losses']), int(r['draws']), int(r['no_contests'])], 'x': x}, fp, ensure_ascii=False, separators=(',', ':'))

    # 選手ごとの静的ページ
    for fid, _v in fout.items():
        if fid.startswith('n'):   # 名前だけでまとめた選手は静的ページを作らない（画面はサイト内で表示）
            continue
        name = _v[0]
        lst = sorted(e_by.get(fid, []), key=lambda x: x[0]['date'], reverse=True)
        w = l = d = nc = 0
        rows = []
        for e, b, side in lst:
            win = b.get('winner') or ''
            ok = 'o'
            ama = e.get('promotion') in (site.get('amateur_promotions') or [])
            c1 = 0 if (b.get('rule') or ama) else 1          # 柔術・グラップリング・エキシビション・アマチュアは戦績に数えない
            if win == str(side): w += c1; r = '勝'; ok = 'w'
            elif win in ('1', '2'): l += c1; r = '負'; ok = 'l'
            elif win == 'draw': d += c1; r = '分'
            elif win == 'nc': nc += c1; r = '無効'
            else: r = '—'
            rtag = f'<span class="unc">{html.escape(b["rule"] or "アマチュア")}・戦績に数えない</span>' if (b.get('rule') or ama) else ''
            ok2 = '2' if side == 1 else '1'
            oid = b.get(f'fighter{ok2}_id'); on = html.escape(b[f'fighter{ok2}'])
            opp = f'<a class="u nb" href="{oid}.html">{on}</a>' if oid and oid in fout else f'<span class="nb">{on}</span>'
            rows.append((e['date'], f'<tr><td><span class="rs {ok}">{r}</span></td><td>{opp}</td><td><a class="u" href="../e/{e["event_id"]}.html">{html.escape(e["name"])}</a></td>'
                        f'<td class="num">{html.escape(e["date"])}</td><td>{html.escape(b.get("method") or "")}{rtag}</td><td class="num">{html.escape(rt(b))}</td></tr>'))
        # 所属の変遷（試合ごとの所属を古い順にたどり、変わったところで区切る）
        ghist = []
        for e, b, side in sorted(lst, key=lambda x: x[0]['date']):
            g = b.get(f'gym{side}') or ''
            if not g:
                continue
            if ghist and ghist[-1][0] == g:
                ghist[-1][2] = e['date']
            else:
                ghist.append([g, e['date'], e['date']])
        # リングネームの変遷（試合ごとの表記。空白・中黒の違いと、日本語名の選手の英字表記は数えない）
        # 1試合だけの表記（誤記・表記ゆれのことが多い）は数えず、2試合以上で使われた名前だけでたどる
        nkey = lambda x: unicodedata.normalize('NFKC', re.sub(r'[\s・･=＝.．"“”\'’]', '', x or '')).lower()
        jp = re.search(r'[぀-ヿ一-鿿]', name or '')
        ncnt = collections.Counter(nkey(b.get(f'fighter{side}')) for e, b, side in lst)
        nhist = []
        for e, b, side in sorted(lst, key=lambda x: x[0]['date']):
            n0 = (b.get(f'fighter{side}') or '').strip()
            if not n0 or (jp and not re.search(r'[぀-ヿ一-鿿]', n0)) or ncnt[nkey(n0)] < 2:
                continue
            # 同じ名前は1行にまとめ、最初に使った日と最後に使った日を出す
            hit = next((x for x in nhist if nkey(x[0]) == nkey(n0)), None)
            if hit:
                hit[2] = e['date']
            else:
                nhist.append([n0, e['date'], e['date']])
        if len({nkey(x[0]) for x in nhist}) >= 2:
            gym_name = ('<h2 class="sec">リングネームの変遷</h2><div class="tbl"><table><thead><tr><th>名前（試合での表記）</th><th class="num">期間（試合の日付）</th></tr></thead><tbody>'
                        + ''.join(f'<tr><td>{html.escape(n)}</td><td class="num">{a[:7].replace("-", ".")}{"" if a[:7] == z[:7] else "〜" + z[:7].replace("-", ".")}</td></tr>' for n, a, z in reversed(nhist))
                        + '</tbody></table></div>')
        else:
            gym_name = ''
        gym_html = ''
        if ghist:
            gym_html = ('<h2 class="sec">所属</h2><div class="tbl"><table><thead><tr><th>所属</th><th class="num">期間（試合の日付）</th></tr></thead><tbody>'
                        + ''.join(f'<tr><td>{html.escape(g)}</td><td class="num">{a[:7].replace("-", ".")}{"" if a[:7] == z[:7] else "〜" + z[:7].replace("-", ".")}</td></tr>' for g, a, z in reversed(ghist))
                        + '</tbody></table></div>')
        gym_html = gym_name + gym_html + ('<h2 class="sec">全試合</h2>' if (gym_name or gym_html) else '')
        rec = f'{w}勝{l}敗{d}分' + (f'{nc}無効試合' if nc else '')
        note = '※日本で開かれた大会・日本の団体の大会と、世界の主要団体（UFC・ONE・PFL・Bellatorなど）での試合の戦績です。そのほかの海外の大会での試合は含みません'
        if fid in wrec:
            r0 = wrec[fid]
            rec = f'通算 {r0["wins"]}勝{r0["losses"]}敗{r0["draws"]}分' + (f'{r0["no_contests"]}無効試合' if r0['no_contests'] not in ('0', '') else '')
            note = (f'通算戦績はWikipedia「<a class="u" href="{html.escape(r0["source_url"])}">{html.escape(r0["wiki_title"])}</a>」の戦績表によります（海外の試合を含む）。印のついた試合はWikipediaからの記録です。'
                    if r0.get('wiki_title') else '通算戦績は海外の大会を含むプロの全試合です。印のついた試合は、このサイトに大会がない試合です。')
            RS = {'win': ('w', '勝'), 'loss': ('l', '負'), 'draw': ('o', '分'), 'nc': ('o', '無効')}
            for x in wextra.get(fid, []):
                c, t = RS.get(x[1], ('o', '—'))
                rows.append((x[0], f'<tr><td><span class="rs {c}">{t}</span></td><td><span class="nb">{html.escape(x[2])}</span></td><td>{html.escape(x[4])}<span class="unc">{'Wikipedia' if r0.get('wiki_title') else '海外の大会'}</span></td>'
                                   f'<td class="num">{html.escape(x[0])}</td><td>{html.escape(x[3])}</td><td class="num"></td></tr>'))
        base_u = site['base_url'].rstrip('/') + '/'
        ld = [{'@context': 'https://schema.org', '@type': 'ProfilePage', 'url': base_u + f'f/{fid}.html', 'name': f'{name}の戦績',
               'mainEntity': {'@type': 'Person', 'name': name, 'description': f'総合格闘技の選手。戦績 {rec}'}},
              {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                  {'@type': 'ListItem', 'position': 1, 'name': 'トップ', 'item': base_u},
                  {'@type': 'ListItem', 'position': 2, 'name': name, 'item': base_u + f'f/{fid}.html'}]}]
        page = (head(site, f'{name}の戦績｜日本MMA戦績録', f'{name}（総合格闘技）の戦績 {rec}。全{len(lst)}試合の結果と出典。', f'f/{fid}.html', '../', ld) + static_header('../') +
                f'<main class="wrap"><p class="crumb"><a class="lnk" href="../index.html">トップ</a>　›　<a class="lnk" href="../index.html#fighters">選手</a></p>'
                f'<div class="ph"><div><h1>{html.escape(name)}</h1><p class="sub">{rec}{"　所属：" + html.escape(ghist[-1][0]) if ghist else ""}</p><p class="sub" style="font-size:13px;color:var(--fg3)">{note}</p></div></div>'
                + gym_html +
                f'<div class="tbl"><table><thead><tr><th>結果</th><th>対戦相手</th><th>大会</th><th class="num">日付</th><th>決まり手</th><th class="num">R・時間</th></tr></thead><tbody>{"".join(h for d, h in sorted(rows, key=lambda t: t[0], reverse=True))}</tbody></table></div></main>'
                + foot(site, len(ev_list), n_b))
        with open(os.path.join(OUT, 'f', f'{fid}.html'), 'w', encoding='utf-8') as fp:
            fp.write(page)
        urls.append(f'f/{fid}.html')

    # 団体ごとの静的ページ（大会の一覧。年ごと・新しい順）
    os.makedirs(os.path.join(OUT, 'p'), exist_ok=True)
    plinks = []
    for pk, lst in sorted(p_ev.items(), key=lambda t: (-len(t[1]), t[0])):
        pn = pname(promos, pk)
        by_y = collections.defaultdict(list)
        for e in lst:
            by_y[e['date'][:4]].append(e)
        secs = []
        for y in sorted(by_y, reverse=True):
            items = ''.join(f'<tr><td class="num">{html.escape(e["date"])}</td><td><a class="u" href="../e/{e["event_id"]}.html">{html.escape(e["name"])}</a></td><td>{html.escape(e.get("venue") or "")}</td><td class="num">{len(bouts[e["event_id"]])}</td></tr>'
                            for e in sorted(by_y[y], key=lambda x: x['date'], reverse=True))
            secs.append(f'<h2>{y}年</h2><div class="tbl"><table><thead><tr><th class="num">日付</th><th>大会</th><th>会場</th><th class="num">試合数</th></tr></thead><tbody>{items}</tbody></table></div>')
        yrs = sorted(by_y)
        span = f'{yrs[0]}年〜{yrs[-1]}年' if yrs[0] != yrs[-1] else f'{yrs[0]}年'
        nb = sum(len(bouts[e['event_id']]) for e in lst)
        base_u = site['base_url'].rstrip('/') + '/'
        ld = [{'@context': 'https://schema.org', '@type': 'CollectionPage', 'name': f'{pn}の大会一覧', 'url': base_u + f'p/{pk}.html'},
              {'@context': 'https://schema.org', '@type': 'BreadcrumbList', 'itemListElement': [
                  {'@type': 'ListItem', 'position': 1, 'name': 'トップ', 'item': base_u},
                  {'@type': 'ListItem', 'position': 2, 'name': pn, 'item': base_u + f'p/{pk}.html'}]}]
        page = (head(site, f'{pn}の大会一覧・全試合結果｜日本MMA戦績録', f'{pn}の全{len(lst):,}大会・{nb:,}試合の結果（{span}）。大会ごとの全試合結果と出典。', f'p/{pk}.html', '../', ld) + static_header('../') +
                f'<main class="wrap"><p class="crumb"><a class="lnk" href="../index.html">トップ</a>　›　<a class="lnk" href="../index.html#promotions">団体</a></p>'
                f'<div class="ph"><div><h1>{html.escape(pn)}</h1><p class="sub">{len(lst):,}大会・{nb:,}試合（{span}）</p>'
                f'<p class="sub"><a class="lnk" href="../index.html#p-{pk.replace("_", "-")}">検索・絞り込みつきの一覧を開く</a></p></div></div>'
                + ''.join(secs) + '</main>' + foot(site, len(ev_list), n_b))
        with open(os.path.join(OUT, 'p', f'{pk}.html'), 'w', encoding='utf-8') as fp:
            fp.write(page)
        urls.append(f'p/{pk}.html')
        plinks.append(f'<a href="p/{pk}.html">{html.escape(pn)}</a>')
    # トップページの下に、団体ページへの普通のリンクを並べる（検索エンジンがたどれるように）
    ip = os.path.join(OUT, 'index.html')
    t = open(ip, encoding='utf-8').read()
    nav = '<nav class="wrap plinks" aria-label="団体の一覧" style="font-size:13px;line-height:2;padding-block:16px"><b>団体別の大会一覧：</b> ' + '　'.join(plinks) + '</nav>'
    t = t.replace('<footer class="ft">', nav + '<footer class="ft">', 1)
    open(ip, 'w', encoding='utf-8').write(t)

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
    # 「本日の大会・過去のこの日の大会」の RSS（無料でずっと続く配信。X・Bluesky・読者のアプリがここから拾える）
    try:
        import xpost
        xpost.get = lambda path: json.load(open(os.path.join(OUT, path), encoding='utf-8'))
        today = datetime.datetime.now(xpost.JST).date()
        items = []
        for i in range(7):
            d = today - datetime.timedelta(days=i)
            t = xpost.build_text(d, True, False)
            if not t:
                continue
            pub = datetime.datetime(d.year, d.month, d.day, 6, 0, tzinfo=xpost.JST).strftime('%a, %d %b %Y %H:%M:%S %z')
            items.append(f'<item><title>{d.month}月{d.day}日の大会（本日の大会・過去のこの日の大会）</title><link>{base}</link>'
                         f'<guid isPermaLink="false">onthisday-{d.isoformat()}</guid><pubDate>{pub}</pubDate><description>{html.escape(t)}</description></item>')
        with open(os.path.join(OUT, 'onthisday.xml'), 'w', encoding='utf-8') as fp:
            fp.write('<?xml version="1.0" encoding="UTF-8"?>\n<rss version="2.0"><channel><title>日本MMA戦績録 本日の大会・過去のこの日の大会</title>'
                     f'<link>{base}</link><description>毎日、その日に開かれる大会と、過去の同じ日に開かれた大会のお知らせ</description><language>ja</language>'
                     + ''.join(items) + '</channel></rss>\n')
        print(f'RSS（本日の大会・過去のこの日の大会）: {len(items)}日分')
    except Exception as ex:
        print('RSS を作れなかった:', ex)
    with open(os.path.join(OUT, 'robots.txt'), 'w', encoding='utf-8') as fp:
        fp.write(f'User-agent: *\nAllow: /\nSitemap: {base}sitemap.xml\n')
    if site.get('google_site_verification'):   # Google Search Console の所有権の確認ファイル（消さないこと）
        g = site['google_site_verification']
        with open(os.path.join(OUT, g + '.html'), 'w') as fp:
            fp.write(f'google-site-verification: {g}.html')
    if site.get('indexnow_key'):   # 検索エンジン（Bingなど）に新しいページを知らせる仕組み（IndexNow）の鍵ファイル
        with open(os.path.join(OUT, site['indexnow_key'] + '.txt'), 'w') as fp:
            fp.write(site['indexnow_key'])
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
