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

## 12. 카카오 연동 (2단계)
- 설계: `docs/superpowers/specs/2026-11-16-watchme-phase2-design.md`. 키가 하나라도 없으면 카카오 기능 전체가 꺼지고 1단계 흐름만 동작.
- 카카오 개발자 콘솔 (사용자가 직접):
  1. `developers.kakao.com/console/app` → 앱 만들기.
  2. [카카오 로그인] > [사용 설정] → 상태 ON (OFF면 KOE004).
  3. [앱] > [플랫폼 키] > [REST API 키] → 카카오 로그인 리다이렉트 URI: `https://evrd.fyi/auth/kakao/callback`, `http://localhost:8000/auth/kakao/callback` (틀리면 KOE006). 호출 허용 IP는 비워 둠.
  4. 같은 화면 [클라이언트 시크릿] → 코드 확인(기본 활성). REST API 키와 이 코드를 `.env`에 넣음.
  5. [앱] > [제품 링크 관리] > [웹 도메인]: `https://evrd.fyi` (메시지 버튼 링크 허용).
  6. [카카오 로그인] > [동의항목] > [접근권한] → "카카오톡 메시지 전송(talk_message)"만 선택 동의. 닉네임 등은 안 씀.
- 서버 `.env` (권한 600, 값은 사용자가 직접 입력):
  - `KAKAO_REST_API_KEY`, `KAKAO_CLIENT_SECRET`
  - `TOKEN_KEY`: 카카오 refresh token 암호화 키(Fernet). 값 출력 없이 생성:
    `cd ~/watchme && grep -q ^TOKEN_KEY= .env || python3 -c "import base64,os;print('TOKEN_KEY='+base64.urlsafe_b64encode(os.urandom(32)).decode())" >> .env`
  - `TOKEN_KEY`는 백업(`pg_dump`)에 들어가지 않는다 → 백업 파일만으로는 토큰을 풀 수 없음. 잃어버리면 저장된 토큰을 못 풀어 사용자가 카톡을 다시 연결해야 함.
- DB: 새 표 `kakao_accounts`, `trial_owners`, `sent_messages`, `next_trials` — 배포 시 `init_db`(`create_all`)가 생성. 기존 표 변경 없음.
- 배포(2026-11-16): main merge 후 `git push evrd main` → healthz OK. 서버 `.env`에 `TOKEN_KEY` 생성(값 출력 없이), 새 표 4개 생성 확인, 기존 `trials` 유지. 카카오 키 입력 전이라 `kakao.enabled()` = False(카카오 경로 404, 버튼 숨김). 리포트 카드 "다음 30일 도전하기" 확인.
- 키 입력 후(2026-11-17): `docker compose up -d`로 app 재생성 → `kakao.enabled()` = True, `/auth/kakao` → 카카오 로그인 화면(KOE 오류 없음).
- 첫 실험 결과(2026-11-17, 폰): 환영 메시지 도착 ✅, 버튼 → 기록 화면 열림 ✅, **폰 알림은 안 울림** ❌ ("나와의 채팅"은 푸시가 없음 — 예상대로). DB: `kakao_accounts` 1건(can_message·notify 켜짐), `trial_owners` 1건, `sent_messages` welcome 1건.
  - 영향: 아침/저녁 메시지도 조용히 쌓임 → 사용자가 카톡을 열어야 봄. 알림이 필요하면 다른 채널(카카오톡 채널 메시지 등, 비즈 앱 필요)을 따로 검토.
- 발송 cron(2026-11-17 등록, KST, 8장 파일 방식으로 기존 3줄 유지):
  - `30 7 * * * cd $HOME/watchme && docker compose exec -T app python -m scripts.send morning >> $HOME/send.log 2>&1`
  - `0 21 * * * cd $HOME/watchme && docker compose exec -T app python -m scripts.send evening >> $HOME/send.log 2>&1`
  - 보낼 게 없으면 아무것도 안 찍음 → `send.log`가 비어 있어도 정상. 첫 발송 결과: `2026-11-17 evening sent=1 failed=0`, `2026-11-18 morning sent=1 failed=0`, 폰 도착 확인 ✅.
- 사용자 피드백 반영(2026-11-18, 6087ce5): 지난 날 기록 화면을 노란 띠·"오늘로 돌아가기"로 표시, 카드·연결 줄·환영 메시지에 "폰 알림은 울리지 않으니 직접 확인" 안내, 다크 모드 끔(`color-scheme: only light`).

