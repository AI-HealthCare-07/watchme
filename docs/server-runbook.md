# 집 서버 Runbook

실제로 수행한 명령과 결과를 단계마다 기록한다. 서버를 다시 만들 때 이 문서만 보고 따라 할 수 있어야 한다.

## 하드웨어
- Lenovo IdeaPad S340-14API (AMD Ryzen 3000 계열 APU)
- 유선 LAN 포트 없음 → Wi-Fi 또는 USB-LAN 어댑터
- CPU Ryzen 5 3500U, RAM 8GB, NVMe SSD 256GB, BIOS AMCN27WW(V1.10)

## 1. BIOS
- 진입: 전원 끈 상태에서 측면 Novo 버튼(작은 구멍)을 클립으로 누름 → BIOS Setup. 또는 부팅 중 F2(필요 시 Fn+F2). 부팅 메뉴는 F12.
- 충전 제한: BIOS 항목 없음 → Ubuntu에서 `ideapad_laptop` 드라이버의 conservation mode로 설정 (5장 참고).
- 정전 후 자동 켜짐: IdeaPad BIOS에 없음(확인 후 기록). 배터리가 UPS 역할을 하므로 짧은 정전은 영향 없음.
- Secure Boot: 켠 상태 유지 (Ubuntu 지원).
- 확인 결과(2026-11-16): BIOS에 충전 제한·AC 복귀 항목 없음. Secure Boot 항목은 Boot Mode가 Legacy Support일 때 보이지 않음.
- 변경:
  - Boot > Boot Mode: Legacy Support → **UEFI** (그 뒤 Security에 Secure Boot가 나타나면 Enabled 유지)
  - Boot > PXE Boot to LAN: **Disabled** (LAN 포트 없음, 부팅 지연 방지)
  - Boot > Fast Boot: **Disabled** (USB 인식 안정)
  - 그 외 기본값 유지 (AMD SVM Enabled: 가상화용으로 유지)
  - Exit > Exit Saving Changes

## 2. Ubuntu Server 설치 (2026-11-16)
- Ubuntu Server 26.04.1 LTS, Rufus(MBR, BIOS 또는 UEFI)로 USB 생성.
- 서버 이름 `evrd`, 사용자 `koo`. LVM 사용, LUKS 암호화 안 함(무인 재부팅 위해). `ubuntu-lv`를 100G → 235.421G(최대)로 수동 확장.
- OpenSSH 설치 + 비밀번호 로그인 일시 허용(키 등록 후 차단 예정). snap 없음.
- 문제: 설치 화면에서 Wi-Fi가 `Applying changes`에서 멈춤.
  - 원인 1: 공유기 라벨의 2.4GHz 이름 `<Wi-Fi 이름 2.4GHz>`이 실제로는 송출되지 않음(스캔에 없음).
  - 원인 2: 5GHz 시도가 실패한 뒤 설치기 네트워크 적용이 멈춰 다른 장치도 대기.
  - 해결: 처음부터 다시 부팅 + 휴대폰 USB 테더링, 미러 테스트 실패 → 오프라인 설치. 설치된 시스템에 `wpasupplicant`는 포함되어 있었음.

## 3. Wi-Fi (설치 후)
- `sudo apt install -y iw` 후 `sudo iw dev wlp2s0 scan | grep -E "freq:|SSID:"`로 실제 송출 이름 확인 → 실제 연결은 `<Wi-Fi 이름>`(5GHz, KT 공유기 직결). 개발 PC는 그 아래 `<집 공유기>5` 공유기(192.168.0.x).
- `/etc/netplan/60-wifi.yaml` (권한 600, 들여쓰기 스페이스 2칸):
  ```yaml
  network:
    version: 2
    wifis:
      wlp2s0:
        dhcp4: true
        access-points:
          "<Wi-Fi 이름>":
            password: "<비밀번호>"
  ```
- `sudo netplan apply` → `wlp2s0` UP, `<LAN IP>/24`.
- 네트워크: 인터넷 ─ KT 공유기(<LAN IP>) ─┬ 서버 evrd(<LAN IP>)
                                        └ <집 공유기> 공유기(192.168.0.x) ─ 개발 PC. 포트포워딩은 KT 공유기 한 곳만 하면 됨.
- ping 지연 90–300ms → Wi-Fi 절전(power_save on)이 원인. 끈 뒤 3–5ms.

