#!/usr/bin/env bash
#
# Integrate the hardware RTC (DS1307, I2C @ 0x68) into the OS so the system
# clock is correct at boot without a network (the box runs offline).
#
# The board is labelled "DS1302" but the chip is a DS1307 (I2C). It sits at
# address 0x68 (see: sudo i2cdetect -y 1).
#
# This uses the in-kernel rtc-ds1307 driver via the stock i2c-rtc overlay, so
# there is no custom code at runtime: /dev/rtc0 appears at boot and the kernel
# sets the system clock from it (dmesg: "setting system clock to ...").
#
# Read-only root note (overlayroot): /boot/firmware is a *separate* vfat mount
# that is NOT part of the root overlay, so editing config.txt here persists
# without toggling the overlay. hwclock/timedatectl write into the RTC chip
# (battery-backed), not the filesystem, so that persists too. No overlay off/on
# cycle is needed for this change.
#
# Run on the Pi:  sudo bash deploy/rtc/setup-rtc.sh
# Set the time :  sudo bash deploy/rtc/setup-rtc.sh --set-time "2026-07-29 20:17:00"
set -euo pipefail

CONFIG=/boot/firmware/config.txt
OVERLAY_LINE="dtoverlay=i2c-rtc,ds1307"

if [ "${1:-}" = "--set-time" ]; then
  # Write the given local time (Europe/Berlin) into the system clock AND the RTC.
  # timedatectl refuses while NTP is on, so disable it for the moment (offline it
  # does nothing anyway). The kernel stores the RTC in UTC (RTC in local TZ: no).
  when="${2:?Usage: --set-time \"YYYY-MM-DD HH:MM:SS\"}"
  timedatectl set-ntp false
  timedatectl set-time "$when"
  timedatectl set-ntp true
  timedatectl
  exit 0
fi

# 1. I2C bus (idempotent; do_i2c already enabled it on the deployed box).
if ! grep -q '^dtparam=i2c_arm=on' "$CONFIG"; then
  echo 'dtparam=i2c_arm=on' >> "$CONFIG"
  echo "config.txt: I2C aktiviert"
fi

# 2. RTC overlay (idempotent).
if grep -q "^${OVERLAY_LINE}" "$CONFIG"; then
  echo "config.txt: RTC-Overlay bereits eingetragen"
else
  {
    echo ""
    echo "# Hardware-RTC DS1307 (I2C 0x68) - Systemuhr beim Boot ohne Netz"
    echo "$OVERLAY_LINE"
  } >> "$CONFIG"
  echo "config.txt: RTC-Overlay hinzugefuegt"
fi

# 3. Load it now so /dev/rtc0 exists without a reboot.
dtoverlay i2c-rtc ds1307 2>/dev/null || true
sleep 1
if [ -e /dev/rtc0 ]; then
  echo "/dev/rtc0 ist da."
else
  echo "/dev/rtc0 fehlt noch - nach einem Reboot da (Overlay ist eingetragen)."
fi

cat <<'EOF'

Fertig. Uhr einmalig stellen (die RTC war ab Werk angehalten, CH-Bit gesetzt):

  sudo bash deploy/rtc/setup-rtc.sh --set-time "JJJJ-MM-TT HH:MM:SS"

Danach kontrollieren:

  timedatectl        # Zeile "RTC time:" muss stimmen

Mit Netz haelt systemd-timesyncd die Systemuhr und der Kernel schreibt sie
alle ~11 min automatisch in die RTC zurueck. Offline ist die RTC die Quelle.
EOF
