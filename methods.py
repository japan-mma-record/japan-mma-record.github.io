"""決まり手の書き方をそろえる（サイトを作るたびに、すべての試合に当てはめます）。

判定の書き方:
  判定3-0
  判定3-0（30-28・30-28・29-28）   … 採点が出典にあるとき
  延長判定2-1 / 本戦判定… / 負傷判定… / テクニカル判定… も同じ形
採点以外の言葉（「ドロー」「ページ表記」など）がついているものは、意味を変えないよう元のまま残します。
"""
import re
import unicodedata

_DASH = '-－ー−‐–—対'
_HEAD = re.compile(r'^\s*(延長|再延長|本戦|負傷|テクニカル)?\s*判定\s*[:：]?\s*'
                   r'[(（]?\s*(\d)\s*[' + _DASH + r']\s*(\d)\s*[)）]?\s*(.*)$')
_SCORE = r'([^\d\s()（）・、,，/／]*?)\s*(\d{1,3})\s*[' + _DASH + r']\s*(\d{1,3})'


def _scores(rest):
    """採点だけが書かれていれば、['30-28', …] を返す。それ以外の言葉があれば None。"""
    s = rest.strip()
    s = re.sub(r'^[※*:：\s]+', '', s)
    if s.startswith(('(', '（')) and s.endswith((')', '）')):
        s = s[1:-1].strip()
    if not s:
        return []
    out = []
    pos = 0
    pat = re.compile(r'\s*' + _SCORE + r'(?:\s*[x×]\s*(\d))?\s*[・、,，/／]?\s*')
    while pos < len(s):
        m = pat.match(s, pos)
        if not m or m.end() == pos:
            return None
        name, a, b, times = m.group(1), m.group(2), m.group(3), m.group(4)
        if name and not re.fullmatch(r'[ぁ-んァ-ヶ一-龥々A-Za-zＡ-Ｚａ-ｚー]+', name):
            return None
        out += [f'{name}{a}-{b}'] * (int(times) if times else 1)
        pos = m.end()
    return out


# 一本: 「一本（技の名前）」にそろえる。同じ技の書き方の違いだけを直す（別の呼び名は変えない）。
_SUB_WORDS = ('絞め', '締め', '固め', 'ロック', 'ホールド', 'チョーク', '十字', 'スリーパー', '腕がらみ', 'ひしぎ',
              'アームバー', 'ストレッチ', 'ツイスター', 'プラッタ', 'クランク', 'スライサー', 'クラッチ', 'ヒールフック', 'シザーズ', 'RNC')
_NOT_SUB = ('KO', 'Ko', 'ko', '判定', 'ストップ', 'パンチ', '蹴り', 'キック', '負傷', '打撃', 'カット', 'タオル', 'テクニカル', 'スラム')
_SPELL = {'三角締め': '三角絞め', 'ヒザ十字固め': '膝十字固め', 'ひざ十字固め': '膝十字固め', 'ヒザ十字': '膝十字固め', '膝十字': '膝十字固め',
          'うで十字': '腕ひしぎ十字固め', '腕十字固め': '腕ひしぎ十字固め', '腕十字': '腕ひしぎ十字固め', '腕挫十字固め': '腕ひしぎ十字固め',
          
          'ギロチン': 'ギロチンチョーク', 'チキンウィングアームロック': 'チキンウイングアームロック', 'Vワンアームロック': 'V1アームロック', 'アキレス腱固': 'アキレス腱固め'}
_TECH = re.compile(r'^[ァ-ヶー一-龥々ぁ-んA-Z0-9・\s]*[ァ-ヶー一-龥々ぁ-んA-Z]$')


_EN = {'armbar': '腕ひしぎ十字固め', 'arm bar': '腕ひしぎ十字固め', 'sleeper choke': 'RNC', 'front neck lock': 'フロントネックロック',
       'front headlock': 'フロントヘッドロック', 'guillotine choke': 'ギロチンチョーク', 'ankle lock': 'アンクルホールド',
       'kneebar': '膝十字固め', 'heel hook': 'ヒールホールド', 'kimura': 'アームロック', 'americana': 'アームロック'}
_SUB_HEAD = re.compile(r'^(?:一本|1本|ギブアップ|タップアウト|タップ|TO|SUB|S|TS|techsub|submission)(?=[\s(（:：=［\[]|$)\s*[:：=]?\s*(.*)$', re.I)


