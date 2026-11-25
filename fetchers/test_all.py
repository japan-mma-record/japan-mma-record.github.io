"""取り込みプログラムが、保存してある本物の公式ページ（tests/）を正しく読めるか確かめる。
公式サイトの作りが変わったときは、新しいページを tests/ に保存し直し、ここの確認も合わせて直す。"""
import os, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from common import text_lines
import pancrase, deep, shooto, rizin, grachan, wardog, upcoming

def read(n): return open(os.path.join(here, 'tests', n), encoding='utf-8', errors='replace').read()

ev, b = pancrase.parse(text_lines(read('pancrase_368.html')), 'x')
assert ev['date'] == '2026-11-08' and ev['name'] == 'PANCRASE 368' and len(b) == 11, (ev, len(b))
assert b[0]['fighter1'] == '菊入正行' and b[0]['winner'] == '1' and b[0]['round'] == '2' and b[0]['time'] == '2:21'
ev, b = deep.parse(text_lines(read('deep_133.html')), 'x')
assert ev['date'] == '2026-09-13' and ev['name'] == 'DEEP 133 IMPACT' and len(b) == 8, (ev, len(b))
assert b[1]['fighter2'] == '新井丈' and b[1]['winner'] == '2' and b[1]['time'] == '1:42'
ev, b = deep.parse(text_lines(read('deep_134.html')), 'x')   # 勝ちの印が「￮」の大会
assert ev['name'] == 'DEEP 134 IMPACT' and len(b) == 10 and all(x['winner'] in ('1', '2') for x in b), (ev, len(b))
assert [x for x in b if x['match_no'] == 1][0]['method'] == '判定3-0'
ev, b = shooto.parse(read('shooto_299.html'), 'x')
assert ev['date'] == '2026-06-28' and len(b) == 10, (ev, len(b))
assert b[0]['winner'] == '2' and b[1]['method'] == '一本（三角絞め）' and b[1]['time'] == '2:19'
ev, b = rizin.parse(read('rizin_53.html'), 'x')
assert ev['date'] == '2026-05-10' and ev['name'] == 'RIZIN.53' and len(b) >= 10, (ev, len(b))
assert b[0]['winner'] == '2' and b[0]['round'] == '1' and b[0]['time'] == '2:08'
ev, b = grachan.parse(text_lines(read('grachan_86.html')), 'x')
assert ev['name'] == 'GRACHAN86' and len(b) == 8, (ev, len(b))
assert b[0]['fighter1'] == '岡田達朗' and b[0]['winner'] == '2' and b[0]['round'] == '2' and b[0]['time'] == '1:09'
assert grachan.list_items(read('grachan_result_list.html'))[1][:2] == ('https://grachan.jp/grachan86-result/', '2026-10-25')
ev, b = wardog.parse(text_lines(read('wardog_59.html')), 'x')
assert ev['name'] == 'WARDOG.59' and ev['date'] == '2026-11-08' and len(b) >= 10, (ev, len(b))
assert b[-1]['fighter1'] == '浅野こうき' and b[-1]['winner'] == '1' and b[-1]['time'] == '4:07'
rows = upcoming.parse_efight_month(read('efight_202612.html'))
assert any(r[1] == 'DEEP 135 IMPACT' and r[0] == '2026-12-13' for r in rows), rows
assert upcoming.promo_of('DEEP 135 IMPACT') == 'DEEP' and upcoming.promo_of('DEEP☆KICK 81') == '' and upcoming.promo_of('PANCRASE 369') == 'パンクラス'
v, c = upcoming.parse_efight_event(read('efight_event.html'))
assert len(c) == 9 and c[0][0] == 'イリー・プロハースカ', c[:2]
print('見本ページの読み取り: すべて正常')
import jbjjf_bracket   # JBJJF のトーナメント表（第15回全日本マスター柔術選手権 2021年9月24日 1マット）
bb = jbjjf_bracket.usable(jbjjf_bracket.parse(os.path.join(here, 'tests', 'jbjjf_bracket_20210924.csv')))
x = [b for b in bb if b['match_no'] == '2'][0]
assert (x['f1'], x['f2'], x['winner'], x['round']) == ('藤原靖典', '長屋英一', '2', '準々決勝'), x
x = [b for b in bb if b['match_no'] == '12'][0]
assert (x['f1'], x['f2'], x['winner'], x['round']) == ('中村圭太', 'Sergey Vedenev', '1', '決勝'), x
assert not [b for b in bb if b['n'] <= 3]
print('JBJJF のトーナメント表の読み取り: 正常')
