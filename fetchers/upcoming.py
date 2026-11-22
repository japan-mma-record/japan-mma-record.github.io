"""今後の大会予定（data/upcoming.json）を、毎日自動で新しくする。

読むところ（どれか一つが失敗しても、ほかは続けます）:
  1. eFight のイベント日程（いろいろな団体の予定と対戦カードがまとまっている）
  2. 各団体の公式サイト（eFight に載っていない大会を補う）
     DEEP / 修斗 / パンクラス / GRACHAN / PFC / ROMAN / WARDOG
書き方:
  ・日本で開かれる、MMA の大会だけを載せる（キック・柔術・グラップリングだけの大会、アマチュア大会は載せない）
  ・終わった大会は自動で消える
  ・今回読めなかった大会（サイトの不調など）も、前回の内容を残しておく
"""
import datetime, json, os, re, urllib.parse
from common import fetch, text_lines, links, DATA

UP = os.path.join(DATA, 'upcoming.json')
JST = datetime.timezone(datetime.timedelta(hours=9))

# 団体名（表示名）と、大会名から見分けるための書き方
PROMOS = [
    ('DEEP JEWELS', r'JEWELS'),
    ('DEEP', r'(?<![☆A-Za-z])DEEP(?![☆])'),
    ('修斗', r'修斗|SHOOTO'),
    ('パンクラス', r'PANCRASE|パンクラス'),
    ('RIZIN', r'RIZIN'),
    ('GRACHAN', r'GRACHAN|グラチャン'),
    ('WARDOG', r'WARDOG'),
    ('KROSS×OVER', r'KROSS\s*[×xX]\s*OVER'),
    ('POUND 4 POUND FC', r'PFC\s*\.\s*\d|POUND\s*4\s*POUND'),
    ('ROOTS OF MARTIAL ARTS NETWORK', r'ROMAN\s*\d|ROMAN\s*[ⅠⅡⅢⅣⅤⅥⅦⅧⅨⅩ]'),
    ('ONE Championship', r'^ONE\s|ONE SAMURAI|ONE Friday|ONE FIGHT NIGHT'),
    ('BLOOM FC', r'BLOOM\s*FC'),
    ('GFG', r'\bGFG\b'),
    ('BRAVE FIGHT', r'BRAVE\s*FIGHT'),
    ('GRASP THE FUTURE CAGE', r'GRASP'),
    ('POUNDOUT', r'POUND\s*OUT'),
    ('格闘技のおもちゃ箱ACF（ATOYS CHALLENGE FIGHT）', r'\bACF\s*\d|ATOYS|A-Toys'),
]
NOT_MMA = r'キック|KICK|ボクシング|BOXING|ムエタイ|柔術|グラップリング|GRAPPLING|アマチュア|AMATEUR|チャレンジ|CHALLENGE|ジュニア|キッズ|空手|Lethwei'
PREF = ('北海道', '青森', '岩手', '宮城', '秋田', '山形', '福島', '茨城', '栃木', '群馬', '埼玉', '千葉', '東京', '神奈川', '新潟', '富山', '石川', '福井',
        '山梨', '長野', '岐阜', '静岡', '愛知', '三重', '滋賀', '京都', '大阪', '兵庫', '奈良', '和歌山', '鳥取', '島根', '岡山', '広島', '山口', '徳島',
        '香川', '愛媛', '高知', '福岡', '佐賀', '長崎', '熊本', '大分', '宮崎', '鹿児島', '沖縄', '札幌', '名古屋', '横浜', '神戸', '仙台')


def promo_of(name):
    if re.search(NOT_MMA, name, re.I) and not re.search(r'MMA|総合', name):
        return ''
    for p, rx in PROMOS:
        if re.search(rx, name, re.I):
            return p
    return ''


def in_japan(venue):
    return not venue or venue.startswith(PREF) or bool(re.search('|'.join(PREF), venue[:12]))