## 4. SSH 키 + 초기 설정 (2026-11-16)
- 개발 PC: `ssh-keygen -t ed25519` → `~/.ssh/config`에 `Host evrd` 별칭. 공개키는 `Get-Content id_ed25519.pub | ssh evrd "umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys"`로 등록(비밀번호 입력 대기 2분 넘기면 서버가 연결을 끊음 → 다시 실행).
- `scripts/server-setup.sh`를 `scp`로 올리고 `ssh -t evrd "sudo bash ~/server-setup.sh"` 실행(sudo 비밀번호 1회).
  - SSH 비밀번호 로그인 차단(`/etc/ssh/sshd_config.d/10-hardening.conf`), ufw 활성(SSH만 허용), 덮개 무시, 배터리 conservation_mode=1(tmpfiles로 부팅 시 유지), Wi-Fi 절전 off(systemd 서비스), 테더링 netplan 정리, 시간대 KST, 업데이트, Docker 29.9, Tailscale 1.104.
- 검증: 비밀번호 로그인 시도 → `Permission denied (publickey)`, ping 4ms, `power_save off`, docker 그룹 포함.

## 5. 재부팅 검증 (2026-11-16)
- 재부팅 후 IP가 DHCP로 `<LAN IP>` → `<LAN IP>`로 바뀜 → `~/.ssh/config`의 HostName 수정. 근본 해결은 Tailscale(이름으로 접속).
- 유지 확인: conservation_mode=1, power_save off, ufw/tailscaled/docker active, 부팅 19.7초, reboot-required 없음.
- 참고: Ubuntu 26.04는 `ssh.socket`이 22번을 듣고 `ssh.service`는 접속 시에만 뜸(inactive가 정상).

## 6. Tailscale + 배포 (2026-11-16)
- 서버 `sudo tailscale up` → 브라우저 로그인. tailnet `<tailnet>.ts.net`, 서버 `evrd` = `<Tailscale IP>`, 개발 PC `<개발 PC>`.
- `~/.ssh/config`의 `Host evrd` HostName → `evrd.<tailnet>.ts.net` (IP가 바뀌어도, 외부에서도 접속).
- 방화벽: `ufw allow in on tailscale0` + `ufw delete allow OpenSSH` → SSH는 Tailscale에서만. `tailscale set --operator=koo`로 sudo 없이 tailscale 조작.
- 배포(push-to-deploy): 서버에 `~/watchme.git`(bare) + `scripts/post-receive` 훅. 개발 PC에서 `git push evrd phase1` → `~/watchme`에 체크아웃 → `docker compose up -d --build` → healthz 출력.
  - 서버 `.env`(권한 600)는 git에 없음: 무작위 `POSTGRES_PASSWORD`, `PUBLIC_BASE_URL=https://evrd.<tailnet>.ts.net`.

## 7. Funnel 공개 + 방문자 IP 확인 (2026-11-16)
- `tailscale funnel --bg 8000` → 처음엔 "Funnel is not enabled" + 허용 링크 → 관리 콘솔에서 Enable(HTTPS 인증서 + ACL funnel 속성) → `https://evrd.<tailnet>.ts.net` 공개. 휴대폰 LTE에서 `/healthz` = `{"ok":true}` 확인.
- 외부(공개 DNS 8.8.8.8)에서 보이는 Funnel 주소: 103.84.155.217 / .153 (Tailscale 중계, 집 IP 노출 없음).
- 방문자 IP: `request.client.host`는 Docker 브리지(172.18.0.1)라 쓸모없음. Funnel이 `X-Forwarded-For`에 실제 공인 IP를 **덮어써서** 넣음(가짜 XFF를 보내도 실제 IP로 대체됨 확인). 추가로 `Tailscale-Funnel-Request: ?1` 헤더가 붙음.
  → 요청 제한의 `client_ip()`는 `X-Forwarded-For` 값을 사용, 없으면(서버 내부 curl 등) `client.host`.

## 8. 백업 (2026-11-16)
- 서버: `scripts/backup.sh`(배포 시 함께 올라감)가 `pg_dump | gzip` → `~/backups/watchme-YYYYMMDD-HHMM.sql.gz`(권한 600), `latest.sql.gz` 링크, 7일 초과 삭제.
- cron(koo, KST): `0 4 * * * $HOME/watchme/scripts/backup.sh >> $HOME/backups/backup.log 2>&1`
  - 주의: `(crontab -l; echo ...) | crontab -`가 26.04에서 조용히 빈 crontab을 남김 → 파일로 만들어 `crontab /tmp/ct`로 등록.
