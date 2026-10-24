#!/system/bin/sh
# SPDX-License-Identifier: MIT
# Run once in Magisk's early stage. No waits, radio toggles or driver resets.
MODDIR=${0%/*}
[ "$MODDIR" = /data/adb/modules/codex_wifi_gen1_husky ] || exit 0
[ -d "$MODDIR" ] && [ ! -L "$MODDIR" ] || exit 0
LOG="$MODDIR/last-boot.log"
[ ! -L "$LOG" ] || exit 0
[ ! -e "$LOG" ] || [ -f "$LOG" ] || exit 0
[ "$(id -u)" = 0 ] || { echo 'skipped=not_root'; exit 0; }
[ "$(/system/bin/getprop ro.product.device)" = husky ] || { echo 'skipped=wrong_device'; exit 0; }
[ "$(/system/bin/getprop ro.build.version.incremental)" = 2026102101 ] || { echo 'skipped=build_changed'; exit 0; }
[ "$(/system/bin/toybox uname -r)" = 6.1.177-android14-11-gce3dfc2513b1 ] || { echo 'skipped=kernel_changed'; exit 0; }
controller=/sys/devices/platform/13120000.pcie
case "$(readlink "$controller/driver/module")" in
  */pcie_exynos_gs) ;;
  *) echo 'skipped=unexpected_driver'; exit 0 ;;
esac
target="$controller/link_speed"
[ -r "$target" ] && [ -w "$target" ] || { echo 'skipped=target_unavailable'; exit 0; }
before=$(cat "$target")
case "$before" in
  GEN1|GEN3) ;;
  *) echo 'skipped=unexpected_target'; exit 0 ;;
esac
exec > "$LOG" 2>&1
printf 'phase=post-fs-data\n'
printf 'boot_id='; cat /proc/sys/kernel/random/boot_id
printf 'uptime_before='; cat /proc/uptime
printf 'target_before=%s\n' "$before"
if printf '1\n' > "$target"; then
  after=$(cat "$target")
  printf 'target_after=%s\n' "$after"
  [ "$after" = GEN1 ] && echo 'result=applied' || echo 'result=verification_failed'
else
  echo 'result=write_failed'
fi
printf 'uptime_after='; cat /proc/uptime
