"""出典の結果ページ（probe-web で取ったもの）から「選手名（所属）」を読み取り、data/gyms.tsv に足す行を作る。

使い方: python3 build.py のあと、python3 fetchers/gym_paren.py DIR [DIR...] >> data/gyms.tsv
  DIR は probe-web ブランチの probe/ と同じ形（index.txt と out/N.html）のフォルダ。
  index.txt の URL が _site/data/events.json の出典URLに入っている大会の試合だけを見る。
決まり:
  ・その試合の2人ともの名前が「名前（所属）」「名前(所属)」の形でページにあり、その選手の所属が1つに決まるときだけ入れる。
  ・Fighting NEXUS 公式（fighting-nexus.net）は「名前／所属／VS／名前／所属」の並びが試合の2人と合うときだけ。
  ・肩書き（推薦・王者・デビュー戦・〇〇級など）、国名・都道府県、名前の読み、「監督：」、「フリー」は入れない。
  ・すでに所属が入っている試合（data/gyms.tsv・表彰台）は出さない。Shift_JIS・EUC-JP のページも読む。
"""
import json, re, html, sys, os, collections

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ev = json.load(open(f'{REPO}/_site/data/events.json'))
bouts = json.load(open(f'{REPO}/_site/data/bouts.json'))
url2ev = collections.defaultdict(list)
for e in ev:
    for u in e[5]:
        url2ev[u].append(e[0])
have = set()
for line in open(f'{REPO}/data/gyms.tsv', encoding='utf-8').read().splitlines()[1:]:
    p = line.split('\t')
    if len(p) >= 4 and p[3].strip():
        have.add((p[0], p[1], re.sub(r'\s', '', p[2])))

COUNTRIES = set('アルジェリア チュニジア リビア スーダン エチオピア ソマリア コンゴ アンゴラ ジンバブエ ザンビア ウガンダ タンザニア イラク シリア ヨルダン レバノン サウジアラビア クウェート カタール バーレーン オマーン アフガニスタン ブータン マカオ 東ティモール ブルネイ パプアニューギニア スロバキア スロベニア ボスニア 北マケドニア マケドニア アルバニア コソボ モンテネグロ キプロス アイスランド ルクセンブルク モナコ アイルランド ポルトガル ベルギー スイス オーストリア チェコ ハンガリー ルーマニア ブルガリア セルビア クロアチア ギリシャ エジプト モロッコ ケニア ガーナ コロンビア ベネズエラ エクアドル ボリビア ウルグアイ パラグアイ プエルトリコ ドミニカ タジキスタン トルクメニスタン ダゲスタン チェチェン パキスタン バングラデシュ スリランカ サモア トンガ フィジー リトアニア ラトビア エストニア モルドバ イスラエル UAE 日本 アメリカ 米国 ブラジル 韓国 中国 タイ ロシア フランス イギリス 英国 オランダ カナダ モンゴル フィリピン オーストラリア ドイツ イタリア スペイン ポーランド ウクライナ カザフスタン キルギス ウズベキスタン 台湾 香港 シンガポール マレーシア インドネシア ベトナム インド ニュージーランド メキシコ ペルー アルゼンチン チリ グアム ハワイ スウェーデン ノルウェー フィンランド デンマーク ベラルーシ ジョージア グルジア アルメニア アゼルバイジャン トルコ イラン ネパール ミャンマー カンボジア ラオス 北朝鮮 南アフリカ ナイジェリア カメルーン セネガル ジャマイカ キューバ USA Japan Brazil Korea Thailand China Russia'.split())
PREFS = set('北海道 青森 岩手 宮城 秋田 山形 福島 茨城 栃木 群馬 埼玉 千葉 東京 神奈川 新潟 富山 石川 福井 山梨 長野 岐阜 静岡 愛知 三重 滋賀 京都 大阪 兵庫 奈良 和歌山 鳥取 島根 岡山 広島 山口 徳島 香川 愛媛 高知 福岡 佐賀 長崎 熊本 大分 宮崎 鹿児島 沖縄'.split())
PREFS |= {p + s for p in list(PREFS) for s in '都道府県'}
BAD = re.compile(r'\d+(\.\d+)?\s*(kg|ｋｇ|Kg|KG|lb|cm|ｃｍ)|\d+\s*(勝|敗|分|戦|歳|才|年生|位)|戦績|王者|挑戦者|チャンピオン|優勝|ランキング|ランカー|位$|代表|選手|出身|高校|中学|小学|大学$|学年|職業|会社員|^[\d\s\-－:：.]+$|vs|ＶＳ|VS|反則|判定|一本|KO|TKO|ラウンド|^\d|第\d|招待|推薦枠|試合|ドクター|減点|イエロー|計量|kg|延長|※|→|http|監督|コーチ$|^コーチ')

