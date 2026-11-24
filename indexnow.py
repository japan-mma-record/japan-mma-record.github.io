#!/usr/bin/env python3
"""検索エンジン（Bing・Yandex など IndexNow に参加しているところ）に、サイトのページ一覧を知らせる。
毎月1日と15日、または更新の説明に [indexnow] と書いたときに、毎日の更新の中で自動で動く。
Googleはこの仕組みに参加していないので、Googleには Search Console からサイトマップを登録する。
"""
import glob, json, os, re, sys, urllib.request

ROOT = os.path.dirname(os.path.abspath(__file__))
site = json.load(open(os.path.join(ROOT, 'data', 'site.json'), encoding='utf-8'))
key = site.get('indexnow_key')
base = site['base_url'].rstrip('/') + '/'
if not key:
    sys.exit('indexnow_key がないので何もしない')
urls = []
for f in sorted(glob.glob(os.path.join(ROOT, '_site', 'sitemap-*.xml'))):
    urls += re.findall(r'<loc>([^<]+)</loc>', open(f, encoding='utf-8').read())
host = re.sub(r'^https?://([^/]+).*$', r'\1', base)
for i in range(0, len(urls), 10000):
    part = urls[i:i + 10000]
    body = json.dumps({'host': host, 'key': key, 'keyLocation': f'{base}{key}.txt', 'urlList': part}).encode()
    req = urllib.request.Request('https://api.indexnow.org/indexnow', data=body, headers={'Content-Type': 'application/json; charset=utf-8'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            print(f'IndexNow: {len(part)}ページを送信 → {r.status}')
    except Exception as e:
        print(f'IndexNow: 送信に失敗（次の回にまた送る）: {e}')
