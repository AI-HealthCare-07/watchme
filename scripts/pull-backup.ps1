# 개발 PC에서 실행: 서버의 최신 DB 백업을 가져와 30개까지 보관 (서버 밖 사본).
# 작업 스케줄러에서 로그온 시 + 매일 실행. 서버 접속은 ~/.ssh/config의 evrd(Tailscale).
$ErrorActionPreference = 'Stop'
$dir = Join-Path $env:USERPROFILE 'Backups\watchme'
New-Item -ItemType Directory -Force $dir | Out-Null
$out = Join-Path $dir ("watchme-{0:yyyyMMdd-HHmm}.sql.gz" -f (Get-Date))
scp -q -o BatchMode=yes evrd:backups/latest.sql.gz $out
if ($LASTEXITCODE -ne 0) { throw "scp failed ($LASTEXITCODE)" }
Get-ChildItem $dir -Filter 'watchme-*.sql.gz' | Sort-Object Name -Descending | Select-Object -Skip 30 | Remove-Item
"{0:yyyy-MM-dd HH:mm} ok {1}" -f (Get-Date), $out | Add-Content (Join-Path $dir 'pull.log')
