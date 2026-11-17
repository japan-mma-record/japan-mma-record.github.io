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
              'アームバー', 'ストレッチ', 'ツイスター', 'プラッタ', 'クランク', 'スライサー', 'クラッチ', 'ヒールフック', 'シザーズ')
_NOT_SUB = ('KO', 'Ko', 'ko', '判定', 'ストップ', 'パンチ', '蹴り', 'キック', '負傷', '打撃', 'カット', 'タオル', 'テクニカル', 'スラム')
_SPELL = {'三角締め': '三角絞め', 'ヒザ十字固め': '膝十字固め', 'ひざ十字固め': '膝十字固め', 'ヒザ十字': '膝十字固め', '膝十字': '膝十字固め',
          'うで十字': '腕ひしぎ十字固め', '腕十字固め': '腕ひしぎ十字固め', '腕十字': '腕ひしぎ十字固め', '腕挫十字固め': '腕ひしぎ十字固め',
          'チョークスリーパーホールド': 'チョークスリーパー', 'リアネイキドチョーク': 'リアネイキッドチョーク', 'リアネイキットチョーク': 'リアネイキッドチョーク',
          'ギロチン': 'ギロチンチョーク', 'チキンウィングアームロック': 'チキンウイングアームロック', 'Vワンアームロック': 'V1アームロック', 'アキレス腱固': 'アキレス腱固め'}
_SUB_HEAD = re.compile(r'^(?:一本|ギブアップ|タップアウト|タップ|TO|SUB|S(?=[\s(（]|$))\s*[:：]?\s*(.*)$')
_TECH = re.compile(r'^[ァ-ヶー一-龥々ぁ-ん・\s]*[ァ-ヶー一-龥々ぁ-ん]$|^V1[ァ-ヶー・\s]+$')


def _sub(t):
    h = _SUB_HEAD.match(t)
    body = h.group(1) if h else t
    if h and not body:
        return '一本'
    body = body.strip()
    if body[:1] in '(（' and body[-1:] in ')）':
        body = body[1:-1].strip()
    body = re.sub(r'^[※*\s]+', '', body)
    body = re.sub(r'^(?:一本|ギブアップ|バーバルタップアウト|タップアウト|タップ)\s*[:：]?\s*', '', body)
    if body in ('RNC', 'R.N.C'):
        body = 'リアネイキッドチョーク'
    if not body or not _TECH.match(body) or any(w in body for w in _NOT_SUB):
        return None
    if not h and not any(w in body for w in _SUB_WORDS):
        return None
    body = re.sub(r'[\s・･]+', '', body)
    body = _SPELL.get(body, body)
    if not any(w in body for w in _SUB_WORDS):
        return None
    return f'一本（{body}）'


def tidy(m):
    m = (m or '').strip()
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


if __name__ == '__main__':
    for x in ['判定3-0', '判定（3-0）', '判定 3-0', '判定3－0', '判定(3-0)', '判定 3-0(梅田20-19 鶴和20-19 小池20-19)',
              '判定3-0 （30-28/30-28/30-28）', '判定0-3 (20-17 x3)', '判定:3-0 30-27 30-27 29-28', '判定3-0 ※30-27、30-27、30-27',
              '延長判定 0-1', '判定 ドロー', '判定2-1 (19-19 x3, マスト2名岩見)', '判定', 'ドロー 判定1-0', '判定 （２－１）']:
        print(f'{x!r:45} → {tidy(x)!r}')
