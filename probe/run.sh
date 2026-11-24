# IndexNow の鍵ファイルが公開されているか確かめてから、ページ一覧を送る（再試行）
curl -sS "https://japan-mma-record.github.io/63f616b145e0e60848dceccc98b5c78c.txt" -o probe/key.txt -w "%{http_code}\n" > probe/key_code.txt || true
git clone -q --depth 1 https://github.com/japan-mma-record/japan-mma-record.github.io.git /tmp/site && cd /tmp/site && python3 build.py > /dev/null 2>&1; python3 indexnow.py > $GITHUB_WORKSPACE/probe/indexnow.txt 2>&1 || true
