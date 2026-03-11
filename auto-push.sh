#!/bin/bash

WATCH_DIR="$HOME/git"

echo "자동 push 시작: $WATCH_DIR 감시 중..."

inotifywait -m -r -e modify,create,delete,move \
  --exclude '\.git' \
  "$WATCH_DIR" |
while read -r dir event file; do
  echo "변경 감지: $event $dir$file"
  sleep 2  # 연속 변경 대기

  cd "$WATCH_DIR"
  git add -A
  git diff --cached --quiet && continue  # 변경사항 없으면 스킵

  git commit -m "auto: $file ($event) $(date '+%Y-%m-%d %H:%M:%S')"
  git push origin main && echo "push 완료" || echo "push 실패"
done
