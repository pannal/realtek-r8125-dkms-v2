#!/usr/bin/env python3
"""Inspect real unsigned package artifacts; never install or load a module."""
import hashlib
import io
from pathlib import Path
import re
import subprocess
import sys
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / 'packages').resolve()


def one(pattern):
    values = list(OUT.glob(pattern))
    assert len(values) == 1, (pattern, values)
    return values[0]


def tar_members(data):
    archive = tarfile.open(fileobj=io.BytesIO(data))
    return archive, {m.name.removeprefix('./'): m for m in archive if m.isfile()}


package = one('*_all.deb')
fields = subprocess.check_output(['dpkg-deb', '-f', str(package)], text=True)
assert re.search(r'^Package: realtek-r8125-optimized-dkms$', fields, re.M)
assert re.search(r'^Architecture: all$', fields, re.M)
assert re.search(r'^Depends: dkms \(>= 3\.0\.11\)$', fields, re.M)
conflicts = re.search(r'^Conflicts: (.+)$', fields, re.M).group(1)
assert set(conflicts.split(', ')) == {'realtek-r8125-dkms', 'r8125-dkms'}
version = re.search(r'^Version: (.+)$', fields, re.M).group(1).rsplit('-', 1)[0]
base = f'usr/src/realtek-r8125-optimized-{version}/'
expected = {base + 'Makefile': 'Makefile', base + 'dkms.conf': 'dkms.conf'}
for source in (ROOT / 'debian/module-source-files').read_text().splitlines():
    destination = base + 'src/' + Path(source).name
    assert destination not in expected
    expected[destination] = source
archive, members = tar_members(subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(package)]))
for member in archive.getmembers():
    if member.name.removeprefix('./').startswith('usr/src/'):
        assert member.isdir() or member.isfile(), member.name
actual_sources = {name for name in members if name.startswith('usr/src/')}
assert actual_sources == set(expected), (actual_sources ^ set(expected))
for name, source in expected.items():
    m = members[name]
    assert m.uid == m.gid == 0 and not (m.mode & 0o111), name
    assert archive.extractfile(m).read() == (ROOT / source).read_bytes(), name
for name in members:
    assert not re.search(r'\.(?:ko|o|cmd|mod)(?:\.|$)|\.mod\.c$', name), name
control, controls = tar_members(subprocess.check_output(['dpkg-deb', '--ctrl-tarfile', str(package)]))
for name in ('postinst', 'prerm'):
    script = control.extractfile(controls[name]).read().decode()
    assert script.count('# Automatically added by dh_dkms/') == 1, name
    assert 'DKMS_NAME=realtek-r8125-optimized\n' in script
    assert f'DKMS_VERSION={version}\n' in script
    assert not re.search(r'\b(?:modprobe|rmmod|reboot|systemctl)\b', script)
manifest = (ROOT / 'debian/source-manifest').read_text().splitlines()
assert len(manifest) == len(set(manifest))
for pattern, is_debian in (('*.orig.tar.xz', False), ('*.debian.tar.xz', True)):
    with tarfile.open(one(pattern)) as source_tar:
        files = {m.name: m for m in source_tar if m.isfile()}
        prefix = '' if is_debian else f'realtek-r8125-optimized-dkms-{version}/'
        wanted = {prefix + path: path for path in manifest if path.startswith('debian/') == is_debian}
        assert set(files) == set(wanted), (pattern, set(files) ^ set(wanted))
        for name, path in wanted.items():
            assert source_tar.extractfile(files[name]).read() == (ROOT / path).read_bytes(), name
expected_artifacts = {one(pattern).name for pattern in (
    '*_all.deb', '*.dsc', '*.orig.tar.xz', '*.debian.tar.xz',
    '*_amd64.changes', '*_source.changes', '*_amd64.buildinfo', '*_source.buildinfo')}
checksums = (OUT / 'SHA256SUMS').read_text().splitlines()
assert len(checksums) == len(expected_artifacts) == 8
seen = set()
for line in checksums:
    digest, name = line.split(maxsplit=1)
    assert '/' not in name and name not in seen
    assert re.fullmatch(r'[0-9a-f]{64}', digest)
    seen.add(name)
    assert hashlib.sha256((OUT / name).read_bytes()).hexdigest() == digest, name
assert seen == expected_artifacts, seen ^ expected_artifacts
with tempfile.TemporaryDirectory(prefix='r8125-source-extract-') as temp:
    subprocess.run(['dpkg-source', '-x', str(one('*.dsc')), str(Path(temp) / 'source')], check=True)
print('PASS: package identity, conflicts, source whitelist/bytes, modes, lifecycle, hashes and source extraction')
