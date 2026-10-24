"""Build the original local helper, then package two Magisk-app ZIPs. No device access."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
VERSION = '1.3-public1'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--zig', required=True, help='Existing official Zig compiler, version 0.17.0')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    compiler = Path(args.zig).resolve()
    if subprocess.check_output([str(compiler), 'version'], text=True).strip() != '0.17.0':
        raise SystemExit('This recorded build uses Zig 0.17.0 only.')
    build = ROOT / 'build'
    build.mkdir(exist_ok=True)
    env = os.environ.copy()
    env['ZIG_LOCAL_CACHE_DIR'] = str(build / 'cache-local')
    env['ZIG_GLOBAL_CACHE_DIR'] = str(build / 'cache-global')
    binary = build / 'dhd-idle-arm64'
    command = [str(compiler), 'cc', '-target', 'aarch64-linux-musl', '-static', '-fPIE',
               '-O2', '-s', '-std=c11', '-Wall', '-Wextra', '-Werror', '-Wconversion',
               '-fstack-protector-strong', '-Wl,-z,relro,-z,now',
               '-o', str(binary), str(ROOT / 'src/dhd_idle.c')]
    subprocess.run(command, cwd=ROOT, env=env, check=True)
    data = binary.read_bytes()
    helper_hash = sha(data)
    # No runtime logic is changed: update only the pinned identity of our fresh build.
    service = ROOT / 'modules/idle0/service.sh'
    text = service.read_text(encoding='utf-8')
    lines = text.splitlines()
    lines = ['EXPECTED_HASH=' + helper_hash if x.startswith('EXPECTED_HASH=') else x for x in lines]
    service.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
    (ROOT / 'modules/idle0/dhd-idle-arm64').write_bytes(data)
    for name in ('gen1', 'idle0'):
        target = ROOT / 'modules' / name / 'customize.sh'
        target.write_text((ROOT / 'tools/customize-template.sh').read_text(encoding='utf-8').replace(
            '@HELPER_SHA256@', helper_hash), encoding='utf-8', newline='\n')
    verify = ROOT / 'modules/idle0/verify.sh'
    verify.write_text((ROOT / 'tools/verify-template.sh').read_text(encoding='utf-8').replace('@HELPER_SHA256@', helper_hash),
                      encoding='utf-8', newline='\n')
    manifest = {'version': VERSION, 'device': 'husky', 'build': '2026102101',
                'kernel': '6.1.177-android14-11-gce3dfc2513b1',
                'dhdDriverSha256': '66b141c29ddfdbf1c42828044d3b36f099c0c564f979c2090f7056fa8c9846d5',
                'compiler': 'Zig 0.17.0', 'target': 'aarch64-linux-musl', 'stripped': True,
                'sourceSha256': sha((ROOT / 'src/dhd_idle.c').read_bytes()),
                'helperSha256': helper_hash, 'helperBytes': len(data),
                'arm64HelperExecutedOnPublishingPC': False,
                'newPackagesTestedOnPhone': False,
                'basis': 'Packaging of the locally verified 1.3 boot logic; source/helper implementation retained'}
    (ROOT / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    artifacts = []
    for name, label in [('gen1', 'husky-pcie-gen1'), ('idle0', 'husky-dhd-idle0')]:
        archive = output / f'{label}-{VERSION}.zip'
        with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            entries = {p.name: p for p in (ROOT / 'modules' / name).iterdir() if p.is_file()}
            entries.update({'LICENSE': ROOT / 'LICENSE', 'README.md': ROOT / 'README.md',
                            'PROVENANCE.md': ROOT / 'PROVENANCE.md',
                            'BUILD-MANIFEST.json': ROOT / 'BUILD-MANIFEST.json'})
            if name == 'idle0':
                entries['src/dhd_idle.c'] = ROOT / 'src/dhd_idle.c'
                for path in (ROOT / 'third-party').iterdir():
                    entries['third-party/' + path.name] = path
            for entry, path in sorted(entries.items()):
                info = zipfile.ZipInfo(entry, date_time=(2026, 10, 24, 0, 0, 0))
                info.create_system = 3
                info.external_attr = (0o100700 if entry.endswith('.sh') or entry == 'dhd-idle-arm64' else 0o100600) << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, path.read_bytes())
        artifacts.append(archive)
    (output / 'SHA256SUMS.txt').write_text(''.join(f'{sha(p.read_bytes())}  {p.name}\n' for p in artifacts), encoding='utf-8')
    print(json.dumps(manifest, indent=2))


if __name__ == '__main__':
    main()
