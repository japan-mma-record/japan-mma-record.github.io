"""取り込みプログラムが保存済みの見本ページを正しく読めるか確かめる。"""
import os, sys
here = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, here)
import pancrase, deep

def read(n): return open(os.path.join(here, 'tests', n), encoding='utf-8').read().split('\n')

ev, b = pancrase.parse(read('pancrase_368.txt'), 'x')
assert ev['date'] == '2026-11-08' and ev['name'] == 'PANCRASE 368' and len(b) == 5, (ev, len(b))
assert b[0]['fighter1'] == '菊入正行' and b[0]['winner'] == '1' and b[0]['round'] == '2' and b[0]['time'] == '2:21'
assert b[1]['winner'] == '2'
ev, b = deep.parse(read('deep_133.txt'), 'x')
assert ev['date'] == '2026-09-13' and len(b) == 6, (ev, len(b))
assert b[1]['fighter2'] == '新井丈' and b[1]['winner'] == '2' and b[1]['time'] == '1:42'
print('見本ページの読み取り: すべて正常')