def jvenue(v):
    """「東京・ニューピアホール」→「ニューピアホール（東京）」"""
    v = re.sub(r'\s+', ' ', v or '').strip()
    m = re.match(r'^([^・]{2,4})・\s*(.+)$', v)
    return f'{m.group(2).strip()}（{m.group(1)}）' if m and m.group(1).rstrip('都府県') in [p.rstrip('都府県') for p in PREF] else v


def clean_fighter(s):
    s = re.sub(r'^[・･\s]+', '', s.strip())   # 先頭の「・」（箇条書きの印）を取る
    s = re.sub(r'^[\d０-９]+\s*[.．]\s*', '', s)
    s = re.sub(r'^(王者|挑戦者|暫定王者)\s*[：:]', '', s)
    s = re.sub(r'[：:]\s*(王者|挑戦者|暫定王者)$', '', s)
    s = re.split(r'\s*[（(]', s, maxsplit=1)[0]
    return s.strip(' 　※')


def is_label(s):
    return bool(re.search(r'級|kg|ＫＧ|KG|ラウンド|\dR|分\s*\d|タイトル|チャンピオン|トーナメント|決定戦|試合|ワンマッチ|契約|ルール', s)) and len(s) <= 80


def cards_from_lines(L):
    """対戦カードを読み取る。3つの書き方に対応：
       ▼(または◎・■)階級 / 選手A / vs / 選手B、 ◎階級 / 選手A / 選手B、 階級 / 選手A VS 選手B（1行）"""
    out, i, n = [], 0, len(L)
    while i < n:
        s = L[i]
        m = re.match(r'^[▼◎■◆●]\s*(.+)$', s)
        if m and is_label(m.group(1)):
            label = m.group(1).strip()
            a = L[i + 1] if i + 1 < n else ''
            if re.search(r'\s(VS|vs|Vs|ｖｓ|VS\.)\s', a):
                x, y = re.split(r'\s(?:VS|vs|Vs|ｖｓ|VS\.)\s', a, maxsplit=1)
                out.append([clean_fighter(x), clean_fighter(y), label]); i += 2; continue
            if i + 3 < n and re.fullmatch(r'(?i)vs\.?|ｖｓ|×', L[i + 2]):
                out.append([clean_fighter(a), clean_fighter(L[i + 3]), label]); i += 4; continue
            if i + 2 < n and not re.match(r'^[▼◎■◆●［\[◇【]', L[i + 2]) and not re.match(r'^[▼◎■◆●［\[◇【]', a):
                out.append([clean_fighter(a), clean_fighter(L[i + 2]), label]); i += 3; continue
        m = re.match(r'^(.+?)\s*(?:VS|ＶＳ)\s*(.+)$', s)
        if m and i > 0 and is_label(L[i - 1]) and not re.search(r'[。、!！]', s) and len(s) < 90:
            out.append([clean_fighter(m.group(1)), clean_fighter(m.group(2)), L[i - 1].strip()]); i += 1; continue
        i += 1
    seen, res = set(), []
    for c in out:
        # 「ライト級暫定王者決定戦 5分3R」のような見出しが選手名の位置に入ったものは、読み違いなので載せない
        if c[0] and c[1] and len(c[0]) <= 30 and len(c[1]) <= 30 and not is_label(c[0]) and not is_label(c[1]) and (c[0], c[1]) not in seen:
            seen.add((c[0], c[1])); res.append(c)
    return res


def mma_card(c):
    lab = c[2] or ''
    if re.search(r'キッズ|ジュニア|少年|U-?1\d', lab):
        return False
    return not re.search(r'キック|ムエタイ|ボクシング|アマチュア|グラップリング|柔術|エキシビション|エキシビジョン', lab) or bool(re.search(r'MMA|総合', lab))


def ev(d, n, v, p, src, cards):
    cards = [c for c in cards if mma_card(c)]
    e = {'d': d, 'n': n, 'v': v, 'p': p, 'c': cards, 'src': [src] if src else []}
    if cards:
        e['m'] = {'f1': cards[0][0], 'f2': cards[0][1], 'l': cards[0][2]}
    return e


