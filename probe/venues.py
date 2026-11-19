import json,re,time,urllib.request
ids=json.load(open('probe/sid.json'))
out=open('probe/venues3.tsv','w')
for k,s in ids.items():
    try:
        req=urllib.request.Request(f'https://www.sherdog.com/events/a-{s}',headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/124.0'})
        t=urllib.request.urlopen(req,timeout=40).read().decode('utf-8','replace')
        loc=re.search(r'itemprop="location">([^<]+)<',t); nm=re.search(r'<h1[^>]*>\s*<span[^>]*>([^<]+)<',t)
        out.write(f"{k}\t{s}\t{loc.group(1).strip() if loc else ''}\t{nm.group(1).strip() if nm else ''}\n")
    except Exception as e:
        out.write(f"{k}\t{s}\tERR {e}\t\n")
    time.sleep(1.5)
