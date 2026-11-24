# Software Heritage にリポジトリの保存を依頼する
curl -sS -X POST "https://archive.softwareheritage.org/api/1/origin/save/git/url/https://github.com/japan-mma-record/japan-mma-record.github.io/" -o probe/swh.json -w "%{http_code}\n" > probe/swh_code.txt || true
python3 probe/venues2.py
