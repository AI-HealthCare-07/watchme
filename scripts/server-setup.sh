#!/usr/bin/env bash
# evrd 서버 초기 설정 (Task 2 Step 1-5). 여러 번 실행해도 안전하도록 작성.
# 실행: ssh -t evrd "sudo bash ~/server-setup.sh"
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "sudo로 실행하세요"; exit 1; }
step() { echo; echo "=== $* ==="; }

step "1. SSH: 키 로그인만 허용"
cat > /etc/ssh/sshd_config.d/10-hardening.conf <<'EOF'
# sshd는 처음 읽은 값을 쓰므로 10-이 설치기의 50-cloud-init.conf보다 우선
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin no
EOF
sshd -t
systemctl reload ssh
sshd -T | grep -E '^(passwordauthentication|permitrootlogin)'

step "2. 방화벽(ufw): 들어오는 연결 기본 차단, SSH만 허용"
# ponytail: Tailscale 연결 후 SSH를 tailscale0으로만 좁힐 예정 (Task 2 Step 4)
ufw allow OpenSSH >/dev/null
ufw default deny incoming >/dev/null
ufw default allow outgoing >/dev/null
ufw --force enable
ufw status verbose | head -8

step "3. 덮개 닫아도 계속 동작"
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/lid.conf <<'EOF'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
EOF
systemctl kill -s HUP systemd-logind

step "4. 배터리 보호 모드(약 60%에서 충전 중지)"
CM=/sys/bus/platform/drivers/ideapad_acpi/VPC2004:00/conservation_mode
if [ -w "$CM" ]; then
  echo 1 > "$CM"
  echo "w $CM - - - - 1" > /etc/tmpfiles.d/battery-conservation.conf
  echo "conservation_mode=$(cat "$CM")"
else
  echo "경고: $CM 없음 → 충전 제한 미적용"
fi

step "5. Wi-Fi 절전 끄기 (지연·끊김 방지)"
cat > /etc/systemd/system/wifi-powersave-off.service <<'EOF'
[Unit]
Description=Disable Wi-Fi power saving on wlp2s0
After=sys-subsystem-net-devices-wlp2s0.device
Wants=sys-subsystem-net-devices-wlp2s0.device

[Service]
Type=oneshot
ExecStart=/usr/sbin/iw dev wlp2s0 set power_save off

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now wifi-powersave-off.service
iw dev wlp2s0 get power_save

step "6. 설치 때 쓴 USB 테더링 네트워크 설정 정리"
# 테더링 장치를 기다리느라 부팅이 최대 2분 늦어지는 것을 막음
if [ -f /etc/netplan/00-installer-config.yaml ] && ! grep -q wlp2s0 /etc/netplan/00-installer-config.yaml; then
  mkdir -p /root/netplan-backup
  mv /etc/netplan/00-installer-config.yaml /root/netplan-backup/
  netplan generate
  echo "00-installer-config.yaml → /root/netplan-backup/ 로 이동"
else
  echo "건너뜀"
fi

step "7. 시간대 Asia/Seoul"
timedatectl set-timezone Asia/Seoul
date

step "8. 시스템 업데이트"
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get -y -q upgrade
apt-get -y -q install ca-certificates curl unattended-upgrades

step "9. Docker (공식 저장소)"
if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -q
  apt-get -y -q install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi
usermod -aG docker "${SUDO_USER:-koo}"
docker --version
docker compose version

step "10. Tailscale 설치 (로그인은 다음 단계에서)"
if ! command -v tailscale >/dev/null; then
  curl -fsSL https://tailscale.com/install.sh | sh
fi
tailscale version | head -1

echo; echo "ALL-DONE"
