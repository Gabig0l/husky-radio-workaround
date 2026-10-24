# Pixel 8 Pro Wi-Fi/Bluetooth dropouts: experimental PCIe GEN1 and DHD idletime=0 mitigation

Case notes, 24 October 2026. This is what was tried on one Pixel 8 Pro, what the records confirm, and what remains unanswered. It is an independent experiment, with no official Google or GrapheneOS fix claimed. For downloads and step-by-step instructions, start with [the guide](../README.md).

## What this case establishes

On this Pixel 8 Pro, two local Wi-Fi adjustments were applied automatically and verified after boot: a PCIe GEN1 target and DHD `idletime=0`. Wi-Fi was associated; Bluetooth reported ON and STATE_CONNECTED in the 24 October capture, with zero Bluetooth crashes reported for that boot. These observations establish the applied settings and that moment's radio state. They do not establish a lasting repair or show that either adjustment directly fixes the Bluetooth stack.

The same device had already reproduced this class of Wi-Fi/PCIe failure on an official Google Android 16 installation without root, with the bootloader locked and Verified Boot green. An earlier configuration using GEN1 and idletime=0 also had a reported overnight recurrence on 8 October. The evidence therefore does not support calling this an Android 17 regression, a GrapheneOS-specific bug, or a definitive software repair. A hardware or power/reset fault remains possible; the records do not identify a failed component.

## Environment and version evidence

| Item | Verified environment |
|---|---|
| Device | Google Pixel 8 Pro, `husky` |
| Current GrapheneOS build | `2026102101` |
| Current kernel | `6.1.177-android14-11-gce3dfc2513b1` |
| Root framework | Magisk 31.0; this is a modified installation |
| SELinux | Enforcing |
| Local radio scripts | `1.3-local-20261023` |
| Previous reviewed build | `2026101601`, kernel `6.1.177-android14-11-ga001019bb34e` |

