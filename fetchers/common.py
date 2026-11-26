"""自動取り込みの共通部品（Python標準機能だけで動きます）。"""
import csv, os, re, time, html, urllib.request, urllib.parse
from html.parser import HTMLParser

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
AUTO = os.path.join(DATA, 'auto')
EV_COLS = ['event_id', 'promotion', 'date', 'name', 'venue', 'sources']
B_COLS = ['event_id', 'match_no', 'fighter1_id', 'fighter1', 'fighter2_id', 'fighter2', 'winner', 'method', 'round', 'time', 'weight', 'note']
UA = 'Mozilla/5.0 (compatible; JapanMMARecordBot/1.0; +https://japan-mma-record.github.io/)'


def fetch(url, tries=3):
    """ページを取ってきて文字列で返す。文字コードはページの指定に従う。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'ja'})
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read()
                cs = r.headers.get_content_charset()
            if not cs:
                m = re.search(rb'charset=["\']?([\w-]+)', raw[:3000], re.I)
                cs = m.group(1).decode() if m else 'utf-8'
            cs = {'shift_jis': 'cp932', 'sjis': 'cp932', 'x-sjis': 'cp932', 'euc-jp': 'euc_jp'}.get(cs.lower(), cs)
            time.sleep(2)  # 相手のサイトに負担をかけないよう、1ページごとに少し待つ
            return raw.decode(cs, errors='replace')
        except Exception as e:  # 一時的な失敗はやり直す
            last = e
            time.sleep(5 * (i + 1))
    raise last


BLOCK = {'p', 'div', 'br', 'li', 'tr', 'td', 'th', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'dt', 'dd', 'section', 'article', 'table', 'ul', 'ol', 'header', 'footer', 'span'}


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript'):
            self.skip += 1
        elif tag in BLOCK and tag != 'span':
            self.out.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript'):
            self.skip = max(0, self.skip - 1)
        elif tag in BLOCK and tag != 'span':
            self.out.append('\n')

    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)


def text_lines(page_html):
    """HTMLを、画面に見えている文字の行のならびにする。"""
    p = _Text()
    p.feed(page_html)
    txt = ''.join(p.out).replace('　', ' ').replace('\xa0', ' ')
    return [re.sub(r'[ \t]+', ' ', l).strip() for l in txt.split('\n')]


def links(page_html, base):
    out = []
    for m in re.finditer(r'href\s*=\s*["\']([^"\']+)["\']', page_html, re.I):
        out.append(urllib.parse.urljoin(base, html.unescape(m.group(1))))
    return out


def read_tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8', newline='') as fp:
        return list(csv.DictReader(fp, delimiter='\t'))


def known_sources():
    """すでに収録済みの出典URL（同じ大会を二重に取り込まないため）。"""
    s = set()
    for f in (os.path.join(DATA, 'core', 'events.tsv'), os.path.join(AUTO, 'events.tsv')):
        for r in read_tsv(f):
            for u in (r.get('sources') or '').split():
                s.add(u.rstrip('/').replace('://www.', '://'))
    return s


def is_known(url, known):
    return url.rstrip('/').replace('://www.', '://') in known


def append(event, bouts):
    """自動取り込みした大会を data/auto に書き足す。"""
    os.makedirs(AUTO, exist_ok=True)
    for name, cols, rows in (('events.tsv', EV_COLS, [event]), ('bouts.tsv', B_COLS, bouts)):
        path = os.path.join(AUTO, name)
        new = not os.path.exists(path)
        with open(path, 'a', encoding='utf-8', newline='') as fp:
            w = csv.DictWriter(fp, fieldnames=cols, delimiter='\t', lineterminator='\n', extrasaction='ignore')
            if new:
                w.writeheader()
            for r in rows:
                w.writerow({k: (r.get(k) or '') for k in cols})


def is_out_of_scope(text):
    """キッズ・ジュニアの試合や、MMA以外の試合は取り込まない。"""
    t = re.sub(r'ジュニア[･・]?(ヘビー|ライト|ウェルター|ミドル|フェザー|バンタム|フライ)', '', text or '')
    if re.search(r'キッズ|少年|子供|子ども|小学|中学|高校生|ジュニア|Jr\.?|U-?1[0-8]', t):
        return True
    if re.search(r'(?i)グラップリング|キックボクシング|キック|柔術|ボクシング|エキシビション|エキシビジョン|\bkick|grappling|boxing', text or '') and not re.search(r'(?i)MMA|総合', text or ''):   # 「KICKルール」のような英字の書き方も
        return True
    return False
