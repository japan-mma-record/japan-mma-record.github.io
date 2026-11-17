#!/usr/bin/env python3
"""Wikipedia（日本語版）の選手記事から、総合格闘技の通算戦績と全試合の一覧を取り込む。
GitHubの自動実行で月に1回動きます（Python標準機能だけで動きます）。

本人の記事かどうかの確かめ方（推測で結びつけないため）:
  記事の戦績表の中に、このデータベースにある同じ選手の試合と
  「同じ日付・同じ対戦相手」の試合が1つ以上あるときだけ、本人の記事とみなします。

出力:
  data/wiki/records.tsv  … 選手ごとの通算戦績（記事の戦績欄の数字）
  data/wiki/bouts.tsv    … 記事の戦績表の全試合（海外の試合も含む）
"""
import csv, json, os, re, time, urllib.request, urllib.parse, collections

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(ROOT, 'data')
OUT = os.path.join(DATA, 'wiki')
API = 'https://ja.wikipedia.org/w/api.php'
UA = 'JapanMMARecordBot/1.0 (https://japan-mma-record.github.io/; record archive)'


def read_tsv(p):
    if not os.path.exists(p):
        return []
    with open(p, encoding='utf-8', newline='') as fp:
        return list(csv.DictReader(fp, delimiter='\t'))


def norm(s):
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s or '')
    s = re.sub(r'\{\{仮リンク\|([^|}]*)\|[^}]*\}\}', r'\1', s)
    return re.sub(r'[\s・･　＝=\.．"“”]', '', s)


def plain(s):
    s = re.sub(r'<br\s*/?>', ' ', s or '')
    s = re.sub(r'<ref[^>]*>.*?</ref>|<ref[^>]*/>', '', s, flags=re.S)
    s = re.sub(r'\{\{仮リンク\|([^|}]*)\|[^}]*\}\}', r'\1', s)
    s = re.sub(r'\[\[(?:[^\]|]*\|)?([^\]]*)\]\]', r'\1', s)
    s = re.sub(r'\{\{[^{}]*\}\}', '', s)
    s = re.sub(r"'''?", '', s)
    return re.sub(r'\s+', ' ', s).strip()


def jdate(s):
    m = re.search(r'(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日', s or '')
    return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}' if m else ''