def _clean_body(body):
    """「一本」などの後ろの部分から、技の名前だけを取り出す。"""
    tag = ''
    mm = re.search(r'\s*(\[[^\]]*\]|(?<=[)）])※[^()（）]*)\s*$', body)   # [決勝] や後ろの※注記は後ろに残す
    if mm:
        tag, body = ' ' + mm.group(1), body[:mm.start()]
    for _ in range(4):
        b0 = body
        body = body.strip()
        body = re.sub(r'^[※*=＝\s]+|[※*\s]+$', '', body)
        body = re.sub(r'(?:本戦|延長R?|\d+R|\d+\s*分\s*[\d.]*\s*秒?|[\d.]+\s*秒|\d+[’\'.:]\d+”?|\bR\b)\s*', '', body)
        body = re.sub(r'[(（]\s*(?:延長R?|本戦)?\s*[)）]', '', body)
        body = _outer(body)
        body = re.sub(r'^[(（]?(?:テクニカル・?サブミッション|バーバルタップアウト|タップアウト|ギブアップ|一本|タップ)[)）]?\s*[:：;/／]?\s*', '', body)
        body = re.sub(r'^[(（](.*)[)）]$', r'\1', body) if re.fullmatch(r'[(（][^()（）]*[)）]', body) else body
        body = re.sub(r'による$|により$', '', body)
        if body == b0:
            break
    if re.search(r'[:：]', body):                       # 「アームバー：腕ひしぎ十字固め」→ 後ろ側
        body = re.split(r'[:：]', body)[-1]
    body = body.strip()
    body = _EN.get(body.lower(), body)
    if re.fullmatch(r'[ァ-ヶー・\s]+', body):
        body = re.sub(r'[\s・･]+', '', body)
    body = _SPELL.get(body, body)
    return body.replace('(', '（').replace(')', '）'), tag


def _outer(b):
    """全体を囲むかっこを1組はずす（中のかっこは残す）。"""
    if b[:1] not in '(（' or b[-1:] not in ')）':
        return b
    depth = 0
    for i, ch in enumerate(b):
        depth += ch in '(（'
        depth -= ch in ')）'
        if depth == 0 and i < len(b) - 1:
            return b
    return b[1:-1].strip()


def _sub(t):
    h = _SUB_HEAD.match(t)
    if h:                                   # 「一本・ギブアップ・タップアウト・TO・S・SUB」→ すべて一本
        body = h.group(1)
        if '一本' in body.replace('一本', '', 0)[1:] and body.count('一本') > 1:
            return None                     # 1つの欄に2試合分が書かれているものは触らない
        body, tag = _clean_body(body)
        if not body or body in ('一本', 'ギブアップ', 'タップアウト'):
            return '一本' + tag
        if '一本' in body or len(body) > 30:
            return None
        return f'一本（{body}）{tag}'
    # 技の名前だけ → 一本（技の名前）（前についた「1R 3:10」などの時間は取る）
    body = re.sub(r'^(?:\d+\s*[×x]\s*\d+R\s*)?(?:\d+R\s*)?(?:\d+\s*[:：]\s*\d+|\d+\s*分(?:\s*\d+\s*秒)?)?\s*', '', t.strip())
    if body[:1] in '(（' and body[-1:] in ')）':
        body = body[1:-1].strip()
    body = re.sub(r'^(?:タップアウト|ギブアップ)\s*[:：]\s*', '', body)
    if not body or not (_TECH.match(body) or body == 'RNC') or any(w in body for w in _NOT_SUB):
        return None
    body = re.sub(r'[\s・･]+', '', body)
    body = _SPELL.get(body, body)
    if not any(w in body for w in _SUB_WORDS):
        return None
    return f'一本（{body}）'


# 技の呼び名の統一（どの決まり手の中でも置き換える）。左の書き方 → 右の正式な書き方
ALIAS = [
    (r'三角締め?(?!め)', '三角絞め'),                                   # 三角締め・三角締 → 三角絞め
    (r'(?<!アーム)トライアングル・?チョーク', '三角絞め'),                # アームトライアングル（肩固め）は別の技なので変えない
    (r'(?i)(?<!arm )(?<!arm-)triangle(?: choke)?', '三角絞め'),
    # 後ろからの絞め（リアネイキッドチョーク）はすべて RNC。フロントチョーク系は別の技なので変えない
    (r'(?<!フロント)(?<!フロント・)(?<!フロント )(?:チョーク・?スリーパー(?:・?ホールド)?|スリーパー・?ホールド|スリーパー)', 'RNC'),
    (r'裸[絞締]め?', 'RNC'),
    (r'ヒザ十字(?:固め)?|ひざ十字(?:固め)?', '膝十字固め'),
    (r'リア・?ネイキ[ッ]?[ドト]・?チョーク', 'RNC'),
    (r'バック・?チョーク', 'RNC'),
    (r'(?i)rear[- ]?naked[- ]?choke|\bR\.N\.C\.?', 'RNC'),
    # 打撃の呼び名
    (r'グランド', 'グラウンド'),
    (r'ヒザ蹴り|ひざ蹴り|ヒザ蹴|膝蹴(?!り)', '膝蹴り'),
    (r'スタンド(?:で|状態で|状態の)?の?パンチ', 'スタンドのパンチ'),
    (r'グラウンド(?:で|状態で|状態の)?の?パンチ|パウンド', 'グラウンドのパンチ'),
    (r'(?:セコンド(?:から|より)?の?)?タオル(?:の)?投入|セコンドのタオル', 'セコンドのタオル'),
    (r'(?i)\bno ?contest\b|ノー・コンテスト', 'ノーコンテスト'),
]