# ---------- eFight ----------
def efight_month_url(y, m, now):
    return 'https://efight.jp/schedule' if (y, m) == (now.year, now.month) else f'https://efight.jp/schedule?{y}&{m:02d}'


def parse_efight_month(page):
    """月の一覧から [日付, 大会名, 会場, 詳しいページ] を取り出す。"""
    out = []
    for blk in re.split(r'<div class="section entry"', page)[1:]:
        md = re.search(r'<h3>(\d{4})年(\d{1,2})月(\d{1,2})日', blk) or re.search(r'jump_schedule-(\d{4})(\d{2})(\d{2})_', blk)
        nm = re.search(r'<h4[^>]*>(.*?)</h4>', blk, re.S)
        if not md or not nm:
            continue
        name = re.sub(r'<[^>]+>', '', nm.group(1)).strip()
        name = (re.search(r'『(.+?)』', name) or re.search(r'(.+)', name)).group(1).strip()
        sub = re.search(r'class="subtitle_head">(.*?)</span>', blk, re.S)
        vv = re.sub(r'<[^>]+>', '', sub.group(1)).strip() if sub else ''
        vv = re.sub(r'^\s*\d{1,2}:\d{2}\s*〜\s*', '', vv).replace('　', ' ').strip()
        u = re.search(r'href="(https://efight\.jp/jump_schedule-[^"]+)"', blk)
        out.append([f'{md.group(1)}-{int(md.group(2)):02d}-{int(md.group(3)):02d}', name, vv, u.group(1) if u else ''])
    return out


def parse_efight_event(page):
    L = [l for l in text_lines(page) if l]
    venue = ''
    for l in L:
        m = re.match(r'^会場\s*[：:]\s*(.+)$', l)
        if m:
            venue = m.group(1).strip(); break
    i = L.index('対戦カード') if '対戦カード' in L else 0
    j = next((k for k in range(i, len(L)) if L[k] in ('地図', '関連記事')), len(L))
    return venue, cards_from_lines(L[i:j])


def from_efight(now):
    res = []
    y, m = now.year, now.month
    for _ in range(6):
        try:
            rows = parse_efight_month(fetch(efight_month_url(y, m, now)))
        except Exception as e:
            print(f'[予定] eFight {y}-{m:02d} 読めず: {e}'); rows = []
        for d, name, vv, u in rows:
            p = promo_of(name)
            if not p or not in_japan(vv) or d < now.strftime('%Y-%m-%d'):
                continue
            venue, cards = vv, []
            if u:
                try:
                    v2, cards = parse_efight_event(fetch(u))
                    venue = v2 or vv
                except Exception as e:
                    print(f'[予定] eFight 大会ページ読めず {u}: {e}')
            res.append(ev(d, name, jvenue(venue) if '・' in venue[:6] else venue, p, u, cards))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return res