## 13. AI 한 줄 요청 (3단계)
- 설계: `docs/superpowers/specs/2026-11-18-watchme-phase3-ai-design.md`. `GEMINI_API_KEY`가 없으면 AI 기능 전체가 꺼지고(설정 6단계 숨김) 1·2단계 흐름 그대로.
- 키 발급 (사용자가 직접):
  1. `aistudio.google.com` → API 키 만들기. **이 앱 전용 키**로 만든다(다른 프로젝트 키 공유 비권장).
  2. 무료 한도는 키가 아니라 구글 프로젝트 단위 → 한도까지 나누려면 구글 프로젝트도 따로. 한도 확인: AI Studio의 rate-limit 화면.
  3. 기본 모델은 `app/ai.py`의 `DEFAULT_MODEL`(`gemini-3.5-flash-lite`, 2026-11-18 모델 문서 기준 안정판 경량 모델). 무료 요금제에서 안 되거나 이름이 바뀌면 `.env`에 `GEMINI_MODEL=모델이름`만 넣고 재시작(코드 수정 불필요).
- 서버 `.env` (값은 사용자가 직접 입력, 출력 금지): `GEMINI_API_KEY` [+ 필요하면 `GEMINI_MODEL`]. 넣은 뒤 `cd ~/watchme && docker compose up -d`(app 재생성).
- 확인(값 출력 없이): `docker compose exec -T app python -c "from app import ai; print(ai.enabled())"` → `True`.
- DB: 새 표 `ai_picks` — 배포 시 `init_db`(`create_all`)가 생성. 기존 표 변경 없음. 보관 삭제(`scripts/purge.py`)가 체험과 함께 지움.
- 실패 확인: `docker compose logs app | grep "ai pick failed"` → 종류만 찍힘(`timeout`·`http`·`invalid`·`floor`). 요청 문장은 로그에 안 남김. `http`가 계속 나오면 키·모델 이름·무료 한도(429) 확인.
- 상태 보기: `docker compose exec -T db psql -U watchme -c "select status, count(*) from ai_picks group by status"`.
- 배포(2026-11-18, `0c88242`): main merge 후 `git push evrd main` → healthz OK, 새 표 `ai_picks` 생성(0건), 기존 `trials` 7건 유지, 시작 화면 개인정보 문장 반영 확인. 키 입력 전이라 `ai.enabled()` = False(설정 6단계 숨김).
- 키 입력 후(2026-11-18): `docker compose up -d` → `ai.enabled()` = True. 기본 모델로 가짜 후보 2개 시험 호출 → 매운 메뉴만 골라 정상.
- 첫 실험 결과(2026-11-18, 폰): 설정 6단계에 매운 음식 요청 → `ai_picks` `ok` 1건(매운 메뉴 1개 제외), 실패 로그 없음. 기록 화면 칩은 서버 HTML에 있음 확인(사용자는 카톡 연결된 11/17 체험을 보고 있었던 것으로 보임).
- 피드백 반영(2026-11-18, `b7688e9`): 준비 화면 AI 안내를 "🤖 이 계획은 AI가 내 요청에 맞춰 골라 줬어요" 한 줄로(뺀 항목 안 보여 줌, 자동 이동 다시 켬), 카톡 카드 "카카오로 연결" 밑에 "바로 시작" 버튼.

## 14. 랜딩 스토리형 개편 + 대표 아이콘 (2026-11-18)
- 설계·계획: `docs/superpowers/specs/2026-11-18-watchme-landing-icon-design.md`, `docs/superpowers/plans/2026-11-18-watchme-landing-icon.md`.
- 아이콘 파일: `app/static/icons/`(favicon.svg, apple-touch-icon 180, icon-192/512, og.png 1200×630). 다시 만들 때 `.venv/Scripts/python scripts/make_icons.py`(Pillow, 개발 PC에서만).
- CSS·JS 주소에 `?v=내용해시`가 붙어 배포 후 폰에 예전 파일이 남지 않음(`ASSET_V`, 서버 시작 때 계산).
- 사용자 몫: 카카오 개발자 콘솔 → 앱 → 앱 아이콘에 `app/static/icons/icon-512.png` 올리기(로그인 동의 화면에 보임).
- 카톡 링크 미리보기가 예전 모습(그림 없음)으로 남으면: 카카오 "카카오톡 URL 메타 정보 관리"(예전 이름 공유 디버거, `https://developers.kakao.com/tool/debugger/sharing`)에서 캐시 초기화. 단 2026-11-18 기준 이 도구는 `https://evrd.fyi/`에 "유효하지 않은 URL" 오류를 냄(카카오 쪽 문제로 보임). 그럴 땐 `og:image` 주소에 `?v=2` 같은 꼬리를 붙여 카카오가 그림을 새로 읽게 한다.
- 확인(2026-11-18): 사용자가 폰 카톡에서 `https://evrd.fyi/` 미리보기(초록 아이콘·제목) 정상 확인.
- 배포(2026-11-18, `40c6d9c`): landing 브랜치 main merge 후 `git push evrd main` → healthz OK. 운영 랜딩 장면 5개(카카오 켜짐), `og:image` = `https://evrd.fyi/static/icons/og.png`, 아이콘·manifest·story.js 200 확인.