_KEEP = re.compile(r'フロント[・ ]?(?:チョーク[・ ]?)?スリーパー(?:[・ ]?ホールド)?')   # フロントチョーク系は RNC にしない


def _alias(m):
    kept = _KEEP.findall(m)
    m = _KEEP.sub('\x00', m)
    for a, b in ALIAS:
        m = re.sub(a, b, m)
    for k in kept:
        m = m.replace('\x00', k, 1)
    return m


_JUNK = r'[\s※*＊:：;/／→=、,]+'


def _paren(body):
    """中身を（ ）でくくる形にする。中身が空なら空。"""
    body = re.sub(r'^' + _JUNK + r'|' + _JUNK + r'$', '', body.strip())
    body = _outer(body).strip()
    body = re.sub(r'^' + _JUNK + r'|' + _JUNK + r'$', '', body)
    body = body.replace('(', '（').replace(')', '）').replace(':', '：')
    return f'（{body}）' if body else ''


def _draw(t):
    """引き分け → 「引き分け」「引き分け（時間切れ）」「引き分け（判定1-1）」"""
    if not re.search(r'ドロー|引き?分け?|(?i:\bdraw\b)', t) or re.search(r'一本|KO|無効|ノーコンテスト|反則|失格|勝', t):
        return None
    timeout = '時間切れ' in t
    judged = '判定' in t
    rest = re.sub(r'(?i)ドロー|引き?分け?|時間切れ|判定|\bdraw\b|[※*()（）\[\]:：、,\s]', ' ', t).strip()
    if not rest:
        return '引き分け（時間切れ）' if timeout else ('引き分け（判定）' if judged else '引き分け')
    mm = re.match(r'^(\d)\s*[' + _DASH + r']\s*(\d)(?!\d)\s*(.*)$', rest)
    if not mm:
        sc = None if timeout else _scores(rest)
        return f'引き分け（判定・' + '・'.join(sc) + '）' if sc else None
    if timeout and not judged:
        return None
    sc = _scores(mm.group(3))
    if sc is None:
        return None
    return f'引き分け（判定{mm.group(1)}-{mm.group(2)}' + ('・' + '・'.join(sc) if sc else '') + '）'


def _nc(t):
    """無効試合 → 「ノーコンテスト」「ノーコンテスト（理由）」"""
    mm = re.match(r'^(?:無効試合|ノーコンテスト|NC\b)\s*(.*)$', t)
    if not mm:
        return None
    return 'ノーコンテスト' + _paren(mm.group(1))


def _strike(kind, body):
    body = re.sub(r'(?<=パンチ)連打|(?<=膝蹴り)連打', '', body)
    body = re.sub(r'(?:に|で)?よる$|により$|のため$', '', _outer(body.strip()).strip())
    return kind + _paren(body)


def _tko(t):
    """TKO → 「TKO」「TKO（レフェリーストップ）」「TKO（グラウンドのパンチ）」"""
    if re.match(r'^TKO', t):
        body = t[3:]
    elif re.match(r'^(?:レフェリーストップ|レフリーストップ|ドクターストップ)', t) and '判定' not in t:
        body = t
    else:
        return None
    body = re.sub(r'(?:による)?\s*→?\s*TKO(?:勝ち)?$|TKO', '', body)
    body = body.replace('レフリー', 'レフェリー')
    if body.count('（') + body.count('(') > 2 or len(body) > 40:
        return 'TKO' + _paren(body) if re.match(r'^\s*[(（]', body) else None
    # 「レフェリーストップ」と原因が両方書いてあれば、原因だけを残す
    inner = _outer(re.sub(r'^' + _JUNK, '', body.strip()))
    cause = re.sub(r'[(（]?レフェリーストップ[)）]?\s*(?:[:：/／→]|で|による)?', ' ', inner)
    cause = re.sub(r'\s*[(（]\s*[)）]\s*', ' ', cause)
    cause = re.sub(r'^\s*(?:で|による)|(?:で|による)\s*$', '', cause.strip())
    if cause.strip(' ※*:：/／→') == '' and 'レフェリーストップ' in inner:
        return 'TKO（レフェリーストップ）'
    return _strike('TKO', cause if 'レフェリーストップ' in inner else inner)