# ---------- 公式サイト ----------
def date_of(s, year=None):
    m = re.search(r'(\d{4})\s*[年/.\-]\s*(\d{1,2})\s*[月/.\-]\s*(\d{1,2})', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'
    m = re.search(r'(\d{1,2})月(\d{1,2})日', s)
    if m and year:
        return f'{year}-{int(m.group(1)):02d}-{int(m.group(2)):02d}'
    return ''


def from_deep(now):
    top = 'https://www.deep2001.com/'
    page = fetch(top)
    blk = page[page.find('newsRisultText'):] if 'newsRisultText' in page else page
    blk = blk[:blk.find('</ul>')] if '</ul>' in blk else blk
    urls = []
    for u in re.findall(r'href="(https://www\.deep2001\.com/[^"?#]+/)"', blk):
        if u not in urls:
            urls.append(u)
    res = []
    for u in urls[:12]:
        L = [l for l in text_lines(fetch(u)) if l]
        name = d = venue = ''
        for l in L:
            if not name and (m := re.match(r'^●\s*開催名\s*[：:]\s*(.+)$', l)): name = m.group(1).strip()
            if not d and re.match(r'^●\s*日時', l): d = date_of(l)
            if not venue and (m := re.match(r'^●\s*会場\s*[：:]\s*(.+)$', l)): venue = m.group(1).strip()
        if not name or not d:
            continue
        i = next((k for k, l in enumerate(L) if '【対戦カード】' in l), 0)
        j = next((k for k in range(i + 1, len(L)) if L[k].startswith('【')), len(L))
        cards = [c for c in cards_from_lines(L[i:j]) if not re.search(r'アマチュア', c[2])] if i else []
        res.append(ev(d, name, venue, 'DEEP JEWELS' if re.search('JEWELS', name) else 'DEEP', u, cards))
    return res


def from_shooto(now):
    base = 'https://www.shooto-mma.com/schedule/'
    page = fetch(base)
    res = []
    ids = []
    for u in links(page, base):
        if re.search(r'/schedule/\?id=\d+$', u) and u not in ids:
            ids.append(u)
    for u in ids[:10]:
        L = [l for l in text_lines(fetch(u)) if l]
        name = venue = d = ''
        for k, l in enumerate(L):
            if l.startswith('［大会名］'): name = l[5:].strip() + (' ' + L[k + 1] if k + 1 < len(L) and not L[k + 1].startswith('［') else '')
            if l.startswith('［日時］'): d = date_of(l)
            if l.startswith('［会場］'): venue = l[4:].strip()
        if not d:
            d = date_of(' '.join(L[:30]))
        if not name or not d:
            continue
        res.append(ev(d, name.strip(), venue, '修斗', u, cards_from_lines(L)))
    return res


def from_pancrase(now):
    res = []
    for y in (now.year, now.year + 1):
        u = f'https://www.pancrase.co.jp/rls/{y}/schedule.html'
        try:
            L = [l for l in text_lines(fetch(u)) if l]
        except Exception:
            continue
        for k in range(len(L) - 1):
            if re.match(r'^PANCRASE', L[k]) and re.match(r'^\d{1,2}月\d{1,2}日', L[k + 1]):
                d = date_of(L[k + 1], y)
                venue = re.sub(r'^\d{1,2}月\d{1,2}日\s*[（(][^）)]*[）)]\s*', '', L[k + 1]).strip()
                res.append(ev(d, L[k].strip(), venue, 'パンクラス', u, []))
    return res


def from_grachan(now):
    base = 'https://grachan.jp/schedule/'
    page = fetch(base)
    res = []
    for u in dict.fromkeys(x for x in links(page, base) if re.search(r'grachan\.jp/schedule/grachan[0-9a-z-]+/?$', x)):
        L = [l for l in text_lines(fetch(u)) if l]
        g = lambda key: next((L[k + 1] for k in range(len(L) - 1) if L[k] == key), '')
        name, d, venue = g('大会名'), date_of(g('開催日')), g('会場')
        if not name or not d or d < now.strftime('%Y-%m-%d') or re.search(r'チャレンジ|challenge', name, re.I):
            continue
        i = L.index('対戦カード') if '対戦カード' in L else len(L)
        res.append(ev(d, name, venue, 'GRACHAN', u, cards_from_lines(L[i:])))
    return res


def next_event(url, promo, rx_name):
    L = [l for l in text_lines(fetch(url)) if l]
    res = []
    for k, l in enumerate(L):
        if re.search(rx_name, l):
            for j in range(k, min(k + 6, len(L))):
                d = date_of(L[j])
                if d:
                    venue = re.split(r'[｜|]', L[j])[-1].strip() if re.search(r'[｜|]', L[j]) else re.sub(r'^.*?\d{1,2}日\s*(?:[（(][^）)]*[）)])?\s*', '', L[j]).strip()
                    res.append(ev(d, re.split(r'\s*/\s*', l)[0].strip(), venue, promo, url, []))
                    break
    return res


def from_pfc(now):
    return next_event('https://p4pfc.com/schedule-match', 'POUND 4 POUND FC', r'^PFC\.\d+')


def from_roman(now):
    return next_event('https://ro-man.site/event/', 'ROOTS OF MARTIAL ARTS NETWORK', r'^ROMAN\s*\d+$')


def from_wardog(now):
    return next_event('https://wardog-cf.jp/', 'WARDOG', r'^WARDOG\.\d+$')


SOURCES = [('eFight', from_efight), ('DEEP', from_deep), ('修斗', from_shooto), ('パンクラス', from_pancrase),
           ('GRACHAN', from_grachan), ('PFC', from_pfc), ('ROMAN', from_roman), ('WARDOG', from_wardog)]


def key(e):
    """同じ大会かどうか：日付と団体が同じで、大会名の番号（例 134、6th）が同じ（番号がなければ同じ日・同じ団体）。"""
    nums = re.findall(r'\d+', re.sub(r'20\d\d', '', e.get('n') or ''))
    return (e.get('d'), e.get('p'), nums[-1].lstrip('0') if nums else '')


def merge(old, new_lists):
    out = {}
    for e in old:
        out[key(e)] = e
    for src_name, lst in new_lists:
        for e in lst:
            k = key(e)
            if k in out:
                o = out[k]
                if len(e.get('c') or []) >= len(o.get('c') or []):
                    o['c'] = e['c']; o.pop('m', None)
                    if e.get('m'): o['m'] = e['m']
                if not o.get('v') and e.get('v'): o['v'] = e['v']
                if len(e.get('n') or '') > len(o.get('n') or '') and src_name != 'eFight': o['n'] = e['n']
                o['src'] = list(dict.fromkeys((o.get('src') or []) + (e.get('src') or [])))
            else:
                # 番号が片方にしかない同じ日・同じ団体の大会は同じ大会とみなす
                same = [kk for kk in out if kk[0] == k[0] and kk[1] == k[1] and (not kk[2] or not k[2])]
                if same:
                    o = out[same[0]]
                    if len(e.get('c') or []) > len(o.get('c') or []):
                        o['c'] = e['c']; o['m'] = e.get('m')
                    o['src'] = list(dict.fromkeys((o.get('src') or []) + (e.get('src') or [])))
                else:
                    out[k] = e
    return list(out.values())


def run(dry=False):
    now = datetime.datetime.now(JST)
    today = now.strftime('%Y-%m-%d')
    old = []
    if os.path.exists(UP):
        old = json.load(open(UP, encoding='utf-8'))
    got = []
    for name, f in SOURCES:
        try:
            lst = [e for e in f(now) if e.get('d') and e['d'] >= today]
            print(f'[予定] {name}: {len(lst)}大会')
            got.append((name, lst))
        except Exception as e:
            print(f'[予定] {name} の読み取りに失敗（前回の内容を残します）: {e}')
    if not got:
        return 0
    merged = [e for e in merge(old, got) if (e.get('d') or '') >= today]
    for e in merged:
        e['c'] = [c for c in (e.get('c') or []) if len(c) < 3 or mma_card(c)]
        if e.get('m') and e['c'] and not any(c[0] == e['m'].get('f1') for c in e['c']):
            e['m'] = {'f1': e['c'][0][0], 'f2': e['c'][0][1], 'l': e['c'][0][2]}
        if not e.get('m'):
            e.pop('m', None)
    merged.sort(key=lambda e: (e['d'], e.get('p') or '', e.get('n') or ''))
    if not dry:
        with open(UP, 'w', encoding='utf-8') as fp:
            json.dump(merged, fp, ensure_ascii=False, indent=1)
    print(f'[予定] 今後の大会: {len(merged)}')
    return 0