TITLE = re.compile(r'推薦|連覇|冠王|冠$|制覇|王者|挑戦者|チャンピオン|優勝|代表|ランカー|ランキング|位$|招待|甲子園|世界一|日本一|^元|^現|MVP|賞$|デビュー|参戦|出場|復帰|引退|ラストファイト|キング・オブ|クイーン・オブ|級|外敵|軍$')

def clean_gym(g):
    import unicodedata
    g = re.sub(r'[\uff61-\uff9f]+', lambda m: unicodedata.normalize('NFKC', m.group(0)), g)
    g = re.sub(r'\s+', ' ', g).strip().strip('　 ・,、')
    g = re.sub(r'所属$', '', g).strip()
    for c in ('北朝鮮', '韓国', '中国', '台湾', '香港', '日本', '米国', '英国'):
        if g.startswith(c) and len(g) > len(c) + 1:
            g = g[len(c):].strip(' ・')
            break
    if re.sub(r'^\S+\s+', '', g) in ('フリー', '無所属', 'FREE', 'Free', 'free'):
        return ''
    if not g or len(g) > 40:
        return ''
    parts = [x.strip() for x in re.split(r'[/／]', g)]
    keep = []
    for x in parts:
        if not x:
            continue
        if re.search(r'(共和国|合衆国|王国|連邦)$', x) or x in COUNTRIES or x in PREFS or x.rstrip('出身') in COUNTRIES | PREFS:
            continue
        if x[0] in '＝=' or TITLE.search(x):
            continue
        if BAD.search(x):
            return ''
        keep.append(x)
    if not keep:
        return ''
    g = g if len(keep) == len(parts) else '/'.join(keep)
    if g in ('フリー', 'フリーランス', '無所属', 'なし', '-', '－', 'ー', '不明', '未定', 'FREE', 'Free', 'free'):
        return ''
    return g


def is_reading(name, g):
    # （ ）の中が名前の読み（ひらがな、またはローマ字の名前のカタカナ読みに「/フリー」など）なら所属ではない
    parts = [x.strip() for x in re.split(r'[/／]', g)]
    for x in parts:
        if re.fullmatch(r'[ぁ-んー“”"・\s]+', x):
            return True
    if len(parts) > 1 and re.fullmatch(r'[ァ-ヶー・“”"\s]+', parts[0]) and '・' in parts[0] and re.fullmatch(r'[A-Za-z .\'-]+', name):
        return True
    return False


