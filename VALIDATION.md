# Validation scope

The underlying 1.3 settings and boot logic were verified on one Pixel 8 Pro running GrapheneOS 2026102101. That observation did not validate this new public installer, freshly built/stripped helper or verification script on a phone. No phone access was performed while preparing this release.

`tests/test_release.py` compiles a host harness which includes the production helper source and mocks only its OS boundary. It checks ioctl sequence, payload bytes, preflight refusal, single SET, zero-already-set behaviour, error/uncertain readback results and nonroot refusal.

Shell tests run the real script bodies in disposable fixtures with mechanically redirected Android paths and mocked system commands. They check compatibility refusal, the bounded service, once-per-boot claim, failure/timeout outcomes, early GEN1 action and the verifier's read-only behaviour. These tests cannot prove Android's installer integration, kernel scheduling or radio reliability.

ELF checks cover AArch64, position-independent static layout, no dynamic interpreter, RELRO, a non-executable stack, absence of writable executable load segments, stripped personal build paths and the pinned helper hash. Source ZIP contents, line endings and published artifacts are reviewed separately.

See `TEST-RESULTS.json` for actual completed PC cases. These are software tests, not tests of Wi-Fi/Bluetooth efficacy. No second handset, controlled A/B, prolonged/overnight, throughput/power benchmark or actual watch synchronisation test was performed for this public release.
