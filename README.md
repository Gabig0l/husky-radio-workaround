# Pixel 8 Pro radio workaround: GEN1 + DHD idletime=0

Wi-Fi works after a reboot, then disappears again. Bluetooth sometimes joins the disappearing act. If that sounds familiar, this project shares the two adjustments used on one Pixel 8 Pro, with installable modules, source code and a way to check the result.

**This is an experiment, not a confirmed permanent repair.** An earlier setup with these settings still had an overnight failure, and a hardware fault remains possible. The original boot logic and settings were checked on that phone. **The new public ZIPs, rebuilt helper and verification script have only been checked on a PC; they have not been installed on any phone.** Version 1.3 has no overnight stability result.

Start with the compatibility table below. This release is deliberately picky: matching the model alone is not enough. Please do not root a supported GrapheneOS installation just to try it.

## 1. Check whether this release applies

Every row must match. The installer checks these details and stops if they do not match; the boot scripts check again when they run.

| Requirement | This release |
|---|---|
| Device | Pixel 8 Pro, codename `husky` |
| OS build | GrapheneOS `2026102101`, already modified with root |
| Kernel | `6.1.177-android14-11-gce3dfc2513b1` |
| Android API | 37 |
| Existing Magisk | 31.0 / 31000 |
| SELinux | Enforcing |
| DHD driver SHA-256 | `66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5` |

Find the build in **Settings > About phone**. If you already have an authorized root shell, these commands read the remaining details without changing anything:

```sh
getprop ro.product.device
getprop ro.build.version.incremental
getprop ro.build.version.sdk
uname -r
getenforce
sha256sum /vendor/lib/modules/bcmdhd4398.ko
```

That `android14` in the kernel name is confusing, but it does not tell you which Android version is running. Use the exact build and kernel above. Other builds, stock Google firmware, other models and other root frameworks are outside this release. **If a check fails, stop. Do not downgrade, edit the checks or disable SELinux to get past it.** A new build needs its driver reviewed before it can be supported.

## 2. Download both module ZIPs

