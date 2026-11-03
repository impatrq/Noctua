#!/bin/bash
# One-shot installer for the Pi camera recorder.
# Put cam_server.py and setup.sh in the same folder on the Pi, then run:
#   sudo bash setup.sh
set -e

if [ "$EUID" -ne 0 ]; then
  echo "Run with: sudo bash setup.sh"
  exit 1
fi

USER_NAME="${SUDO_USER:-nyctus}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SRC_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "== Installing packages =="
apt update
apt install -y python3-flask python3-requests ffmpeg rpicam-apps network-manager

echo "== Installing script =="
if [ ! "$SRC_DIR/cam_server.py" -ef "$HOME_DIR/cam_server.py" ]; then
  install -m 755 "$SRC_DIR/cam_server.py" "$HOME_DIR/cam_server.py"
fi
chmod 755 "$HOME_DIR/cam_server.py"
mkdir -p "$HOME_DIR/videos"
chown "$USER_NAME":"$USER_NAME" "$HOME_DIR/cam_server.py" "$HOME_DIR/videos"

echo
read -r -p "Wi-Fi country code, 2 letters, e.g. US (blank to skip): " CC
if [ -n "$CC" ]; then
  raspi-config nonint do_wifi_country "$CC" || true
fi

echo
read -r -p "Wi-Fi name to join (blank to skip): " WIFI_SSID
if [ -n "$WIFI_SSID" ]; then
  read -r -s -p "Wi-Fi password: " WIFI_PASS
  echo
  nmcli connection delete "$WIFI_SSID" >/dev/null 2>&1 || true
  nmcli connection add type wifi ifname wlan0 con-name "$WIFI_SSID" \
    ssid "$WIFI_SSID" wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$WIFI_PASS" \
    connection.autoconnect yes
fi

echo
read -r -p "Hotspot password, 8+ characters [picam1234]: " HP
HP="${HP:-picam1234}"
if [ "${#HP}" -lt 8 ]; then
  echo "Hotspot password must be at least 8 characters."
  exit 1
fi

echo
read -r -p "NYCTUS Render API URL, e.g. https://nyctus-api.onrender.com (blank to keep manual Start/Stop only, no auto-polling): " RENDER_URL
RENDER_URL="${RENDER_URL%/}"

echo "== Creating service =="
cat > /etc/systemd/system/camera.service << SERVICE
[Unit]
Description=Pi camera recorder and web control
After=multi-user.target

[Service]
WorkingDirectory=$HOME_DIR
Environment="HOTSPOT_PASS=$HP"
Environment="VIDEO_DIR=$HOME_DIR/videos"
Environment="RENDER_API_URL=$RENDER_URL"
ExecStart=/usr/bin/python3 $HOME_DIR/cam_server.py
Restart=always

[Install]
WantedBy=multi-user.target
SERVICE

systemctl daemon-reload
systemctl enable camera
systemctl restart camera

echo
echo "Done. After boot the Pi joins a saved Wi-Fi, or starts the hotspot:"
echo "  Hotspot name: PiCam   password: $HP   page: http://10.42.0.1"
echo "  On a normal network:  http://$(hostname).local"
if [ -n "$RENDER_URL" ]; then
  echo "  NYCTUS auto-polling:  $RENDER_URL/pendientes (every 5s)"
else
  echo "  NYCTUS auto-polling:  disabled (no Render URL given)"
fi
echo "Check status with: systemctl status camera"