- 복원 검증: 표본 테이블 3행 → 덤프 → 빈 DB `restore_test`에 복원 → 3행 일치, 정리함.
- 서버 밖 사본: 개발 PC가 `scripts/pull-backup.ps1`로 `scp evrd:backups/latest.sql.gz` → `%USERPROFILE%\Backups\watchme\`(30개 보관). 수동 실행 확인. Windows 작업 스케줄러 "Watchme pull backup"(로그온 시 + 매일 12:00, 놓치면 가능할 때 실행) 등록, 첫 실행 결과 0.

## 9. evrd.fyi 직접 연결: 포트포워딩 + Caddy + DDNS (2026-11-16)
- 회선: KT 공유기 <공유기 모델>(GiGA WiFi home), WAN DHCP 공인 IP `<집 공인 IP>` (CGNAT 아님: 공유기 WAN IP = 서버에서 본 공인 IP).
- 공유기 (관리 페이지 `http://<LAN IP>`):
  - 장치설정 → 네트워크 관리 → LAN 연결 설정 → 수동 IP 할당: `<MAC>` → `<LAN IP>`
  - 장치설정 → 트래픽 관리 → 포트 포워딩: TCP 80→<LAN IP>:80, TCP 443→<LAN IP>:443 (소스 IP·포트 비움). DMZ·UPnP 안 씀.
  - KT는 80/443을 막지 않음 (LTE 폰에서 nginx 테스트 페이지로 확인).
- Caddy (`compose.yaml`의 `caddy`, `Caddyfile`): `${LAN_IP}:80/443`에만 바인딩. 0.0.0.0:443은 Tailscale Funnel(tailscale0:443)과 충돌하므로. 인증서는 Let's Encrypt HTTP-01 자동 발급·갱신(볼륨 `caddy_data`). 접근 로그 끔.
- 방문자 IP: Caddy는 들어온 X-Forwarded-For를 버리고 실제 IP로 덮어씀 → `client_ip`(첫 값) 그대로. 위조 XFF 6회 → 6번째 429로 확인. Funnel 경로도 계속 동작.
- DNS (Porkbun): `evrd.fyi` A → 공인 IP, TTL 600. Vercel A·www CNAME 삭제. google-site-verification TXT는 유지.
- DDNS: `ddns/update.py` (표준 라이브러리, 호스트 python3), cron 5분마다, 바뀔 때만 `~/ddns.log`에 기록. 키는 서버 `.env`의 `PORKBUN_API_KEY`/`PORKBUN_SECRET_KEY` (사용자가 직접 입력, 600). 도메인 API Access 켜야 동작.
- `.env`: `LAN_IP=<LAN IP>`, `PUBLIC_BASE_URL=https://evrd.fyi` (QR·링크).
- 문제 시: `docker compose logs caddy` (인증서), `dig +short evrd.fyi @1.1.1.1` (DNS), `cat ~/ddns.log`. 서버 IP가 바뀌면 공유기 할당과 `.env`의 LAN_IP를 같이 확인.

## 10. 보관 기간 삭제 (2026-11-16)
- 시작 화면 안내("체험 종료 후 90일")대로, 시작 후 120일(체험 30일 + 90일)이 지난 체험과 기록을 매일 04:30 삭제 (`scripts/purge.py` → `service.purge_expired`). 사용자 승인 후 cron 등록.
- cron: `30 4 * * * cd $HOME/watchme && docker compose exec -T app python -m scripts.purge >> $HOME/purge.log 2>&1` (지운 게 있을 때만 기록).
- 백업에는 서버 최대 7일, PC 최대 30일 더 남았다가 사라짐.

## 11. 리디자인 배포 (2026-11-16)
- 내용: 초록 디자인 체계(`app/static/app.css`, `flow.js`), 토스식 입력 → 결과 → 맞춤 5문항, 맞춤 30일 계획(`app/plan.py` + `app/data/{meals,exercises,tips}.json`), 정체 감지·강도 질문(`app/progress.py`, 표 `week_decisions`), 주간 PDF(`/c/<token>/week/<n>.pdf`, `plan.pdf`는 이번 주로 이동), Pretendard 자체 호스팅(`app/static/fonts`, OFL).
- DB: `trials`에 맞춤 답변 컬럼이 생겨 `create_all`로는 못 바꾸므로, 사용자 승인 후 운영 `trials`(2건)·`day_logs`(30건)를 `DROP TABLE` → 배포 시 `init_db`가 새 표 3개 생성. 지운 데이터는 그날 백업(`~/backups/watchme-20261116-1259.sql.gz`)에 남음.
- 배포 후: 데모 시드 `docker compose exec -T app python -m scripts.seed_demo` → 리포트 URL 200. `/`, `/start`, 기록·리포트·주간 PDF·CSS·글꼴 200, 외부 src/href 없음 확인.
- 다음에 표 구조를 또 바꾸면: 지금은 마이그레이션 도구가 없으니 같은 방식(승인 → 백업 확인 → DROP → 배포)이거나 Alembic 도입.
