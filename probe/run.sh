cd fetchers && python3 -c "import upcoming; upcoming.run()"
cd ..; for u in 'https://efight.jp/schedule?2027' 'https://efight.jp/schedule?2027&1' 'https://efight.jp/schedule/?2027&01'; do curl -sSL "$u" | grep -o '<h3>20[0-9]*年[0-9]*月' | head -2; echo "-- $u"; done
