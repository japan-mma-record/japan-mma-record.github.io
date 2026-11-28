"""毎日の X（旧Twitter）投稿：「本日の大会」と「過去のこの日の大会」。

公開中のサイトのデータ（data/upcoming.json・events.json・bouts.json・meta.json）を読んで投稿文を作り、
X API（POST /2/tweets）で1件投稿する。

【無料】GitHub の Secrets に BUFFER_API_KEY（Buffer の無料プランの API キー。Buffer に X のアカウントをつないでおく）があれば、
Buffer 経由で X に投稿する（X の API 料金はかからない）。任意で BUFFER_CHANNEL_ID。
【有料・使わない】GitHub の Secrets に次の4つが入っているときだけ X API で直接投稿する（入っていなければ投稿文を表示するだけ）:
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


def build_text(day, long_post, with_url, limit=None, wfun=None):
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
    limit = limit or (25000 if long_post else 280)
    weight_ = wfun or weight

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
    if weight_(text) > limit:
        # 長すぎるときは、まずメインの行を外し、それでも長ければ過去の大会→本日の大会の順に減らす
        lines_today[:] = [x.split('\n')[0] for x in lines_today]
        lines_past[:] = [x.split('\n')[0] for x in lines_past]
        text = compose(nt, np_)
    while weight_(text) > limit and (np_ > 1 or nt > 1):
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


def post_bluesky(text):
    """Bluesky（無料・自動投稿できる）。BLUESKY_HANDLE と BLUESKY_APP_PASSWORD（アプリパスワード）を使う"""
    api = 'https://bsky.social/xrpc/'
    def call(m, body, tok=None):
        h = {'Content-Type': 'application/json'}
        if tok:
            h['Authorization'] = 'Bearer ' + tok
        req = urllib.request.Request(api + m, data=json.dumps(body).encode(), headers=h, method='POST')
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    ses = call('com.atproto.server.createSession', {'identifier': os.environ['BLUESKY_HANDLE'], 'password': os.environ['BLUESKY_APP_PASSWORD']})
    rec = {'$type': 'app.bsky.feed.post', 'text': text, 'langs': ['ja'],
           'createdAt': datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S.000Z')}
    # サイトのURLをリンクにする
    i = text.encode().find(SITE.encode())
    if i >= 0:
        rec['facets'] = [{'index': {'byteStart': i, 'byteEnd': i + len(SITE.encode())},
                          'features': [{'$type': 'app.bsky.richtext.facet#link', 'uri': SITE}]}]
    return call('com.atproto.repo.createRecord', {'repo': ses['did'], 'collection': 'app.bsky.feed.post', 'record': rec}, ses['accessJwt'])


def buffer_call(query, variables=None):
    req = urllib.request.Request('https://api.buffer.com', method='POST',
                                 data=json.dumps({'query': query, 'variables': variables or {}}).encode(),
                                 headers={'Authorization': 'Bearer ' + os.environ['BUFFER_API_KEY'], 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=60) as r:
        out = json.load(r)
    if out.get('errors'):
        raise RuntimeError(json.dumps(out['errors'], ensure_ascii=False)[:500])
    return out['data']


def buffer_x_channel():
    """Buffer につないだ X のチャンネルの番号。BUFFER_CHANNEL_ID があればそれを使い、なければ探す"""
    if os.environ.get('BUFFER_CHANNEL_ID'):
        return os.environ['BUFFER_CHANNEL_ID']
    orgs = buffer_call('query { account { organizations { id } } }')['account']['organizations']
    for o in orgs:
        chs = buffer_call('query($id: OrganizationId!) { channels(input: { organizationId: $id }) { id service } }', {'id': o['id']})['channels']
        for c in chs:
            if str(c.get('service', '')).lower() in ('twitter', 'x'):
                return c['id']
    raise RuntimeError('Buffer に X のチャンネルが見つからない')


def post_buffer(text):
    """Buffer（無料プランでも API が使える）経由で X に投稿する。X の API 料金はかからない"""
    due = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=2)).strftime('%Y-%m-%dT%H:%M:%S.000Z')
    q = ('mutation($text: String!, $ch: ChannelId!, $due: DateTime!) { createPost(input: { text: $text, channelId: $ch, '
         'schedulingType: automatic, mode: customScheduled, dueAt: $due }) { __typename } }')
    return buffer_call(q, {'text': text, 'ch': buffer_x_channel(), 'due': due})['createPost']


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
        print('X の鍵が設定されていないので、X には投稿していない')
    failed = False
    if os.environ.get('BUFFER_API_KEY'):
        bt = build_text(day, long_post, True)   # Buffer 経由なら URL を付けても無料
        try:
            print('Buffer 経由で X に投稿を入れました:', post_buffer(bt))
        except Exception as ex:
            print('Buffer 経由の X 投稿に失敗:', ex); failed = True
    else:
        print('Buffer の鍵がないので、Buffer 経由の X 投稿はしていない')
    if os.environ.get('BLUESKY_HANDLE') and os.environ.get('BLUESKY_APP_PASSWORD'):
        bt = build_text(day, False, True, limit=300, wfun=len)   # Bluesky は300文字まで。URLを付けても無料
        try:
            print('Bluesky に投稿しました:', post_bluesky(bt).get('uri'))
        except Exception as ex:
            print('Bluesky への投稿に失敗:', ex); failed = True
    else:
        print('Bluesky の設定がないので、Bluesky には投稿していない')
    if failed:
        sys.exit(1)


if __name__ == '__main__':
    main()
