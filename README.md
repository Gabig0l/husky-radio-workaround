# Pixel 8 Pro radio workaround: GEN1 + DHD idletime=0

Installable, open-source packaging of the two local adjustments used on one Pixel 8 Pro. **Experimental mitigation, not an official or permanent Wi-Fi/Bluetooth repair.** Earlier use of these settings still had an overnight recurrence. A hardware fault remains possible.

The underlying boot logic/settings were verified on that phone. The new public ZIP installer, freshly built helper and verification script have PC-side checks only; **these release archives have not been installed or tested on a second phone, or on the publishing owner's phone**. There is no claim of overnight stability. Do not root a supported GrapheneOS installation just to try this.

## 1. Check whether this release applies

Every row must match. The installer refuses other combinations; the boot services keep their own checks.

| Requirement | This release |
|---|---|
| Device | Pixel 8 Pro, codename `husky` |
| OS build | GrapheneOS `2026102101`, already modified with root |
| Kernel | `6.1.177-android14-11-gce3dfc2513b1` |
| Android API | 37 |
| Existing Magisk | 31.0 / 31000 |
| SELinux | Enforcing |
| DHD driver SHA-256 | `66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5` |

Read the build in Settings > About phone. To check the remaining technical identifiers, an owner with an already authorized root shell can run these read-only commands:

```sh
getprop ro.product.device
getprop ro.build.version.incremental
getprop ro.build.version.sdk
uname -r
getenforce
sha256sum /vendor/lib/modules/bcmdhd4398.ko
```

The kernel suffix `android14` is not the userspace Android version. This package does not apply to every Android 17 Pixel, stock Google firmware, other GrapheneOS builds, other models or other root frameworks. **Do not downgrade, edit the checks or disable SELinux to make an unsupported phone pass.** A future build needs a new driver review, not just a new date in a list.

## 2. Download both module ZIPs

Open [release v1.3-public1](https://github.com/Gabig0l/husky-radio-workaround/releases/tag/v1.3-public1) and download:

- `husky-pcie-gen1-1.3-public1.zip`
- `husky-dhd-idle0-1.3-public1.zip`
- `SHA256SUMS.txt` to check the downloaded files.

The automatically generated GitHub **Source code** archive is for inspection/building; it is not a Magisk installer. Do not install a documentation ZIP or the source archive as a module.

On a PC, compare each downloaded ZIP's SHA-256 with `SHA256SUMS.txt` using `sha256sum`, or PowerShell `Get-FileHash -Algorithm SHA256`. These hashes detect file mismatch; trust in the download still depends on obtaining it from the intended release.

## 3. Install on an already rooted, matching phone

1. Keep a copy of your existing module versions if you already use them. The module IDs below are the same as the original local experiment; installing this release updates those modules rather than adding duplicates.
2. In the Magisk app, open **Modules > Install from storage** and choose `husky-pcie-gen1-1.3-public1.zip`.
3. If its checks pass, install `husky-dhd-idle0-1.3-public1.zip` the same way. **Install both before rebooting.** If either install fails, disable the other newly installed module before rebooting and stop. Do not bypass the error.
4. If Wi-Fi can be enabled normally, leave it enabled before reboot. Reboot normally once after both installs. The PCIe target is set early; the DHD service has a fixed 120-second readiness window and only calls the helper while wlan0 is up. It does not turn Wi-Fi on for you.
5. If Wi-Fi cannot start or the driver does not answer healthy GETs during that window, this release will not force it. Read the result rather than repeatedly running the service. A dead PCIe link/driver may need repair outside the scope of these adjustments.

The installer validates identity and stages module files; it does not change the live radio state. These packages do not flash boot images, replace firmware/drivers, alter SELinux policies, install app hooks or hide root.

## 4. Verify the settings and then test normal use

After boot, enable Wi-Fi normally and allow the readiness window to complete. From an **already authorized root shell**, run once:

```sh
/system/bin/sh /data/adb/modules/wifi_dhd_idle0/verify.sh
```

For an already authorized ADB connection, the equivalent is:

```sh
adb shell su -c '/system/bin/sh /data/adb/modules/wifi_dhd_idle0/verify.sh'
```

The verifier does not write DHD settings or reset radios. It checks compatibility/hashes, the GEN1 target, actual negotiated speed and one bounded native DHD GET. Expected output includes:

```text
pcie_target=GEN1
pcie_negotiated=2.5 GT/s PCIe
interface=wlan0 magic=0x00444944
ioctl_version=1
idletime_before=0
mode=inspect mutation=none
PASS: GEN1 target and healthy DHD GET reporting idletime=0. This is not a stability test.
```

An `UNCONFIRMED` timeout is not success. A kernel ioctl stuck in uninterruptible sleep may survive a kill request. Do not repeat helper writes or delete the once-per-boot claim to force retries. If idletime is nonzero after a successful earlier application, the bus may have been reinitialised; this service deliberately does not enforce it continuously.

Then test the actual use you care about: Wi-Fi browsing/transfer, screen-off idle, Bluetooth accessory connection and its real function, including watch synchronisation if relevant. Record the duration and any recurrence. A PASS from the verifier means settings were read back, not that connectivity or long-term stability was proved.

Useful local records, if a maintainer needs them:

- `/data/adb/modules/codex_wifi_gen1_husky/last-boot.log`
- `/data/adb/wifi_dhd_idle0/boot-<current-boot-id>/outcome.txt`
- The neighbouring `service.log`, `inspect-*.log` and `set.log`.

Keep these private initially. Redact boot IDs and any other identifiers before sharing. No telemetry or network upload is part of these modules.

## 5. Undo

In Magisk **Modules**, disable **both**:

- `codex_wifi_gen1_husky` (PCIe Gen1)
- `wifi_dhd_idle0` (DHD idletime zero)

Reboot normally, then verify the resulting PCIe/DHD state. Disabling does not undo a setting in the already running boot; this is why a reboot is part of rollback. Do not guess a live reversal value or flash somebody else's boot image. You can then remove the disabled modules in Magisk if desired. This restores neither an unmodified OS nor the original security assumptions of GrapheneOS.

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

Prepared with AI assistance from local records and source. This repository is independent of Google and GrapheneOS. Respect each community's rules on AI-authored content when sharing.
