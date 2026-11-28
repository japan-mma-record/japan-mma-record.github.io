"""WordPress の記事一覧の JSON（/wp-json/wp/v2/posts?...&_fields=date,link,content）から「選手名（所属）」を読み取り、
data/gyms.tsv に足す行を作る（BOUTREVIEW のレポート https://www.boutreview.com/3/wp-json/wp/v2/posts?categories=… など）。

使い方: python3 build.py のあと、python3 fetchers/gym_wpjson.py DIR [DIR...] >> data/gyms.tsv
  DIR は probe-web ブランチの probe/ と同じ形（index.txt と out/N.html）のフォルダ。中身が JSON の配列のものだけ読む。
決まり:
  ・記事ごとに、記事の日付の3日前から当日までの大会（柔術の団体は除く）の試合と照らし合わせる。
  ・読み取りの決まりは fetchers/gym_paren.py と同じ（2人ともの「名前（所属）」がある試合だけ）。
  ・出典は記事の URL（link）。
"""
import json, os, sys, datetime, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gym_paren as gp  # noqa: E402


def main(dirs):
    tmp = tempfile.mkdtemp()
    os.makedirs(os.path.join(tmp, 'out'))
    idx = []
    k = 0
    for d in dirs:
        for line in open(os.path.join(d, 'index.txt'), encoding='utf-8'):
            p = line.split()
            if len(p) < 4 or p[1] != '200':
                continue
            path = os.path.join(d, 'out', f'{p[0]}.html')
            try:
                posts = json.load(open(path, encoding='utf-8'))
            except Exception:
                continue
            if not isinstance(posts, list):
                continue
            for po in posts:
                try:
                    link = po['link']
                    day = datetime.date.fromisoformat(po['date'][:10])
                    body = po['content']['rendered']
                except Exception:
                    continue
                k += 1
                open(os.path.join(tmp, 'out', f'{k}.html'), 'w', encoding='utf-8').write(
                    '<meta charset="utf-8">' + body)
                idx.append(f'{k} 200 0 {link}')
                for back in range(0, 4):
                    for eid in gp.date2ev.get((day - datetime.timedelta(back)).isoformat(), []):
                        if eid not in gp.url2ev[link]:
                            gp.url2ev[link].append(eid)
                            gp.DIST[(link, eid)] = back
    open(os.path.join(tmp, 'index.txt'), 'w', encoding='utf-8').write('\n'.join(idx) + '\n')
    # events_for が url2ev を使い、DIST が上書きされないように NEAR は使わない
    orig = gp.events_for

    def ev_for(url):
        return list(gp.url2ev.get(url, []))
    gp.events_for = ev_for
    gp.run([tmp])
    gp.events_for = orig


if __name__ == '__main__':
    main(sys.argv[1:])
