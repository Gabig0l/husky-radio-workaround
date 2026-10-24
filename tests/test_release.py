"""PC-only tests. OS calls and Android paths are replaced only in disposable fixtures."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import shutil
import struct
import subprocess
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
DRIVER_HASH = '66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5'
KERNEL = '6.1.177-android14-11-gce3dfc2513b1'
RESULTS = []


def passed(name):
    RESULTS.append(name)
    print('PASS', name)


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')


def run(command, **kwargs):
    return subprocess.run(command, text=True, capture_output=True, timeout=kwargs.pop('timeout', 20), **kwargs)


def helper_tests(zig, build):
    executable = build / ('helper-tests.exe' if os.name == 'nt' else 'helper-tests')
    compiled = run([zig, 'cc', '-std=c11', '-O2', '-UNDEBUG', '-Wall', '-Wextra', '-Werror',
                    '-I' + str(ROOT / 'tests/mock'), str(ROOT / 'tests/helper_harness.c'), '-o', str(executable)], timeout=180)
    assert compiled.returncode == 0, compiled.stderr
    cases = {'set-success': (0, 5, 2, 1), 'inspect': (0, 3, 1, 0),
             'default-inspect': (0, 3, 1, 0), 'already-zero': (0, 3, 1, 0),
             'invalid-args': (2, 0, 0, 0), 'nonroot': (1, 0, 0, 0),
             'socket-fail': (1, 0, 0, 0), 'magic-error': (1, 1, 0, 0),
             'wrong-magic': (1, 1, 0, 0), 'version-error': (1, 2, 0, 0),
             'wrong-version': (1, 2, 0, 0), 'get-error': (1, 3, 1, 0),
             'negative': (1, 3, 1, 0), 'unchanged-buffer': (1, 3, 1, 0),
             'set-error': (3, 4, 1, 1), 'readback-error': (4, 5, 2, 1),
             'readback-nonzero': (4, 5, 2, 1)}
    for name, expected in cases.items():
        result = run([str(executable), name])
        assert result.returncode == 0, (name, result.stderr)
        match = re.search(r'TEST_RESULT rc=(\d+) calls=(\d+) gets=(\d+) sets=(\d+)', result.stdout)
        assert match and tuple(map(int, match.groups())) == expected, (name, result.stdout)
        passed('helper/' + name)


class Fixture:
    def __init__(self, root, helper_hash):
        self.root, self.helper_hash = root, helper_hash
        self.bin = root / 'bin'
        self.idle = root / 'modules/idle0'
        self.gen1 = root / 'modules/gen1'
        for p in (self.bin, self.idle, self.gen1): p.mkdir(parents=True)
        for source in (ROOT / 'modules/idle0').iterdir():
            if source.is_file() and source.name != 'dhd-idle-arm64': shutil.copyfile(source, self.idle / source.name)
        for source in (ROOT / 'modules/gen1').iterdir():
            if source.is_file(): shutil.copyfile(source, self.gen1 / source.name)
        write(root / 'pcie/link_speed', 'GEN1\n')
        write(root / 'net/flags', '0x1\n')
        write(root / 'uptime', '10.00 0.00\n')
        write(root / 'boot-id', str(uuid.UUID(int=1)) + '\n')
        self.env = os.environ.copy()
        shell_bin = self.bin.as_posix()
        if os.name == 'nt':
            shell_bin = '/' + shell_bin[0].lower() + shell_bin[2:]
        self.env.update({'PATH': shell_bin + ':/usr/bin:/bin', 'TEST_PATH': shell_bin + ':/usr/bin:/bin',
                         'BOOTMODE': 'true', 'ARCH': 'arm64', 'API': '37', 'MAGISK_VER_CODE': '31000'})
        replacements = {'/data/adb/modules/wifi_dhd_idle0': str(self.idle),
                        '/data/adb/modules/codex_wifi_gen1_husky': str(self.gen1),
                        '/data/adb/wifi_dhd_idle0': str(root / 'state'),
                        '/sys/devices/platform/13120000.pcie': str(root / 'pcie'),
                        '/sys/class/net/wlan0/flags': str(root / 'net/flags'),
                        '/sys/bus/pci/devices/0001:01:00.0/current_link_speed': str(root / 'pcie/actual'),
                        '/proc/sys/kernel/random/boot_id': str(root / 'boot-id'),
                        '/proc/uptime': str(root / 'uptime'),
                        '/system/bin/toybox': str(self.bin / 'toybox'),
                        '/system/bin/getprop': str(self.bin / 'getprop'),
                        '/system/bin/getenforce': str(self.bin / 'getenforce')}
        self.paths = replacements
        for folder in (self.idle, self.gen1):
            for path in folder.glob('*.sh'):
                text = path.read_text()
                for old, new in replacements.items(): text = text.replace(old, new.replace('\\', '/'))
                write(path, text)
        posix = lambda p: str(p).replace('\\', '/')
        write(self.bin / 'id', '#!/bin/sh\n[ "$TEST_CASE" = nonroot ] && echo 1000 || echo 0\n')
        write(self.bin / 'getenforce', '#!/bin/sh\n[ "$TEST_CASE" = selinux ] && echo Permissive || echo Enforcing\n')
        write(self.bin / 'getprop', '''#!/bin/sh
case "$1" in
ro.product.device) [ "$TEST_CASE" = device ] && echo other || echo husky ;;
ro.build.version.incremental) [ "$TEST_CASE" = build ] && echo 9999999999 || echo 2026102101 ;;
esac
''')
        write(self.bin / 'toybox', f'''#!/bin/sh
operation=$1; shift
case "$operation" in
id) exec id "$@" ;;
uname) [ "$TEST_CASE" = kernel ] && echo unknown || echo {KERNEL} ;;
sha256sum)
case "$1" in
*/bcmdhd4398.ko) [ "$TEST_CASE" = driver-hash ] && echo wrong || echo '{DRIVER_HASH}  driver' ;;
*/dhd-idle-arm64) [ "$TEST_CASE" = helper-hash ] && echo wrong || echo '{helper_hash}  helper' ;;
*) exit 1 ;; esac ;;
readlink) [ "$TEST_CASE" = driver-name ] && echo /wrong || echo /modules/pcie_exynos_gs ;;
sleep) read tick rest < '{posix(root / 'uptime')}'; tick=${{tick%%.*}}; echo "$((tick + ${{1:-1}})).00 0.00" > '{posix(root / 'uptime')}'; /bin/sleep 0.02 ;;
*) exec "$operation" "$@" ;;
esac
''')
        write(self.bin / 'readlink', f'#!/bin/sh\nexec "{posix(self.bin / "toybox")}" readlink "$@"\n')
        write(self.bin / 'cat', f'''#!/bin/sh
if [ "$1" = '{posix(root / 'pcie/link_speed')}' ]; then
 value=$(/bin/cat "$1"); [ "$value" = 1 ] && echo GEN1 || echo "$value"
else exec /bin/cat "$@"; fi
''')
        write(self.idle / 'dhd-idle-arm64', f'''#!/bin/sh
echo "$*" >> '{posix(root / 'helper-calls')}'
if [ "$1" = inspect ]; then
 [ "$TEST_CASE" = inspect-fail ] && exit 1
 [ "$TEST_CASE" = inspect-abnormal ] && exit 2
 [ "$TEST_CASE" = inspect-timeout ] && exec /bin/sleep 60
 echo interface=wlan0 magic=0x00444944
 echo ioctl_version=1
 echo idletime_before=0
 echo mode=inspect mutation=none
 exit 0
fi
[ "$TEST_CASE" = set-fail ] && exit 3
[ "$TEST_CASE" = readback-fail ] && exit 4
exit 0
''')
        write(root / 'pcie/actual', '2.5 GT/s PCIe\n')
        for path in list(self.bin.iterdir()) + [self.idle / 'dhd-idle-arm64']:
            path.chmod(0o700)

    def execute(self, sh, relative, case='', installer=False, overrides=None):
        env = self.env.copy()
        env['TEST_CASE'] = case
        if overrides: env.update(overrides)
        target = self.root / relative
        if installer:
            env['MODPATH'] = str(self.idle).replace('\\', '/')
            runner = self.root / 'installer-runner.sh'
            write(runner, 'abort() { echo "ABORT: $*"; exit 22; }\nui_print() { echo "$*"; }\nset_perm() { :; }\n. "' + str(target).replace('\\', '/') + '"\n')
            target = runner
        # Git for Windows prepends its own tools on startup; restore the fixture
        # PATH inside the shell before sourcing, while retaining the script's $0.
        return run([sh, '-c', 'PATH="$TEST_PATH"; export PATH; . "$0"', target.as_posix()], env=env)

    def outcome(self):
        files = list((self.root / 'state').glob('*/outcome.txt'))
        return files[0].read_text().strip() if files else None

    def calls(self):
        file = self.root / 'helper-calls'
        return file.read_text().splitlines() if file.exists() else []


def shell_tests(sh, build, helper_hash):
    def fixture(): return Fixture(Path(tempfile.mkdtemp(prefix='radio-test-', dir=build)), helper_hash)
    for case, overrides in [('success', {}), ('bootmode', {'BOOTMODE': 'false'}),
                            ('arch', {'ARCH': 'x86'}), ('api', {'API': '36'}),
                            ('magisk', {'MAGISK_VER_CODE': '30000'}),
                            *[(x, {}) for x in ['nonroot', 'device', 'build', 'kernel', 'selinux', 'driver-hash', 'helper-hash', 'driver-name']]]:
        f = fixture()
        result = f.execute(sh, 'modules/idle0/customize.sh', case, True, overrides)
        assert result.returncode == (0 if case == 'success' else 22), (case, result.stdout, result.stderr)
        assert not f.calls() and (f.root / 'pcie/link_speed').read_text() == 'GEN1\n'
        passed('installer/' + case)
    for case in ['device', 'build', 'kernel', 'driver-hash', 'helper-hash', 'driver-name', 'nonroot']:
        f = fixture()
        result = f.execute(sh, 'modules/idle0/service.sh', case)
        assert result.returncode == 0 and not f.calls() and f.outcome() is None, (case, result.stdout, result.stderr)
        assert 'result=guard_failed' in result.stdout, (case, result.stdout, result.stderr)
        passed('service/reject-' + case)
    for case, outcome, max_sets in [('success', 'helper_confirmed_zero', 1),
                                   ('set-fail', 'set_failed_state_unconfirmed', 1),
                                   ('readback-fail', 'readback_failed_state_unconfirmed', 1),
                                   ('inspect-fail', ('inspect_attempts_exhausted_no_set', 'readiness_window_expired'), 0),
                                   ('inspect-abnormal', 'inspect_abnormal_exit_no_set', 0),
                                   ('inspect-timeout', 'inspect_timeout_or_deadline_no_set', 0),
                                   ('wifi-off', ('readiness_window_expired', 'readiness_steps_exhausted_no_set'), 0)]:
        f = fixture()
        if case == 'wifi-off': write(f.root / 'net/flags', '0x0\n')
        result = f.execute(sh, 'modules/idle0/service.sh', case)
        expected_outcomes = outcome if isinstance(outcome, tuple) else (outcome,)
        assert result.returncode == 0 and f.outcome() in expected_outcomes, (case, f.outcome(), result.stdout, result.stderr)
        initial_outcome = f.outcome()
        calls = f.calls()
        assert calls.count('explicit-set idletime 0') == max_sets
        assert calls.count('inspect') <= 12
        if max_sets: assert calls == ['inspect', 'explicit-set idletime 0']
        again = f.execute(sh, 'modules/idle0/service.sh', case)
        assert again.returncode == 0 and f.calls() == calls and f.outcome() == initial_outcome
        passed('service/' + case + '-and-no-retry')
    for case in ['success', 'device', 'build', 'kernel', 'driver-name', 'nonroot']:
        f = fixture()
        write(f.root / 'pcie/link_speed', 'GEN3\n')
        result = f.execute(sh, 'modules/gen1/post-fs-data.sh', case)
        assert result.returncode == 0
        assert (f.root / 'pcie/link_speed').read_text() == ('1\n' if case == 'success' else 'GEN3\n'), (case, result.stdout, result.stderr)
        assert not f.calls()
        passed('gen1/' + case)
    for case in ['success', 'driver-hash', 'helper-hash', 'device', 'build', 'kernel']:
        f = fixture()
        result = f.execute(sh, 'modules/idle0/verify.sh', case)
        assert result.returncode == (0 if case == 'success' else 1), (case, result.stdout, result.stderr)
        assert all(x == 'inspect' for x in f.calls())
        assert len(f.calls()) == (1 if case == 'success' else 0)
        passed('verifier/read-only-' + case)
    for file in list((ROOT / 'modules').rglob('*.sh')):
        assert run([sh, '-n', str(file)]).returncode == 0, file.name
    passed('shell/syntax-all-modules')


def elf_tests():
    data = (ROOT / 'modules/idle0/dhd-idle-arm64').read_bytes()
    header = struct.unpack_from('<16sHHIQQQIHHHHHH', data)
    assert data[:6] == b'\x7fELF\x02\x01' and header[2] == 183
    assert header[1] == 3, 'Expected position-independent ET_DYN'
    programs = [struct.unpack_from('<IIQQQQQQ', data, header[5] + i * header[9]) for i in range(header[10])]
    assert not any(p[0] == 3 for p in programs), 'Must have no dynamic interpreter'
    assert any(p[0] == 0x6474e552 for p in programs), 'RELRO missing'
    assert any(p[0] == 0x6474e551 and not p[1] & 1 for p in programs), 'Stack must not execute'
    assert not any(p[0] == 1 and p[1] & 7 == 7 for p in programs), 'Writable executable segment'
    assert b'C:\\Users\\' not in data and b'/Users/' not in data
    manifest = json.loads((ROOT / 'BUILD-MANIFEST.json').read_text())
    assert hashlib.sha256(data).hexdigest() == manifest['helperSha256']
    assert manifest['helperSha256'] in (ROOT / 'modules/idle0/service.sh').read_text()
    assert manifest['helperSha256'] in (ROOT / 'modules/idle0/verify.sh').read_text()
    passed('binary/aarch64-static-pie-hardening-and-hash-pins')


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--zig', required=True)
    p.add_argument('--sh', required=True)
    args = p.parse_args()
    build = ROOT / 'build/tests'
    build.mkdir(parents=True, exist_ok=True)
    os.environ['ZIG_LOCAL_CACHE_DIR'] = str(build / 'cache-local')
    os.environ['ZIG_GLOBAL_CACHE_DIR'] = str(build / 'cache-global')
    helper_tests(args.zig, build)
    elf_tests()
    manifest = json.loads((ROOT / 'BUILD-MANIFEST.json').read_text())
    shell_tests(args.sh, build, manifest['helperSha256'])
    result = {'passed': len(RESULTS), 'cases': RESULTS, 'scope': 'PC tests with mocked OS/driver/filesystem boundaries; no phone access or efficacy test'}
    (ROOT / 'TEST-RESULTS.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'passed': len(RESULTS), 'phoneAccess': False}))


if __name__ == '__main__':
    main()
