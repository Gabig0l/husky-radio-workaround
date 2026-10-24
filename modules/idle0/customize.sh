#!/system/bin/sh
# SPDX-License-Identifier: MIT
# Sourced by Magisk's own installer. It must not change radio settings.
[ "$BOOTMODE" = true ] || abort 'Install from the Magisk app, not recovery.'
[ "$ARCH" = arm64 ] || abort 'This package requires arm64.'
[ "$API" = 37 ] || abort 'This package is restricted to the reviewed Android API 37.'
[ "$MAGISK_VER_CODE" = 31000 ] || abort 'This release is reviewed for Magisk 31.0 only.'
[ "$(id -u)" = 0 ] || abort 'An existing authorized root installation is required.'
[ "$(/system/bin/getprop ro.product.device)" = husky ] || abort 'Wrong device: Pixel 8 Pro / husky only.'
[ "$(/system/bin/getprop ro.build.version.incremental)" = 2026102101 ] || abort 'Unreviewed build. Do not bypass this check or downgrade to use this package.'
[ "$(/system/bin/toybox uname -r)" = 6.1.177-android14-11-gce3dfc2513b1 ] || abort 'Unreviewed kernel. Stop here.'
[ "$(/system/bin/getenforce)" = Enforcing ] || abort 'Keep SELinux Enforcing.'
driver_hash=$(/system/bin/toybox sha256sum /vendor/lib/modules/bcmdhd4398.ko 2>/dev/null) || abort 'Cannot identify the installed DHD driver.'
[ "${driver_hash%% *}" = 66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5 ] || abort 'DHD driver differs from the reviewed build.'
case "$(/system/bin/toybox readlink /sys/devices/platform/13120000.pcie/driver/module)" in
    */pcie_exynos_gs) ;;
    *) abort 'The expected PCIe controller driver is not available.' ;;
esac
IFS= read -r target < /sys/devices/platform/13120000.pcie/link_speed || abort 'Cannot read the PCIe target.'
case "$target" in GEN1|GEN3) ;; *) abort 'Unexpected PCIe interface.' ;; esac

if [ -f "$MODPATH/service.sh" ]; then
    helper_hash=$(/system/bin/toybox sha256sum "$MODPATH/dhd-idle-arm64") || abort 'Helper missing.'
    [ "${helper_hash%% *}" = ae8f165e50eb29e6192211281bd04319132895c7026d78b8e46902782be90f0f ] || abort 'Helper hash mismatch.'
    set_perm "$MODPATH/dhd-idle-arm64" 0 0 700
    set_perm "$MODPATH/service.sh" 0 0 700
    set_perm "$MODPATH/verify.sh" 0 0 700
fi
if [ -f "$MODPATH/post-fs-data.sh" ]; then
    set_perm "$MODPATH/post-fs-data.sh" 0 0 700
fi
set_perm "$MODPATH/module.prop" 0 0 600
ui_print 'Exact device/build/kernel/driver checks passed. No radio change was made by the installer.'
ui_print 'Install BOTH matching packages before rebooting. Keep Wi-Fi enabled if possible.'
ui_print 'Experimental mitigation: previous recurrences exist; read README for checks and rollback.'
