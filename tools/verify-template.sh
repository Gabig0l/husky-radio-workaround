#!/system/bin/sh
# SPDX-License-Identifier: MIT
# Read-only radio checks. Does not enable radios, write iovars or reset drivers.
MODDIR=${0%/*}
[ "$MODDIR" = /data/adb/modules/wifi_dhd_idle0 ] || exit 1
[ -d "$MODDIR" ] && [ ! -L "$MODDIR" ] || exit 1
[ "$(id -u)" = 0 ] || { echo 'Existing root is required.'; exit 1; }
[ "$(/system/bin/getprop ro.product.device)" = husky ] || exit 1
[ "$(/system/bin/getprop ro.build.version.incremental)" = 2026102101 ] || exit 1
[ "$(/system/bin/toybox uname -r)" = 6.1.177-android14-11-gce3dfc2513b1 ] || exit 1
hash=$(/system/bin/toybox sha256sum /vendor/lib/modules/bcmdhd4398.ko) || exit 1
[ "${hash%% *}" = 66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5 ] || exit 1
hash=$(/system/bin/toybox sha256sum "$MODDIR/dhd-idle-arm64") || exit 1
[ "${hash%% *}" = @HELPER_SHA256@ ] || exit 1
IFS= read -r target < /sys/devices/platform/13120000.pcie/link_speed || exit 1
printf 'pcie_target=%s\n' "$target"
printf 'pcie_negotiated='; cat /sys/bus/pci/devices/0001:01:00.0/current_link_speed || exit 1
[ "$target" = GEN1 ] || { echo 'FAIL: target is not GEN1.'; exit 1; }
IFS= read -r flags < /sys/class/net/wlan0/flags || exit 1
case "$flags" in 0x*) flags_hex=${flags#0x} ;; *) exit 1 ;; esac
case "$flags_hex" in ''|*[!0-9a-fA-F]*) exit 1 ;; esac
[ "${#flags_hex}" -le 8 ] && [ "$((flags & 1))" -ne 0 ] || { echo 'Wi-Fi interface is down; no DHD call made.'; exit 1; }
OUT="$MODDIR/verify-last.txt"
[ ! -L "$OUT" ] && { [ ! -e "$OUT" ] || [ -f "$OUT" ]; } || exit 1
umask 077
"$MODDIR/dhd-idle-arm64" inspect > "$OUT" 2>&1 &
PID=$!
trap 'kill -KILL "$PID" 2>/dev/null; exit 1' 1 2 15
for attempt in 1 2 3; do
    /system/bin/toybox sleep 1 || break
    if ! kill -0 "$PID" 2>/dev/null; then
        wait "$PID"
        result=$?
        cat "$OUT"
        [ "$result" = 0 ] || exit 1
        /system/bin/toybox grep -qx 'idletime_before=0' "$OUT" || exit 1
        echo 'PASS: GEN1 target and healthy DHD GET reporting idletime=0. This is not a stability test.'
        exit 0
    fi
done
kill -KILL "$PID" 2>/dev/null || :
echo 'UNCONFIRMED: DHD inspection timed out; a stuck kernel ioctl may survive. No SET was attempted.'
exit 1