Android 17 is corroborated by [GrapheneOS release history](https://grapheneos.org/releases#2026061800). An earlier capture from this same device/build `2026100201` explicitly recorded `ro.build.version.release=17` and SDK 37. The selected current-build captures record the build and kernel, but do not include a fresh release/SDK property pair. The `android14` string in the kernel release is not a measurement of the running Android userspace version. The current build is used as the precise compatibility identifier.

## Symptoms and diagnostic sequence

Before the mitigation, Wi-Fi could work after reboot and later stop scanning or fail to turn on; Bluetooth could fail around the same incident. In the Google Android 16 test on 5 October, kernel records showed PCIe suspend, failed resume/link training, `pcie link up fail`, `PCIe RC resume failed!!! (-32)` and `PCIE_RC_LINK_UP_FAIL`. Wi-Fi requested a Big Hammer recovery; a Bluetooth `BT_COEX_THREAD` abort with vendor error 127 followed. The framework eventually disabled Wi-Fi after repeated recovery failures.

This sequence is consistent with a shared radio recovery following Wi-Fi/PCIe failure. It does not prove that all Bluetooth problems on Pixels have that cause. Similar symptoms alone cannot identify the same defect on another phone. A later 5 October test reproduced the class of fault after about 18 minutes on that unrooted Google system. Recovery after reboot was temporary.

The 8 October overnight recurrence was reported after earlier adjustments. The available capture came from a subsequent boot, so it cannot establish whether idletime had remained zero at the instant of the overnight failure or identify that incident's kernel cause. The recurrence must still be counted against any permanent-fix claim.

## Exact local changes

### 1. PCIe target GEN1

An early Magisk `post-fs-data.sh` writes `1` plus a newline to:

```text
/sys/devices/platform/13120000.pcie/link_speed
```

The audited control changes the target link speed; this is not a direct reset or retrain command. On the 20 October verified boot, target readback was GEN1 and the actual negotiated endpoint speed was `2.5 GT/s PCIe`, width x1. Target readback and negotiated speed are separate checks.

The installed script requires the exact husky/build/kernel identity, expected controller driver module and readable/writable target with the expected GEN1/GEN3 format. It performs one write without waits, radio toggles or driver resets. The controller driver was reviewed offline; the early script does not itself hash the PCIe module at every boot.

### 2. Native DHD idletime=0

A separate late-start service uses a small local AArch64 helper on `wlan0`. It performs DHD GET_MAGIC, GET_VERSION and GET_VAR `idletime` before any explicit SET. Expected responses are magic `0x00444944`, ioctl version 1, and a valid integer. If already zero, it does not write. Otherwise it sends a single DHD SET_VAR payload consisting of `idletime\0` followed by four zero bytes and immediately reads the value back.

This uses the native DHD private ioctl, **not** an interchangeable generic `wl` command. In the reviewed AArch64 ABI, SIOCDEVPRIVATE is `0x89f0`; the DHD request is 40 bytes, with pointer at offset 8, length at 16, uint32 set at 20, used/needed at 24/28 and driver magic at 32. Native routing copies the first 32 bytes plus the driver field at offset 32. The current driver audit checked seven relevant instruction patterns and the unique `idletime` entry: varid 27, INT32/type 6, table stride 16.

The public [DHD ioctl header](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/include/dhdioctl.h) documents the protocol. In the [PCIe baseline implementation](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/dhd_pcie.c), setting zero invokes the runtime-PM disable path. That source revision is an explanatory baseline, not a claim that it exactly matches the shipped module. Local ELF review and successful live GET/readback provide the build-specific evidence.

The service requires exact device/build/kernel, the DHD and helper hashes below, expected driver module and existing GEN1. It checks wlan0 IFF_UP, has a fixed 120-second readiness deadline, at most 12 inspection attempts and one reserved SET invocation per boot. Calls have a roughly three-second userspace timeout. A kernel ioctl stuck in uninterruptible sleep may outlive a kill request; timeout means unconfirmed state, not guaranteed cancellation. There is no repeated SET, radio reset or attempt to revive a dead driver.

| Technical identity, build 2026102101 | SHA-256 |
|---|---|
| `bcmdhd4398.ko` | `66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5` |
| PCIe controller module reviewed offline | `62f4b54113c2ad10b6977f316d7cd43d94532414630fec8cb1694ae9ed37dc89` |
| Existing local helper binary | `0ce0316cf9e6ea17e9d512f76ffd27893c40a05d3949c9e15b5ddc0a13f8fa41` |

These are compatibility references, not download endorsements. No driver, firmware or boot image is distributed. The subsequent public release now includes the local helper with its corresponding source and runtime notices; see the repository README.

## Installation and reversal

The public follow-up now provides two guarded Magisk-app module ZIPs, helper source with an explicit MIT licence, static runtime notices, and a read-only verifier. Follow the repository README for the exact compatibility table, downloads, installation and rollback. The public installation packaging has PC-side validation only; it has not been installed on a phone in this publishing task.

For an existing installation of the exact two modules, disable both in Magisk and reboot normally to stop automatic boot actions. Verify resulting target/DHD state; disabling does not undo a setting already applied in the running boot. Do not guess defaults or flash an old boot image. Root modification remains outside supported unmodified GrapheneOS use.

## OTA maintenance

The 1.3 port was reviewed against modules extracted from the authenticated `2026102101` OTA and compared with the prior reviewed build. Broad code identity checks were false: changed code triggered focused review. The relevant PCIe control had retained control flow/relocations with two load offsets changed; the DHD native ABI patterns and idletime entry were rechecked. Live driver identity and GET/readback were subsequently confirmed after boot.

This was not merely adding a date to a whitelist. Unknown kernels/builds must remain rejected until the exact new driver is reviewed. An OTA can also replace modified boot components and prevent local modules from running. Root preservation and radio compatibility are separate checks; neither is established by a generic post-OTA recovery tool passing its tests.

## Observations and limits

| Observation | Scope |
|---|---|
| 20 October: automatic GEN1, 2.5 GT/s x1 and idletime 0 | Build 2026101601; short boot capture |
| 20 October: 3/3 ICMP replies explicitly through wlan0, no packet loss | Short connectivity sample; not a reliability benchmark |
| 20 October: no searched radio faults in captured kernel window | Approximately boot 0–132 seconds only |
| 24 October: automatic radio adjustments confirmed; Wi-Fi associated | Build 2026102101; captured boot state |
| 24 October: Bluetooth ON, STATE_CONNECTED, zero reported crashes | Same observed boot; no effective watch synchronisation test |
| 8 October: reported overnight recurrence with earlier configuration | Failure-time kernel/state evidence missing |

There is no controlled A/B study, no separation of the two adjustments' effects, no prolonged/overnight validation of 1.3 and no validation on another handset. Radio settings can be lost if the bus is reinitialised; this bounded once-per-boot service is not a continuous enforcer. Disabling runtime PM may increase battery use, while GEN1 may reduce peak throughput; neither effect has been measured here. System-wide suspend/resume still exists. There is no claim of repaired hardware, fixed Bluetooth software, or validated accessory synchronisation.

For a future recurrence, the useful evidence is the fault-time kernel/HAL sequence and DHD/PCIe state before reboot, captured privately and redacted before sharing. Logs, Wi-Fi dumps and bugreports can contain personal identifiers. Do not change SELinux or add repeated recovery loops merely because a diagnostic call fails.

Root-manager repairs and namespace/app compatibility cleanup were separate maintenance work; they are not offered as radio fixes. Software tests for a private recovery tool do not measure Wi-Fi or Bluetooth efficacy.
