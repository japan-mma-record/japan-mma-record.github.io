"""毎日の X（旧Twitter）投稿：「本日の大会」と「過去のこの日の大会」。

公開中のサイトのデータ（data/upcoming.json・events.json・bouts.json・meta.json）を読んで投稿文を作り、
X API（POST /2/tweets）で1件投稿する。

GitHub の Secrets に次の4つが入っているときだけ投稿する（入っていなければ投稿文を表示するだけ）:
  X_API_KEY, X_API_SECRET, X_ACCESS_TOKEN, X_ACCESS_TOKEN_SECRET
任意の設定（GitHub の Variables）:
  X_INCLUDE_URL = 1  … 最後にサイトのURLを付ける（URL付きの投稿は X API の料金が高い）
  X_LONG_POST   = 1  … 長い投稿ができるアカウント（X Premium）なら 1。0 のときは全角140字（半角280）に収める
使い方: python3 xpost.py [YYYY-MM-DD]   （日付を省くと日本時間の今日）
"""
import base64, datetime, hashlib, hmac, json, os, re, sys, time, urllib.parse, urllib.request, uuid

SITE = 'https://japan-mma-record.github.io/'
JST = datetime.timezone(datetime.timedelta(hours=9))
W = '日月火水木金土'


def get(path):
    with urllib.request.urlopen(SITE + path, timeout=60) as r:
        return json.load(r)


def weight(s):
    # X の文字数の数え方：半角（ラテン文字など）は1、全角は2。URLは23として数える
    n = 0
    for part in re.split(r'(https?://\S+)', s):
        if re.match(r'https?://', part):
            n += 23
            continue
        for ch in part:
            o = ord(ch)
            n += 1 if (o <= 0x10FF or 0x2000 <= o <= 0x200D or 0x2010 <= o <= 0x201F or 0x2032 <= o <= 0x2037) else 2
    return n


def short_venue(v):
    v = re.sub(r'[（(][^（）()]*[）)]\s*$', '', v or '').strip()
    return v


def build_text(day, long_post, with_url):
    up = get('data/upcoming.json')
    ev = get('data/events.json')
    bouts = get('data/bouts.json')
    meta = get('data/meta.json')
    skip = set(meta.get('bjj') or []) | set(meta.get('grappling') or [])
    world = set(meta.get('world') or [])
    label = meta.get('plabel') or {}
    ds = day.isoformat()
    md = ds[5:]

    head = f'{day.month}月{day.day}日（{W[(day.weekday() + 1) % 7]}）'
    lines_today = []
    for u in up:
        if u.get('d') != ds:
            continue
        s = f'・{u.get("n", "")}'
        v = short_venue(u.get('v'))
        if v:
            s += f'（{v}）'
        m = u.get('m') or {}
        if m.get('f1') and m.get('f2'):
            s += f'\n　メイン：{m["f1"]} vs {m["f2"]}'
        lines_today.append(s)

    past = [e for e in ev if re.fullmatch(r'\d{4}-\d{2}-\d{2}', e[1] or '') and e[1][5:] == md and int(e[1][:4]) < day.year and e[2] not in skip]
    # 日本の団体を先に、その中は新しい年から
    past.sort(key=lambda e: (e[2] in world, -int(e[1][:4]), -(e[6] or 0)))
    lines_past = []
    for e in past:
        y = int(e[1][:4])
        s = f'・{day.year - y}年前（{y}年）{e[3]}'
        bs = [b for b in bouts.get(e[0], []) if not b[11]] or bouts.get(e[0], [])
        if bs:
            b = sorted(bs, key=lambda b: b[0] or 0)[-1]
            if b[5] in (1, 2):
                w, l = (b[2], b[4]) if b[5] == 1 else (b[4], b[2])
                s += f'\n　メイン：{w} def. {l}'
        lines_past.append(s)

    tail = f'\n\n日本MMA戦績録 {SITE}' if with_url else '\n\n日本MMA戦績録'
    limit = 25000 if long_post else 280

    def compose(nt, np_):
        out = f'{head}'
        if lines_today:
            out += '\n\n【本日の大会】\n' + '\n'.join(lines_today[:nt])
            if nt < len(lines_today):
                out += f'\nほか{len(lines_today) - nt}大会'
        if lines_past:
            out += '\n\n【過去のこの日の大会】\n' + '\n'.join(lines_past[:np_])
            if np_ < len(lines_past):
                out += f'\nほか{len(lines_past) - np_}大会'
        return out + tail

    nt, np_ = len(lines_today), len(lines_past)
    text = compose(nt, np_)
    if weight(text) > limit:
        # 長すぎるときは、まずメインの行を外し、それでも長ければ過去の大会→本日の大会の順に減らす
        lines_today[:] = [x.split('\n')[0] for x in lines_today]
        lines_past[:] = [x.split('\n')[0] for x in lines_past]
        text = compose(nt, np_)
    while weight(text) > limit and (np_ > 1 or nt > 1):
        if np_ > 1:
            np_ -= 1
        else:
            nt -= 1
        text = compose(nt, np_)
    if not lines_today and not lines_past:
        return ''
    return text


def oauth_header(method, url, key, secret, token, token_secret):
    q = lambda s: urllib.parse.quote(str(s), safe='~')
    p = {'oauth_consumer_key': key, 'oauth_nonce': uuid.uuid4().hex, 'oauth_signature_method': 'HMAC-SHA1',
         'oauth_timestamp': str(int(time.time())), 'oauth_token': token, 'oauth_version': '1.0'}
    base = '&'.join([method, q(url), q('&'.join(f'{q(k)}={q(v)}' for k, v in sorted(p.items())))])
    sig = base64.b64encode(hmac.new(f'{q(secret)}&{q(token_secret)}'.encode(), base.encode(), hashlib.sha1).digest()).decode()
    p['oauth_signature'] = sig
    return 'OAuth ' + ', '.join(f'{q(k)}="{q(v)}"' for k, v in sorted(p.items()))


def post(text):
    url = 'https://api.x.com/2/tweets'
    h = oauth_header('POST', url, os.environ['X_API_KEY'], os.environ['X_API_SECRET'],
                     os.environ['X_ACCESS_TOKEN'], os.environ['X_ACCESS_TOKEN_SECRET'])
    req = urllib.request.Request(url, data=json.dumps({'text': text}).encode(), method='POST',
                                 headers={'Authorization': h, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def main():
    day = datetime.date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.datetime.now(JST).date()
    long_post = os.environ.get('X_LONG_POST', '0') == '1'
    with_url = os.environ.get('X_INCLUDE_URL', '0') == '1'
    text = build_text(day, long_post, with_url)
    if not text:
        print('この日の大会がないので投稿しない')
        return
    print(text)
    print(f'--- 文字数（Xの数え方）: {weight(text)}')
    if all(os.environ.get(k) for k in ('X_API_KEY', 'X_API_SECRET', 'X_ACCESS_TOKEN', 'X_ACCESS_TOKEN_SECRET')):
        r = post(text)
        print('投稿しました:', r.get('data', {}).get('id'))
    else:
        print('X の鍵が設定されていないので、投稿はしていない（投稿文の表示だけ）')


if __name__ == '__main__':
    main()
