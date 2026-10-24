#!/system/bin/sh
# SPDX-License-Identifier: MIT
# Active candidate for a separate Magisk late_start module.
# Outside the exact intended module path, exit before guards or device access.
MODDIR=${0%/*}
[ "$MODDIR" = /data/adb/modules/wifi_dhd_idle0 ] || exit 0
[ ! -L "$MODDIR" ] || exit 0

HELPER="$MODDIR/dhd-idle-arm64"
EXPECTED_HASH=ae8f165e50eb29e6192211281bd04319132895c7026d78b8e46902782be90f0f
EXPECTED_KERNEL=6.1.177-android14-11-gce3dfc2513b1
TOYBOX=/system/bin/toybox
STATEBASE=/data/adb/wifi_dhd_idle0
CONTROLLER=/sys/devices/platform/13120000.pcie
WLAN_FLAGS=/sys/class/net/wlan0/flags
CLAIM=
ACTIVE_PID=
umask 077

now_seconds() {
    IFS=' ' read -r uptime_value uptime_rest < /proc/uptime || return 1
    NOW=${uptime_value%%.*}
    case "$NOW" in ''|*[!0-9]*) return 1 ;; esac
}

now_seconds || exit 0
DEADLINE=$((NOW + 120))

guards() {
    GUARD_REASON=identity_path_driver_or_helper
    [ "$MODDIR" = /data/adb/modules/wifi_dhd_idle0 ] || return 1
    [ -d "$MODDIR" ] && [ ! -L "$MODDIR" ] || return 1
    [ ! -L "$STATEBASE" ] || return 1
    [ -x "$TOYBOX" ] || return 1
    [ "$("$TOYBOX" id -u)" = 0 ] || return 1
    [ "$(/system/bin/getprop ro.product.device)" = husky ] || return 1
    [ "$(/system/bin/getprop ro.build.version.incremental)" = 2026102101 ] || {
        GUARD_REASON=build_mismatch
        return 1
    }
    [ "$("$TOYBOX" uname -r)" = "$EXPECTED_KERNEL" ] || {
        GUARD_REASON=kernel_mismatch
        return 1
    }
    driver_hash=$("$TOYBOX" sha256sum /vendor/lib/modules/bcmdhd4398.ko 2>/dev/null) || return 1
    [ "${driver_hash%% *}" = 66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5 ] || return 1
    [ -r "$CONTROLLER/link_speed" ] || return 1
    IFS= read -r target_speed < "$CONTROLLER/link_speed" || return 1
    [ "$target_speed" = GEN1 ] || return 1
    driver_module=$("$TOYBOX" readlink "$CONTROLLER/driver/module") || return 1
    case "$driver_module" in */pcie_exynos_gs) ;; *) return 1 ;; esac
    [ -f "$HELPER" ] && [ -x "$HELPER" ] && [ ! -L "$HELPER" ] || return 1
    hash_output=$("$TOYBOX" sha256sum "$HELPER" 2>/dev/null) || return 1
    [ "${hash_output%% *}" = "$EXPECTED_HASH" ] || return 1
}

wlan_is_up() {
    [ -r "$WLAN_FLAGS" ] || return 1
    IFS= read -r net_flags < "$WLAN_FLAGS" || return 1
    case "$net_flags" in 0x*) flags_hex=${net_flags#0x} ;; *) return 1 ;; esac
    case "$flags_hex" in ''|*[!0-9a-fA-F]*) return 1 ;; esac
    [ "${#flags_hex}" -le 8 ] || return 1
    [ "$((net_flags & 1))" -ne 0 ]
}

guards || { printf 'result=guard_failed reason=%s\n' "$GUARD_REASON"; exit 0; }
IFS= read -r BOOT_ID < /proc/sys/kernel/random/boot_id || exit 0
case "$BOOT_ID" in ''|*[!0-9a-f-]*) exit 0 ;; esac
case "$BOOT_ID" in ????????-????-????-????-????????????) ;; *) exit 0 ;; esac
[ "${#BOOT_ID}" = 36 ] || exit 0
[ ! -L "$STATEBASE" ] || exit 0
"$TOYBOX" mkdir -p "$STATEBASE" || exit 0
[ -d "$STATEBASE" ] && [ ! -L "$STATEBASE" ] || exit 0
CLAIM="$STATEBASE/boot-$BOOT_ID"

# Atomic claim before OFF waits or driver ioctls. Never remove it in this boot.
"$TOYBOX" mkdir "$CLAIM" 2>/dev/null || {
    printf 'result=boot_already_claimed\n'
    exit 0
}
exec > "$CLAIM/service.log" 2>&1
printf 'phase=late_start boot_id=%s deadline_uptime=%s\n' "$BOOT_ID" "$DEADLINE"

outcome() {
    printf '%s\n' "$1" > "$CLAIM/outcome.txt"
    printf 'result=%s\n' "$1"
}