Open [release v1.3-public1](https://github.com/Gabig0l/husky-radio-workaround/releases/tag/v1.3-public1), or use these versioned downloads:

- [PCIe GEN1 module](https://github.com/Gabig0l/husky-radio-workaround/raw/refs/tags/v1.3-public1/downloads/husky-pcie-gen1-1.3-public1.zip): `husky-pcie-gen1-1.3-public1.zip`
- [DHD idletime=0 module](https://github.com/Gabig0l/husky-radio-workaround/raw/refs/tags/v1.3-public1/downloads/husky-dhd-idle0-1.3-public1.zip): `husky-dhd-idle0-1.3-public1.zip`
- [SHA256SUMS.txt](https://github.com/Gabig0l/husky-radio-workaround/raw/refs/tags/v1.3-public1/downloads/SHA256SUMS.txt) to check the downloaded files.

You need **both module ZIPs**. GitHub also offers a **Source code** archive for reading or building the project. That one does not install in Magisk, despite looking equally ZIP-shaped.

On a PC, check each ZIP against `SHA256SUMS.txt` using `sha256sum`, or PowerShell `Get-FileHash -Algorithm SHA256`. Each result must match the line for that file. Get the files and checksum list from this repository's release; a checksum only helps if you trust the list you compare against.

## 3. Install on an already rooted, matching phone

1. If you already use these modules, keep a copy of your current versions. This release uses the original module IDs, so it updates them in place.
2. In the Magisk app, open **Modules > Install from storage** and choose `husky-pcie-gen1-1.3-public1.zip`.
3. If its checks pass, install `husky-dhd-idle0-1.3-public1.zip` the same way. **Install both before rebooting.** If either install fails, disable the other newly installed module before rebooting and stop. Do not bypass the error.
4. If Wi-Fi can be enabled normally, leave it enabled before reboot. Reboot normally once after both installs. The PCIe target is set early; the DHD service has a fixed 120-second readiness window and only calls the helper while wlan0 is up. It does not turn Wi-Fi on for you.
5. If Wi-Fi cannot start, or the driver does not respond to the initial read checks in that window, stop and read the result. Repeatedly running the service will not repair a dead PCIe link or driver.

Installation checks the phone and copies the module files. The radio adjustments happen on the next boot. The packages do not flash boot images, replace firmware or drivers, change SELinux policies, install app hooks or hide root.

## 4. Verify the settings and then test normal use

After boot, enable Wi-Fi normally and allow the readiness window to complete. From an **already authorized root shell**, run once:

```sh
/system/bin/sh /data/adb/modules/wifi_dhd_idle0/verify.sh
```

For an already authorized ADB connection, the equivalent is:

```sh
adb shell su -c '/system/bin/sh /data/adb/modules/wifi_dhd_idle0/verify.sh'
```

This check only reads: it does not change DHD settings or reset the radios. It checks compatibility, file hashes, the GEN1 target, the actual link speed and one DHD read. A successful result includes:

```text
pcie_target=GEN1
pcie_negotiated=2.5 GT/s PCIe
interface=wlan0 magic=0x00444944
ioctl_version=1
idletime_before=0
mode=inspect mutation=none
PASS: GEN1 target and healthy DHD GET reporting idletime=0. This is not a stability test.
```

`UNCONFIRMED` means the check could not confirm the state. Treat it as a stop sign. A driver call stuck inside the kernel can outlive a request to kill its process. Do not repeat helper writes or delete the once-per-boot claim to force another attempt. If idletime later returns to a nonzero value, the bus may have restarted; the service applies the setting once per boot, rather than continually forcing it.

Next, try the things you actually use: browsing, file transfers, leaving the screen off, and connecting a Bluetooth accessory **and using it**. For a watch, that includes a real sync. Keep a note of how long it works and whether the fault returns. A verifier PASS confirms the settings were read back. Your usual use is the next test; the PASS alone cannot tell you the problem is solved.

Useful local records, if a maintainer needs them:

- `/data/adb/modules/codex_wifi_gen1_husky/last-boot.log`
- `/data/adb/wifi_dhd_idle0/boot-<current-boot-id>/outcome.txt`
- The neighbouring `service.log`, `inspect-*.log` and `set.log`.

Keep these records private until you have removed boot IDs and other personal identifiers. The modules do not upload anything or collect telemetry.

## 5. Undo

In Magisk **Modules**, disable **both**:

- `codex_wifi_gen1_husky` (PCIe Gen1)
- `wifi_dhd_idle0` (DHD idletime zero)

Reboot normally, then check the resulting PCIe/DHD state. The reboot matters: disabling a module does not undo a setting already applied during the current boot. After that, you can remove the disabled modules in Magisk. Do not guess a live reversal value or flash somebody else's boot image. Removing these modules does not remove root or restore an unmodified GrapheneOS installation.

If Android cannot boot after installing a module, use the recovery procedure appropriate to your already rooted installation. Do not unlock/relock or factory-reset on the basis of this README: those operations can erase data. Have a working module-disable/recovery path before installing experimental boot modules.

## What the changes actually do

The early module writes `1` to `/sys/devices/platform/13120000.pcie/link_speed`. This selects a GEN1 target; it does not directly retrain/reset the link. A separate service uses the native DHD private ioctl on wlan0, with GET_MAGIC/GET_VERSION/GET_VAR preflight before a single explicit INT32 `idletime=0` SET and readback. Zero disables the audited DHD runtime-PM path, not system-wide suspend/resume. The service uses a fixed readiness deadline, bounded inspections and one SET invocation per boot.

GEN1 can reduce peak throughput; disabling runtime PM can increase power use. Neither effect was measured in this case. The settings can be lost when the bus is reinitialised. There is no direct Bluetooth-stack patch here; any Bluetooth benefit is an observation to test, not a guarantee.

The same device reproduced the class of PCIe failure on an unrooted official Google Android 16 system with a locked bootloader. A reported overnight recurrence also occurred with an earlier GEN1/idletime-zero configuration. Read [the evidence](docs/case-report.md) before drawing a causal conclusion.

## Build, review and licence

The local C helper and boot scripts are published under MIT; [provenance and runtime notices](PROVENANCE.md) explain their origin and the static runtime licences. No vendor driver, firmware or boot image is redistributed. Source is provided for the helper included in the DHD ZIP.

To build using an existing official Zig 0.17.0 compiler and Python 3:

```sh
python tools/build.py --zig /path/to/zig --output /path/to/release-files
python tests/test_release.py --zig /path/to/zig --sh /path/to/sh
```

See `BUILD-MANIFEST.json`, `VALIDATION.md` and `tests/`. PC-side tests cover refusal paths, helper semantics and packaging. They are not radio efficacy tests. The new helper is compiled from the same local implementation with licensing added and symbols stripped; its new hash is pinned by the service, installer and verifier.

[Magisk's module guide](https://topjohnwu.github.io/Magisk/guides.html) explains installation and module boot stages. The [DHD ABI header](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/include/dhdioctl.h) and [PCIe source baseline](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/dhd_pcie.c) explain the protocol/mechanism; that baseline is not claimed to match every instruction in the shipped driver.

This is an independent community project, with no affiliation to Google or GrapheneOS.
