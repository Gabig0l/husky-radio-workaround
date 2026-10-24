# Source and distribution provenance

The helper is a small locally authored userspace DHD ioctl client created during this device's diagnostic work in October 2026. Its original C source SHA-256 was `bbbfbb13088fb000723ba217978e2a96c036672cd870b2eda4c8f072a7062a0f`. The original locally verified executable SHA-256 was `0ce0316cf9e6ea17e9d512f76ffd27893c40a05d3949c9e15b5ddc0a13f8fa41`. The public source adds an explicit MIT licence identifier to that local implementation; no vendor binary or upstream driver implementation is included.

The two boot script bodies come from the locally verified `1.3-local-20261023` configuration for GrapheneOS build 2026102101. Public changes are licensing, module descriptions/version, a freshly compiled stripped helper and its pinned hash. Installation checks and a read-only verifier were added. See `BUILD-MANIFEST.json` for public source/helper hashes. The public ZIP installation itself has not been tested on a phone.

The original source contained no explicit licence. The public copies of these original local components now carry the MIT licence as part of this requested open distribution. This does not relicense third-party material. Protocol/layout facts were checked against Google's published DHD interface and the actual OTA module; full upstream source is linked rather than copied.

Upstream references retain their own notices and licences:

- [DHD interface header](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/include/dhdioctl.h): Broadcom GPLv2 with its stated linking exception. Not bundled as a source dependency or copied implementation.
- [DHD PCIe baseline](https://android.googlesource.com/kernel/google-modules/wlan/bcmdhd/bcm4398/+/85d6c7b2eb4e81fffb3cb349db06c885bfc0005b/dhd_pcie.c): mechanism reference, not redistributed.
- [Magisk](https://github.com/topjohnwu/Magisk): uses the user's existing installation/installer. No Magisk binary/installer source is bundled.
- The included helper is statically compiled with official Zig 0.17.0 for aarch64-linux-musl. The relevant bundled runtime notices are preserved in `third-party/`. The compiler itself is not distributed.

The Windows compiler archive used in the earlier local build was verified against the official Zig index before extraction: SHA-256 `b5663f69581dcf391293fbf16c06cb80d81d806545ce618b4d0bab7f0eb8c428`. [Official download index](https://ziglang.org/download/index.json).

No personal logs, serials, root-manager identity, Wi-Fi addresses/credentials, app data, boot images, proprietary drivers or firmware are included. Static runtimes are the only third-party binary code linked into the helper. Source and notices accompany it; downloaded firmware/driver images remain private and are not needed in the package.