interrupted() {
    if [ -n "$ACTIVE_PID" ]; then
        kill -KILL "$ACTIVE_PID" 2>/dev/null || :
    fi
    outcome interrupted_state_unconfirmed
    exit 0
}
trap 'interrupted' 1 2 15
outcome claimed

run_helper() {
    operation=$1
    helper_log=$2
    now_seconds || return 124
    [ "$((DEADLINE - NOW))" -ge 3 ] || return 124
    call_deadline=$((NOW + 3))
    if [ "$operation" = inspect ]; then
        "$HELPER" inspect > "$helper_log" 2>&1 &
    elif [ "$operation" = explicit-set ]; then
        "$HELPER" explicit-set idletime 0 > "$helper_log" 2>&1 &
    else
        return 125
    fi
    ACTIVE_PID=$!
    printf 'operation=%s helper_pid=%s\n' "$operation" "$ACTIVE_PID"
    for poll in 1 2 3 4; do
        if ! kill -0 "$ACTIVE_PID" 2>/dev/null; then
            wait "$ACTIVE_PID"
            helper_rc=$?
            ACTIVE_PID=
            printf 'operation=%s exit=%s\n' "$operation" "$helper_rc"
            return "$helper_rc"
        fi
        now_seconds || NOW=$call_deadline
        if [ "$NOW" -ge "$call_deadline" ] || [ "$NOW" -ge "$DEADLINE" ]; then
            kill -KILL "$ACTIVE_PID" 2>/dev/null || :
            printf 'operation=%s timeout_pid=%s state=unconfirmed\n' "$operation" "$ACTIVE_PID"
            ACTIVE_PID=
            # No wait after timeout: an uninterruptible kernel ioctl may survive.
            return 124
        fi
        if ! "$TOYBOX" sleep 1; then
            kill -KILL "$ACTIVE_PID" 2>/dev/null || :
            printf 'operation=%s infrastructure=sleep_failed state=unconfirmed\n' "$operation"
            ACTIVE_PID=
            return 125
        fi
    done
    kill -KILL "$ACTIVE_PID" 2>/dev/null || :
    ACTIVE_PID=
    return 124
}

inspect_count=0
window_steps=0
# Finite count plus one fixed 120-second deadline; OFF never resets either.
while [ "$window_steps" -lt 120 ] && [ "$inspect_count" -lt 12 ]; do
    window_steps=$((window_steps + 1))
    now_seconds || { outcome clock_unavailable; exit 0; }
    [ "$NOW" -lt "$DEADLINE" ] || { outcome readiness_window_expired; exit 0; }
    if ! wlan_is_up; then
        # Cheap sysfs polling only while OFF; no helper ioctl and no radio toggle.
        "$TOYBOX" sleep 1 || { outcome off_wait_sleep_failed_no_set; exit 0; }
        continue
    fi
    inspect_count=$((inspect_count + 1))
    printf 'inspect_attempt=%s uptime=%s flags=%s\n' "$inspect_count" "$NOW" "$net_flags"
    run_helper inspect "$CLAIM/inspect-$inspect_count.log"
    inspect_rc=$?
    if [ "$inspect_rc" = 0 ]; then
        guards || {
            printf 'guard_failed reason=%s\n' "$GUARD_REASON"
            outcome guard_changed_before_set
            exit 0
        }
        wlan_is_up || { outcome wlan_down_before_set_no_write; exit 0; }
        outcome set_invocation_reserved
        # One invocation, fresh healthy GETs, at most one SET and one readback.
        run_helper explicit-set "$CLAIM/set.log"
        set_rc=$?
        case "$set_rc" in
            0) outcome helper_confirmed_zero ;;
            1) outcome set_preflight_failed_no_write ;;
            3) outcome set_failed_state_unconfirmed ;;
            4) outcome readback_failed_state_unconfirmed ;;
            124) outcome set_timeout_or_deadline_state_unconfirmed ;;
            125) outcome set_infrastructure_failed_state_unconfirmed ;;
            *) outcome helper_failed_state_unconfirmed ;;
        esac
        exit 0
    fi
    if [ "$inspect_rc" = 124 ]; then
        outcome inspect_timeout_or_deadline_no_set
        exit 0
    fi
    if [ "$inspect_rc" != 1 ]; then
        outcome inspect_abnormal_exit_no_set
        exit 0
    fi
    [ "$inspect_count" = 12 ] && break
    for pause in 1 2 3 4 5 6 7 8 9 10; do
        now_seconds || { outcome clock_unavailable; exit 0; }
        [ "$NOW" -lt "$DEADLINE" ] || { outcome readiness_window_expired; exit 0; }
        "$TOYBOX" sleep 1 || { outcome readiness_sleep_failed_no_set; exit 0; }
    done
    # The next iteration rechecks IFF_UP, even if it changed during the pause.
done
if [ "$inspect_count" -ge 12 ]; then
    outcome inspect_attempts_exhausted_no_set
else
    outcome readiness_steps_exhausted_no_set
fi
exit 0