def page_text(path):
    raw = open(path, 'rb').read()
    m = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:3000])
    enc = (m.group(1).decode().lower() if m else 'utf-8')
    enc = {'shift_jis': 'cp932', 'sjis': 'cp932', 'x-sjis': 'cp932', 'shift-jis': 'cp932', 'euc-jp': 'euc_jp'}.get(enc, enc)
    try:
        t = raw.decode('utf-8')
    except UnicodeDecodeError:
        try:
            t = raw.decode(enc, errors='replace')
        except LookupError:
            t = raw.decode('cp932', errors='replace')
    t = re.sub(r'(?is)<(script|style|noscript)\b.*?</\1>', '', t)
    t = re.sub(r'(?is)<!--.*?-->', '', t)
    t = re.sub(r'(?i)<br\s*/?>|</(p|div|li|tr|td|th|h\d|dt|dd|span)>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = html.unescape(t).replace('　', ' ').replace('\xa0', ' ')
    return t


NAMECH = re.compile(r'[\w぀-ヿ一-鿿・ー"”“’\'.＝=]')


def paren_map(text, name):
    """name（空白は無視）の直後に（所属）が付いた箇所を全部拾う"""
    out = []
    pat = r'[ \t]*'.join(re.escape(c) for c in name) + r'[ \t]*[○×〇●△▲◯]?[ \t]*\n?[ \t]*[（(]([^（）()\n]{1,40})[)）]'
    for m in re.finditer(pat, text):
        s = m.start()
        pre = re.sub(r'[ \t]', '', text[max(0, s - 6):s])
        if pre:
            pc = pre[-1]
            if pc not in '〇○●◯×✕✖△▲☆★◎◇◆□■' and NAMECH.match(pc) and pre[-2:].lower() != 'vs' and pre[-2:] not in ('ＶＳ', 'ｖｓ'):
                continue
        out.append(m.group(1))
    return out


def vs_pairs(text):
    L = [x.strip() for x in text.split('\n') if x.strip()]
    pairs = []
    for i, x in enumerate(L):
        if x in ('VS', 'vs', 'ＶＳ', 'Vs', 'vs.') and 2 <= i < len(L) - 2:
            pairs.append((L[i - 2], L[i - 1], L[i + 1], L[i + 2]))
    return pairs


def nz(s):
    return re.sub(r'\s', '', s or '')


def run(dirs):
    res = []
    for d in dirs:
        idx = {}
        for line in open(os.path.join(d, 'index.txt'), encoding='utf-8'):
            p = line.split()
            if len(p) >= 4 and p[1] == '200':
                idx[p[0]] = p[3]
        for n, url in idx.items():
            path = os.path.join(d, 'out', f'{n}.html')
            if not os.path.exists(path):
                continue
            text = page_text(path)
            pairs = vs_pairs(text) if 'fighting-nexus.net' in url else []
            for eid in url2ev.get(url, []):
                for b in bouts.get(eid, []):
                    no = str(b[0]) if b[0] else ''
                    n1, n2 = nz(b[2]), nz(b[4])
                    if not n1 or not n2 or '＆' in n1 or '&' in n1:
                        continue
                    got = {}
                    if pairs:
                        for a, ga, c, gc in pairs:
                            if {nz(a), nz(c)} == {n1, n2}:
                                got = {nz(a): ga, nz(c): gc}
                    else:
                        for nm in (n1, n2):
                            gs = {clean_gym(g) for g in paren_map(text, nm)}
                            raw = paren_map(text, nm)
                            if raw:
                                got[nm] = raw
                        if len(got) < 2:
                            continue
                        g2 = {}
                        for nm, raw in got.items():
                            cs = {clean_gym(g) for g in raw}
                            cs.discard('')
                            if len(cs) == 1 and all(clean_gym(g) for g in raw) or (len(cs) == 1):
                                g2[nm] = cs.pop()
                        got = g2
                    for nm, orig in ((n1, b[2]), (n2, b[4])):
                        g = got.get(nm)
                        if g is None:
                            continue
                        g = clean_gym(g)
                        if not g or is_reading(orig, g):
                            continue
                        if (eid, no, nm) in have or (eid, '', nm) in have:
                            continue
                        cur = b[16] if nm == n1 else b[17]
                        if cur:
                            continue
                        res.append((eid, no, orig, g, url))
    seen = set()
    for r in res:
        k = r[:3]
        if k in seen:
            continue
        seen.add(k)
        print('\t'.join(r))


if __name__ == '__main__':
    run(sys.argv[1:])
