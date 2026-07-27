"""Small system helpers for the admin area (CPU temperature, uptime, shutdown).

These touch the OS, not the camera/printer protocols, so they live outside
``hardware/``. All are best-effort: on a dev box without a Pi thermal zone they
return ``None`` rather than failing.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

_THERMAL = Path("/sys/class/thermal/thermal_zone0/temp")

# NetworkManager connection profile used for the guest access point (M7b). It is
# created with autoconnect=no so a reboot always returns to the normal WiFi — the
# safety net if the AP ever locks us out of the box.
_AP_CON = "fotobox-ap"

# Where a USB stick is mounted for an event export (auto-mount is disabled on the
# kiosk, so the backend mounts it itself).
_EXPORT_MOUNT = Path("/media/fotobox-export")


def cpu_temp() -> float | None:
    try:
        return round(int(_THERMAL.read_text()) / 1000.0, 1)
    except Exception:
        return None


def uptime_seconds() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text().split()[0])
    except Exception:
        return None


def versions() -> dict:
    return {"python": sys.version.split()[0]}


def poweroff() -> None:
    """Clean shutdown (Pi). Requires passwordless sudo (configured on the box)."""
    subprocess.Popen(["sudo", "systemctl", "poweroff"])


def reboot() -> None:
    """Clean reboot (Pi). Requires passwordless sudo (configured on the box)."""
    subprocess.Popen(["sudo", "systemctl", "reboot"])


# --- network / access point (M7b) -------------------------------------------
#
# The box runs NetworkManager (Raspberry Pi OS / Trixie). The guest access point
# is an NM connection in AP mode with ipv4.method=shared, so NM runs its own
# DHCP+DNS and hands guests an address on the configured subnet — no hostapd or
# dnsmasq to wire up by hand. Bringing the AP up on wlan0 drops the normal WiFi;
# that is expected (the box is used at the touchscreen, not over SSH).


def primary_ip() -> str | None:
    """The box's current primary IPv4 address, best-effort."""
    try:
        out = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=5)
        parts = out.stdout.split()
        return parts[0] if parts else None
    except Exception:
        return None


def ap_active() -> bool:
    """True if the Fotobox access-point profile is currently active."""
    try:
        out = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return _AP_CON in out.stdout.split()
    except Exception:
        return False


def ap_enable(ssid: str, passphrase: str, channel: int, address: str) -> None:
    """(Re)create and activate the guest access point on wlan0."""
    # Recreate the profile from scratch so config changes always take effect.
    subprocess.run(
        ["sudo", "nmcli", "connection", "delete", _AP_CON],
        capture_output=True,
        timeout=10,
    )
    subprocess.run(
        [
            "sudo",
            "nmcli",
            "connection",
            "add",
            "type",
            "wifi",
            "ifname",
            "wlan0",
            "con-name",
            _AP_CON,
            "autoconnect",
            "no",
            "ssid",
            ssid,
            "802-11-wireless.mode",
            "ap",
            "802-11-wireless.band",
            "bg",
            "802-11-wireless.channel",
            str(channel),
            "ipv4.method",
            "shared",
            "ipv4.addresses",
            f"{address}/24",
        ],
        check=True,
        capture_output=True,
        timeout=20,
    )
    if passphrase:
        subprocess.run(
            [
                "sudo",
                "nmcli",
                "connection",
                "modify",
                _AP_CON,
                "802-11-wireless-security.key-mgmt",
                "wpa-psk",
                "802-11-wireless-security.psk",
                passphrase,
            ],
            check=True,
            capture_output=True,
            timeout=15,
        )
    subprocess.run(
        ["sudo", "nmcli", "connection", "up", _AP_CON],
        check=True,
        capture_output=True,
        timeout=30,
    )


def ap_disable() -> None:
    """Bring the access point down; NM auto-reconnects the normal WiFi."""
    subprocess.run(
        ["sudo", "nmcli", "connection", "down", _AP_CON],
        capture_output=True,
        timeout=30,
    )


# --- USB export (M7b) -------------------------------------------------------


def find_usb_storage() -> dict | None:
    """First writable USB partition, as ``{device, fstype, size}`` — or None."""
    try:
        out = subprocess.run(
            ["lsblk", "-J", "-o", "NAME,PATH,TYPE,TRAN,FSTYPE,SIZE"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        data = json.loads(out.stdout)
    except Exception:
        return None
    for disk in data.get("blockdevices", []):
        if disk.get("tran") != "usb":
            continue
        for part in disk.get("children") or []:
            if part.get("fstype"):
                return {
                    "device": part["path"],
                    "fstype": part["fstype"],
                    "size": part.get("size"),
                }
        if disk.get("fstype"):  # unpartitioned stick
            return {
                "device": disk["path"],
                "fstype": disk["fstype"],
                "size": disk.get("size"),
            }
    return None


def mount_usb(device: str, fstype: str) -> Path:
    """Mount a USB partition writable for us and return the mount point."""
    subprocess.run(["sudo", "mkdir", "-p", str(_EXPORT_MOUNT)], check=True, timeout=10)
    fat_like = fstype in ("vfat", "msdos", "exfat", "ntfs")
    opts = ["-o", f"uid={os.getuid()},gid={os.getgid()},umask=0022"] if fat_like else []
    subprocess.run(
        ["sudo", "mount", *opts, device, str(_EXPORT_MOUNT)],
        check=True,
        capture_output=True,
        timeout=25,
    )
    if not fat_like:  # POSIX fs: make the mount writable for the service user
        subprocess.run(
            ["sudo", "chown", f"{os.getuid()}:{os.getgid()}", str(_EXPORT_MOUNT)],
            capture_output=True,
            timeout=10,
        )
    return _EXPORT_MOUNT


def unmount_usb() -> None:
    """Flush and unmount the export stick (best-effort)."""
    subprocess.run(["sync"], timeout=30)
    subprocess.run(["sudo", "umount", str(_EXPORT_MOUNT)], capture_output=True, timeout=30)