def _ko(t):
    mm = re.match(r'^KO(?![a-zA-Z])\s*(.*)$', t)
    if not mm or re.search(r'\d', mm.group(1)):
        return None
    return _strike('KO', mm.group(1))


def tidy(m):
    m = re.sub(r'<!--.*?(?:-->|$)', '', m or '', flags=re.S)   # Wikipediaの注釈コメントは載せない
    m = _alias(m.strip())
    t = unicodedata.normalize('NFKC', m)
    for f in (_nc, _draw, _tko, _ko):
        r = f(t)
        if r:
            return r
    m = re.sub(r'^1本', '一本', m)
    m = re.sub(r'^(.+?)\s*[(（](?:タップアウト|ギブアップ|タップ)[)）]$', r'一本 \1', m)
    m = re.sub(r'^(?i:submission)\s*,\s*', '一本 ', m)
    if re.fullmatch(r'一本（.{40,}）', m):   # 試合の経過の文章が入ってしまったもの
        m = '一本'
    if '判定' not in m:
        s = _sub(unicodedata.normalize('NFKC', m)) if m else None
        return s or m
    t = unicodedata.normalize('NFKC', m)
    h = _HEAD.match(t)
    if not h:
        return m
    pre, a, b, rest = h.group(1) or '', h.group(2), h.group(3), h.group(4)
    sc = _scores(rest)
    if sc is None:
        return m
    out = f'{pre}判定{a}-{b}'
    return out + ('（' + '・'.join(sc) + '）' if sc else '')



# 大会名：「Gladiator - Gladiator 7」のような、団体名が二重になった書き方を直す
_UPPER = {'zst': 'ZST', 'heat': 'HEAT', 'gladiator': 'GLADIATOR', 'dream': 'DREAM', 'deep': 'DEEP', 'rizin': 'RIZIN',
          'pride': 'PRIDE', 'grachan': 'GRACHAN', 'nexus': 'NEXUS', 'isshin': 'ISSHIN', 'ikusa': 'IKUSA', 'sengoku': 'SENGOKU'}


def event_name(n):
    n = (n or '').strip()
    m = re.match(r'^(.+?) - (.+)$', n)
    if m and m.group(2).lower().replace(' ', '').startswith(m.group(1).lower().replace(' ', '')):
        n = m.group(2)
    w = n.split(' ', 1)
    if w and w[0].lower() in _UPPER:
        n = _UPPER[w[0].lower()] + (' ' + w[1] if len(w) > 1 else '')
    m = re.fullmatch(r'(DREAM|PRIDE|RIZIN) (\d+)', n)      # 正式な表記は「DREAM.17」のように点でつなぐ
    if m:
        n = f'{m.group(1)}.{m.group(2)}'
    return n


# 出典：海外の記録サイトの名前・住所は載せず、「海外の記録サイト」とだけ書く
OVERSEAS = '海外の記録サイト'


def clean_sources(src):
    toks = [t for t in (src or '').split(' ') if t]
    keep = [t for t in toks if not re.search(r'(?i)sherdog|tapology', t) and t != OVERSEAS]
    if len(keep) < len(toks) or OVERSEAS in toks:
        keep.append(OVERSEAS)
    return ' '.join(keep)


# 階級：「フェザー級」「女子アトム級」「65kg契約」の形にそろえる。特別なルール名は「・」のあとに残す
_CLASSES = ('スーパーヘビー', 'ライトヘビー', 'クルーザー', 'ヘビー', 'ミドル', 'スーパーウェルター', 'ウェルター', 'スーパーライト', 'ライト',
            'スーパーフェザー', 'フェザー', 'スーパーバンタム', 'バンタム', 'スーパーフライ', 'ライトフライ', 'フライ', 'ストロー',
            'スーパーアトム', 'アトム', 'ミニマム', 'ミクロ', 'メガトン', '無差別', 'ピン')
