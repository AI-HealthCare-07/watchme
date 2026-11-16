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
