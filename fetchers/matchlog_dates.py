"""BJJ MATCH LOG で日付が空の大会（海外の IBJJF の大会など）の日付を、IBJJF の公式サイトから補う。

公式ページが「ChampionshipResults/番号」の大会は、IBJJF の大会カレンダー（開始日）を使い、
カレンダーにない古い大会は、IBJJF の結果ページ（ibjjf.com/events/番号/results）の「結果の確定日」を使う。
→ data/matchlog/dates.tsv（tid, date, source）
"""
import csv, json, os, re, time, urllib.request

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = os.path.join(HERE, 'data', 'matchlog')
H = {'User-Agent': 'Mozilla/5.0', 'Accept': 'application/json', 'X-Requested-With': 'XMLHttpRequest'}
MON = {m: i for i, m in enumerate(['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'], 1)}


def get(url, hdr=None):
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=hdr or {'User-Agent': 'Mozilla/5.0'}), timeout=60) as r:
                return r.read().decode('utf-8', 'replace')
        except Exception:
            time.sleep(5)
    return ''


def main():
    rows = list(csv.DictReader(open(os.path.join(D, 'tournaments.tsv'), encoding='utf-8'), delimiter='\t'))
    old = {}
    p = os.path.join(D, 'dates.tsv')
    if os.path.exists(p):
        old = {r['tid']: r for r in csv.DictReader(open(p, encoding='utf-8'), delimiter='\t')}
    cal = {}
    try:
        for e in json.loads(get('https://ibjjf.com/api/v1/events/calendar.json', H)).get('infosite_events') or []:
            try:
                cal[str(e['id'])] = f"{int(e['year']):04d}-{MON[e['month']]:02d}-{int(e['startDay']):02d}"
            except Exception:
                pass
    except Exception as ex:
        print('カレンダーが読めなかった', ex)
    out = dict(old)
    for r in rows:
        if r.get('date') or r['tid'] in out:
            continue
        m = re.search(r'ChampionshipResults/(\d+)', r.get('official_url') or '') or re.search(r'ibjjf\.com/events/(\d+)', r.get('official_url') or '')
        if not m:
            continue
        eid = m.group(1)
        if eid in cal:
            out[r['tid']] = {'tid': r['tid'], 'date': cal[eid], 'source': f'https://ibjjf.com/events/{eid}'}
            continue
        t = get(f'https://ibjjf.com/events/{eid}/results')
        d = re.search(r'([A-Z][a-z]{2})/(\d{1,2})/(\d{4})', t)
        if d and d.group(1) in MON:
            out[r['tid']] = {'tid': r['tid'], 'date': f'{int(d.group(3)):04d}-{MON[d.group(1)]:02d}-{int(d.group(2)):02d}', 'source': f'https://ibjjf.com/events/{eid}/results'}
        time.sleep(1)
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, ['tid', 'date', 'source'], delimiter='\t', lineterminator='\n')
        w.writeheader()
        for k in sorted(out, key=int):
            w.writerow(out[k])
    print('日付を補った大会', len(out))


if __name__ == '__main__':
    main()
