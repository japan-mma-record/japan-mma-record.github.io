"""取り込みプログラムが、保存してある本物の公式ページ（tests/）を正しく読めるか確かめる。
公式サイトの作りが変わったときは、新しいページを tests/ に保存し直し、ここの確認も合わせて直す。"""
import os, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
from common import text_lines
import pancrase, deep, shooto, rizin

def read(n): return open(os.path.join(here, 'tests', n), encoding='utf-8', errors='replace').read()

ev, b = pancrase.parse(text_lines(read('pancrase_368.html')), 'x')
assert ev['date'] == '2026-11-08' and ev['name'] == 'PANCRASE 368' and len(b) == 11, (ev, len(b))
assert b[0]['fighter1'] == '菊入正行' and b[0]['winner'] == '1' and b[0]['round'] == '2' and b[0]['time'] == '2:21'
ev, b = deep.parse(text_lines(read('deep_133.html')), 'x')
assert ev['date'] == '2026-09-13' and ev['name'] == 'DEEP 133 IMPACT' and len(b) == 8, (ev, len(b))
assert b[1]['fighter2'] == '新井丈' and b[1]['winner'] == '2' and b[1]['time'] == '1:42'
ev, b = shooto.parse(read('shooto_299.html'), 'x')
assert ev['date'] == '2026-06-28' and len(b) == 10, (ev, len(b))
assert b[0]['winner'] == '2' and b[1]['method'] == '一本（三角絞め）' and b[1]['time'] == '2:19'
ev, b = rizin.parse(read('rizin_53.html'), 'x')
assert ev['date'] == '2026-05-10' and ev['name'] == 'RIZIN.53' and len(b) >= 10, (ev, len(b))
assert b[0]['winner'] == '2' and b[0]['round'] == '1' and b[0]['time'] == '2:08'
print('見本ページの読み取り: すべて正常')
