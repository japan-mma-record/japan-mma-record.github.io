#!/usr/bin/env python3
"""各団体の公式サイトから新しい大会の結果と、今後の大会予定を取り込む（毎日自動で実行されます）。
一つの団体で失敗しても、ほかの団体の取り込みは続けます。
使い方:  python3 fetch.py
"""
import os, sys, traceback, importlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fetchers'))
SOURCES = ['pancrase', 'deep', 'shooto', 'rizin', 'grachan', 'wardog']   # 取り込み元を増やすときは fetchers/ にファイルを足してここに名前を書く

total, failed = 0, []
for name in SOURCES:
    try:
        n = importlib.import_module(name).run()
        total += n or 0
    except Exception:
        failed.append(name)
        print(f'[{name}] 取り込みに失敗しました。サイトの形が変わった可能性があります。')
        traceback.print_exc()
print(f'新しく取り込んだ大会: {total}')
# 今後の大会予定（data/upcoming.json）も新しくする
try:
    importlib.import_module('upcoming').run()
except Exception:
    failed.append('upcoming')
    print('[予定] 今後の予定の更新に失敗しました（前回の予定はそのまま残ります）。')
    traceback.print_exc()
if failed:
    print('失敗した取り込み元: ' + ', '.join(failed))
