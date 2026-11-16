#!/usr/bin/env bash
# 매일 DB 덤프를 ~/backups/에 남기고 7일 지난 것은 지운다.
# cron(koo): 0 4 * * * $HOME/watchme/scripts/backup.sh >> $HOME/backups/backup.log 2>&1
# 서버 밖 사본은 개발 PC가 가져간다(pull): scripts/pull-backup.ps1
# ponytail: 서버 밖 사본은 개발 PC가 켜져 있을 때만 생김. 상시 보관이 필요하면 rclone으로 클라우드 저장소에 올리기
set -euo pipefail
DIR="$HOME/backups"
mkdir -p "$DIR"
OUT="$DIR/watchme-$(date +%Y%m%d-%H%M).sql.gz"
cd "$HOME/watchme"
docker compose exec -T db pg_dump -U watchme --clean --if-exists watchme | gzip > "$OUT.tmp"
mv "$OUT.tmp" "$OUT"
ln -sf "$(basename "$OUT")" "$DIR/latest.sql.gz"
find "$DIR" -name 'watchme-*.sql.gz' -mtime +7 -delete
echo "$(date '+%F %T') ok $(du -h "$OUT" | cut -f1) $OUT"