def api(titles):
    q = urllib.parse.urlencode({'action': 'query', 'prop': 'revisions', 'rvprop': 'content', 'rvslots': 'main',
                                'format': 'json', 'redirects': '1', 'titles': '|'.join(titles)})
    for i in range(4):
        try:
            req = urllib.request.Request(API + '?' + q, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except Exception as e:
            time.sleep(10 * (i + 1))
    return {}


def mma_section(text):
    """記事の「総合格闘技」の戦績部分だけを取り出す（キックボクシング等の表を除く）。"""
    m = re.search(r'^(=+)\s*(?:プロ)?総合格闘技(?:\s*戦績)?\s*\1\s*$', text, re.M)
    if not m:
        return text if 'MMA recordbox' in text else ''
    level = len(m.group(1))
    rest = text[m.end():]
    end = re.search(r'^={2,%d}\s*[^=\n].*?=+\s*$' % level, rest, re.M)
    return rest[:end.start()] if end else rest


def parse(text):
    sec = mma_section(text)
    if not sec:
        return None, []
    rec = {}
    rb = re.search(r'\{\{MMA recordbox(.*?)\n\}\}|\{\{MMA recordbox(.*?)\}\}', sec, re.S)
    if rb:
        for k, v in re.findall(r'\|\s*([a-zA-Z ]+?)\s*=\s*(\d+)', rb.group(1) or rb.group(2) or ''):
            rec[k.strip()] = v
    rows = []
    for line in sec.split('\n'):
        if not line.startswith('{{Fight-cont'):
            continue
        body = line[len('{{Fight-cont'):].rstrip()
        body = body[:-2] if body.endswith('}}') else body
        parts, depth, cur = [], 0, ''
        for ch in body:
            if ch in '{[':
                depth += 1
            elif ch in '}]':
                depth -= 1
            if ch == '|' and depth == 0:
                parts.append(cur); cur = ''
            else:
                cur += ch
        parts.append(cur)
        parts = [p.strip() for p in parts[1:]]
        if len(parts) < 5:
            continue
        res = {'○': 'win', '×': 'loss', '△': 'draw', '-': 'nc', '－': 'nc', '―': 'nc'}.get(parts[0].strip(), '')
        if not res:   # 試合前・中止などは数えない
            continue
        rows.append({'result': res, 'opponent': plain(parts[1]), 'method': plain(parts[2]),
                     'event': plain(parts[3]), 'date': jdate(parts[4]), 'opp_key': norm(parts[1])})
    return rec, rows


def main():
    os.makedirs(OUT, exist_ok=True)
    fighters = {r['fighter_id']: r['name'] for r in read_tsv(os.path.join(DATA, 'core', 'fighters.tsv'))}
    mine = collections.defaultdict(set)   # 選手 → {(日付, 対戦相手)}
    ev_date = {r['event_id']: r['date'] for r in read_tsv(os.path.join(DATA, 'core', 'events.tsv'))}
    for b in read_tsv(os.path.join(DATA, 'core', 'bouts.tsv')):
        d = ev_date.get(b['event_id'], '')
        if b['fighter1_id']:
            mine[b['fighter1_id']].add((d, norm(b['fighter2'])))
        if b['fighter2_id']:
            mine[b['fighter2_id']].add((d, norm(b['fighter1'])))
    # 名前 → 記事名の候補（そのまま、空白を取ったもの）
    cand = collections.defaultdict(set)
    for fid, name in fighters.items():
        if not name or not re.search(r'[ぁ-んァ-ン一-龥]', name):
            continue
        for t in {name.strip(), re.sub(r'\s+', '', name)}:
            cand[t].add(fid)
    titles = sorted(cand)
    pages = {}
    for i in range(0, len(titles), 50):
        d = api(titles[i:i + 50])
        q = d.get('query', {})
        back = {}
        for n in q.get('normalized', []) + q.get('redirects', []):
            back.setdefault(n['to'], set()).update(back.get(n['from'], {n['from']}))
        for p in q.get('pages', {}).values():
            if 'revisions' not in p:
                continue
            text = p['revisions'][0]['slots']['main'].get('*', '')
            if 'Fight-cont' not in text:
                continue
            asked = back.get(p['title'], {p['title']}) | {p['title']}
            pages[p['title']] = (text, asked)
        time.sleep(1)
    recs, bouts = [], []
    for title, (text, asked) in pages.items():
        rec, rows = parse(text)
        if not rows:
            continue
        keys = {(r['date'], r['opp_key']) for r in rows}
        for t in asked:
            for fid in cand.get(t, ()):
                if not (keys & mine.get(fid, set())):
                    continue   # 同じ日・同じ相手の試合が一つもなければ別人とみなす
                w = sum(r['result'] == 'win' for r in rows); l = sum(r['result'] == 'loss' for r in rows)
                dr = sum(r['result'] == 'draw' for r in rows); nc = sum(r['result'] == 'nc' for r in rows)
                recs.append([fid, title, w, l, dr, nc,
                             'https://ja.wikipedia.org/wiki/' + urllib.parse.quote(title.replace(' ', '_'))])
                for r in rows:
                    bouts.append([fid, r['date'], r['result'], r['opponent'], r['method'], r['event']])
    recs.sort(); bouts.sort()
    with open(os.path.join(OUT, 'records.tsv'), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['fighter_id', 'wiki_title', 'wins', 'losses', 'draws', 'no_contests', 'source_url']); w.writerows(recs)
    with open(os.path.join(OUT, 'bouts.tsv'), 'w', encoding='utf-8', newline='') as fp:
        w = csv.writer(fp, delimiter='\t', lineterminator='\n')
        w.writerow(['fighter_id', 'date', 'result', 'opponent', 'method', 'event']); w.writerows(bouts)
    print(f'Wikipediaの戦績を取り込みました: 選手 {len(recs)}人・試合 {len(bouts)}')


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'test':
        t = json.load(open(sys.argv[2], encoding='utf-8'))
        p = list(t['query']['pages'].values())[0]
        rec, rows = parse(p['revisions'][0]['slots']['main']['*'])
        print(rec, len(rows)); print(rows[:3])
    else:
        main()