_PROMO = r'DEEP ?JEWELS|DEEP|JEWELS|修斗|パンクラス|ZST|MMA|RIZIN|GRACHAN|HEAT|DREAM|SRC|SENGOKU|戦極|HERO\'S|PRIDE|GLADIATOR|NEXUS'
_ROUTINE = re.compile(r'^(?:' + _PROMO + r'|MMAルール|総合格闘技ルール|総合ルール|総合格闘技|総合|RIZIN ?MMAルール|ZSTルール|DEEPルール|修斗ルール|パンクラスルール|プロ|プロ修斗公式戦|'
                      r'シングルマッチ|ワンマッチ|\d+分\s*\d+\s*(?:R|ラウンド)(?:\s*[(（]延長\s*\d+\s*R[)）])?|\d+分×?\d+R|,)$', re.I)


def weight(w):
    t = unicodedata.normalize('NFKC', w or '').strip()
    if not t or '記載なし' in t:
        return ''
    t = re.sub(r'\[[^\]]*\]', ' ', t)                                     # [-70.0Kg] など
    t = re.sub(r'[(（]\s*-?[\d.]+\s*kg(?:以下|未満)?\s*[)）]', ' ', t, flags=re.I)   # (70.3kg) など
    t = re.sub(r'(\d+)\s*分\s*(\d+)\s*(R|ラウンド)', r'\1分\2\3', t)
    t = re.sub(r'(?i)RIZIN ?MMAルール\s*[:：]?\s*(?:\d+分\d+R)?', ' ', t)
    t = re.sub(r'[(（][^()（）]*[)）]', lambda m: m.group(0).replace(' ', '\x01').replace('・', '\x02'), t)   # かっこの中は区切らない
    t = re.sub(r'(\d+\s*分\s*\d+\s*R)', r' \1 ', t)
    t = re.sub(r'(?i)RIZIN ?MMAルール\s*[:：]?\s*\d+\s*分\s*\d+\s*R', ' ', t)
    parts = [x.strip() for x in re.split(r'[・/／;；、,]|\s{1,}(?=\S)', t) if x.strip()]
    wt, rule = '', []
    for x in parts:
        x = re.sub(r'\(延長\d+R\)', '', x).strip()
        if _ROUTINE.match(x) or not x:
            continue
        m = re.search(r'(女子)?(?:' + _PROMO + r')?\s*(女子)?(' + '|'.join(_CLASSES) + r')級(?:戦|契約)?', x)
        if m and not wt:
            wt = (m.group(1) or m.group(2) or '') + m.group(3) + '級'
            rest = (x[:m.start()] + x[m.end():]).strip(' （）()')
            rest = re.sub(r'-?[\d.]+\s*kg(?:以下|未満)?(?:契約)?', '', rest, flags=re.I).strip()
            rest = re.sub(r'^(?:' + _PROMO + r')', '', rest).strip()
            if rest and not _ROUTINE.match(rest) and not re.fullmatch(r'\d+分\d+R', rest):
                rule.append(rest)
            continue
        m = re.search(r'(?:契約体重\s*)?(\d+(?:\.\d+)?)\s*lb', x, re.I)
        if m and wt in ('', '契約体重'):
            wt = f'{round(float(m.group(1)) * 0.45359237, 1):g}kg契約'
            continue
        m = re.search(r'-?\s*(\d+(?:\.\d+)?)\s*kg(?:以下|未満)?(契約|級)?', x, re.I)
        if m and wt in ('', '契約体重') and re.fullmatch(r'(?:' + _PROMO + r')?[-\s\d.kgKG以下未満契約級戦]*', x):
            wt = f'{float(m.group(1)):g}kg' + ('契約' if m.group(2) == '契約' or '契約' in x else '')
            continue
        if x in ('メガトン', '無差別', '無差別契約'):
            wt = wt or (x[:-2] if x.endswith('契約') else x) + '級'
            continue
        if x in ('契約体重', 'キャッチウェイト', '契約'):
            wt = wt or '契約体重'
            continue
        rule.append(x)
    rule = [x.replace('\x01', ' ').replace('\x02', '・') for x in rule]
    out = wt
    if rule:
        out = (out + '・' if out else '') + '・'.join(dict.fromkeys(rule))
    return out

if __name__ == '__main__':
    for x in ['判定3-0', '判定（3-0）', '判定 3-0', '判定3－0', '判定(3-0)', '判定 3-0(梅田20-19 鶴和20-19 小池20-19)',
              '判定3-0 （30-28/30-28/30-28）', '判定0-3 (20-17 x3)', '判定:3-0 30-27 30-27 29-28', '判定3-0 ※30-27、30-27、30-27',
              '延長判定 0-1', '判定 ドロー', '判定2-1 (19-19 x3, マスト2名岩見)', '判定', 'ドロー 判定1-0', '判定 （２－１）']:
        print(f'{x!r:45} → {tidy(x)!r}')
