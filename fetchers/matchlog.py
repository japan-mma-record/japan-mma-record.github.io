"""BJJ MATCH LOG（matchlog.bjjhub.biz）の全大会の入賞者を取り込む。

サイトの持ち主（このサイトの管理者）の了解を得ているので、出典にはこのサイトの名前を出さず、
各大会ページにある「公式ページ」（JBJJF・IBJJF・ASJJF・SJJJF の結果ページ）を出典にする。

使い方: python3 fetchers/matchlog.py [最初の番号] [最後の番号]
  大会ページ（/tournament/番号）を1から順に読み、404 が 300 回続いたら終わる。
  → data/matchlog/tournaments.tsv（tid, federation, date, name, official_url, categories, podiums）
  → data/matchlog/podium.tsv（tid, division, place, athlete_id, name, team）
GitHub Actions（.github/workflows/matchlog.yml）で毎週動かす。
"""
import csv, html, os, re, sys, time, urllib.error, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, 'data', 'matchlog')
BASE = 'https://matchlog.bjjhub.biz'
UA = {'User-Agent': 'japan-mma-record archive (https://japan-mma-record.github.io/)'}


def get(url):
    for i in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.status, r.read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, ''
            time.sleep(5 * (i + 1))
        except Exception:
            time.sleep(5 * (i + 1))
    return 0, ''


T = lambda s: html.unescape(re.sub(r'<[^>]+>', '', s or '')).strip()


def parse(tid, t):
    h1 = re.search(r'<h1>(.*?)</h1>', t, re.S)
    if not h1:
        return None, []
    name = re.sub(r'^【公式結果】\s*', '', T(h1.group(1)))
    hero = t[h1.end(): t.find('section-card', h1.end())]
    tags = [T(x) for x in re.findall(r'<span class="meta-tag">(.*?)</span>', hero, re.S)]
    date = next((x for x in tags if re.match(r'\d{4}-\d{2}-\d{2}$', x)), '')
    fed = tags[0] if tags else ''
    off = re.search(r'<a href="([^"]+)"[^>]*class="meta-tag"[^>]*>\s*公式ページ', hero)
    rows = []
    for g in re.split(r'<div class="category-group">', t)[1:]:
        hd = re.search(r'<div class="category-header">(.*?)</div>', g, re.S)
        div = T(hd.group(1)) if hd else ''
        for a in re.split(r'<div class="athlete-row">', g)[1:]:
            pl = re.search(r'pl-badge p(\d)', a)
            m = re.search(r'<a href="/athlete/(\d+)">(.*?)</a>', a, re.S)
            dj = re.search(r'<div class="athlete-dojo">(.*?)</div>', a, re.S)
            if not m:
                nm = re.search(r'<div class="athlete-name">\s*(?:<span[^>]*>)?([^<]+)', a)
                if not nm:
                    continue
                aid, nmv = '', T(nm.group(1))
            else:
                aid, nmv = m.group(1), T(m.group(2))
            rows.append([str(tid), div, pl.group(1) if pl else '', aid, nmv, T(dj.group(1)) if dj else ''])
    ev = [str(tid), fed, date, name, html.unescape(off.group(1)) if off else '', str(len({r[1] for r in rows})), str(len(rows))]
    return ev, rows


def main():
    a = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    b = int(sys.argv[2]) if len(sys.argv) > 2 else 10 ** 6
    os.makedirs(OUT, exist_ok=True)
    evs, pods, miss, tid = [], [], 0, a
    while tid <= b and miss < 300:
        st, t = get(f'{BASE}/tournament/{tid}')
        if st == 200:
            ev, rows = parse(tid, t)
            if ev:
                evs.append(ev); pods.extend(rows); miss = 0
        elif st == 404:
            miss += 1
        else:
            print('読めなかった', tid)
        if tid % 100 == 0:
            print(tid, len(evs), len(pods), flush=True)
        tid += 1
        time.sleep(0.3)
    if len(evs) < 100 and a == 1:
        print('!!! 大会が少なすぎるので書き込まない', len(evs)); sys.exit(1)
    with open(os.path.join(OUT, 'tournaments.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['tid', 'federation', 'date', 'name', 'official_url', 'categories', 'podiums'])
        w.writerows(evs)
    with open(os.path.join(OUT, 'podium.tsv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f, delimiter='\t', lineterminator='\n')
        w.writerow(['tid', 'division', 'place', 'athlete_id', 'name', 'team'])
        w.writerows(pods)
    print('大会', len(evs), '入賞', len(pods))


if __name__ == '__main__':
    main()
