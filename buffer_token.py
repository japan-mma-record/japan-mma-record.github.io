"""Buffer の鍵を、人の手なしで新しくし続ける仕組み。

Buffer の「個人の鍵」は最長1年で切れる。そこで Buffer の OAuth（アプリとしての許可）を使い、
1時間で切れる「使う鍵（アクセストークン）」を、長く使える「更新の鍵（リフレッシュトークン）」から毎回作り直す。
更新の鍵は使うたびに新しいものに替わる（古いものは使えなくなる）ので、毎回すぐに保存し直す。

保存のしかた（どれも期限がない）:
- 更新の鍵は、公開鍵で暗号化して、このリポジトリの data/buffer_token.enc に置く（暗号化してあるので公開されても読めない）。
- それを開ける秘密鍵は GitHub の Secrets の BUFFER_PRIVATE_KEY に置く（GitHub の Secrets には期限がない）。
- 毎日の投稿のたびに、更新の鍵を新しくして、暗号化して、リポジトリに保存し直す（GitHub Actions の GITHUB_TOKEN で push する）。

最初の1回だけ：サイトの buffer-oauth.html で「Buffer に許可」を押すと、許可のしるし（コード）を公開鍵で暗号化した文字列が出る。
それを data/buffer_grant.enc に置けば、次の実行でここが更新の鍵に交換する。
"""
import base64, json, os, subprocess, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
CONF = os.path.join(HERE, 'data', 'buffer_oauth.json')
TOKEN = os.path.join(HERE, 'data', 'buffer_token.enc')
GRANT = os.path.join(HERE, 'data', 'buffer_grant.enc')
TOKEN_URL = 'https://auth.buffer.com/token'


def _conf():
    return json.load(open(CONF, encoding='utf-8'))


def encrypt(obj):
    """公開鍵で暗号化（RSA-OAEP(SHA-256) で AES-256-GCM の鍵を包む）。ブラウザ側（buffer-oauth.html）と同じ形"""
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pub = serialization.load_pem_public_key(_conf()['public_key_pem'].encode())
    k, iv = os.urandom(32), os.urandom(12)
    ct = AESGCM(k).encrypt(iv, json.dumps(obj).encode(), None)
    ek = pub.encrypt(k, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    b = lambda x: base64.b64encode(x).decode()
    return json.dumps({'v': 1, 'k': b(ek), 'iv': b(iv), 'ct': b(ct)})


def decrypt(text):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    pem = os.environ['BUFFER_PRIVATE_KEY'].strip().replace('\\n', '\n')
    priv = serialization.load_pem_private_key(pem.encode(), password=None)
    d = json.loads(text)
    u = lambda x: base64.b64decode(x)
    k = priv.decrypt(u(d['k']), padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None))
    return json.loads(AESGCM(k).decrypt(u(d['iv']), u(d['ct']), None))


def _post(params):
    req = urllib.request.Request(TOKEN_URL, data=urllib.parse.urlencode(params).encode(), method='POST',
                                 headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', 'replace')[:300]
        raise RuntimeError(f'HTTP {e.code}: {body}')


def _save_and_push(path, content, msg):
    """更新の鍵を保存して、すぐに GitHub に送る（ここで失敗すると次から使えなくなるので、何度もやり直す）"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content + '\n')
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        return True
    g = lambda *a: subprocess.run(['git', '-C', HERE, *a], capture_output=True, text=True)
    g('config', 'user.name', 'github-actions[bot]')
    g('config', 'user.email', '41898282+github-actions[bot]@users.noreply.github.com')
    g('add', '-A', 'data/buffer_token.enc', 'data/buffer_grant.enc')
    g('commit', '-m', msg)
    for i in range(8):
        g('pull', '--rebase', '-X', 'theirs', 'origin', 'main')
        if g('push', 'origin', 'HEAD:main').returncode == 0:
            return True
        time.sleep(5 + i * 5)
    print('!!! 更新の鍵を GitHub に保存できなかった。次の実行で使えなくなるおそれがある')
    return False


def access_token():
    """Buffer の使う鍵を返す。OAuth が使えなければ None（呼ぶ側は個人の鍵 BUFFER_API_KEY に切り替える）"""
    if not os.environ.get('BUFFER_PRIVATE_KEY') or not os.path.exists(CONF):
        return None
    cid = _conf()['client_id']
    try:
        if os.path.exists(TOKEN) and open(TOKEN).read().strip():
            rt = decrypt(open(TOKEN).read())['refresh_token']
            r = _post({'grant_type': 'refresh_token', 'refresh_token': rt, 'client_id': cid})
        elif os.path.exists(GRANT) and open(GRANT).read().strip():
            g = decrypt(open(GRANT).read())
            r = _post({'grant_type': 'authorization_code', 'code': g['code'], 'redirect_uri': g['redirect_uri'],
                       'code_verifier': g['verifier'], 'client_id': cid})
            os.remove(GRANT)
        else:
            return None
    except Exception as ex:
        print('Buffer の更新の鍵が使えなかった:', ex)
        return None
    if r.get('refresh_token'):
        _save_and_push(TOKEN, encrypt({'refresh_token': r['refresh_token'], 'saved_at': int(time.time())}),
                       'Buffer の更新の鍵を新しくした（暗号化して保存。自動）')
    print('Buffer の鍵を OAuth で新しくした（使える時間: %s 秒）' % r.get('expires_in'))
    return r.get('access_token')


if __name__ == '__main__':
    # 鍵が新しくできるかだけを試す
    t = access_token()
    print('OK' if t else 'OAuth の鍵はまだない／使えない')
    sys.exit(0)
