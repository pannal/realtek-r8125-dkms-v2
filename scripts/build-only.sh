#!/usr/bin/env bash
# Compile and inspect a module; never install or load it.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
kdir=$(realpath -- "${1:?Usage: build-only.sh KERNEL_HEADERS [OUTPUT_DIRECTORY]}")
output=$(realpath -m -- "${2:-$repo/build}")
[[ -f "$kdir/Makefile" ]] || { echo 'Missing kernel headers' >&2; exit 1; }
mkdir -p -- "$output"
jobs=${JOBS:-$(getconf _NPROCESSORS_ONLN)}
(( jobs > 16 )) && jobs=16
compiler=${CC:-cc}
ptp=${ENABLE_PTP_SUPPORT:-n}
[[ "$ptp" == y || "$ptp" == n ]] || { echo 'PTP must be y or n' >&2; exit 1; }
make -C "$kdir" M="$repo/src" clean
make -C "$kdir" M="$repo/src" CC="$compiler" ENABLE_PTP_SUPPORT="$ptp" \
    V=1 -j"$jobs" modules 2>&1 | tee "$output/build.log"
# Verify defines actually reached both translation units and RSS was linked.
python3 - "$repo/src" "$ptp" <<'PY'
from pathlib import Path
import re
import sys
src = Path(sys.argv[1])
required = ('CONFIG_R8125_NAPI', 'ENABLE_RSS_SUPPORT',
            'ENABLE_MULTIPLE_TX_QUEUE', 'ENABLE_PAGE_REUSE', 'ENABLE_DASH_SUPPORT')
for obj in ('r8125_n', 'r8125_rss'):
    command = (src / f'.{obj}.o.cmd').read_text()
    for define in required:
        if f'-D{define}' not in command:
            raise SystemExit(f'{obj}: missing {define}')
link = (src / '.r8125.o.cmd').read_text()
# Newer Kbuild passes object inputs through an ld response file.
if re.search(r'@(?:[^\s]*/)?r8125\.mod(?:\s|$)', link):
    link += (src / 'r8125.mod').read_text()
if 'r8125_rss.o' not in link:
    raise SystemExit('RSS object missing from link command')
if sys.argv[2] == 'y':
    if '-DENABLE_PTP_SUPPORT' not in (src / '.r8125_n.o.cmd').read_text():
        raise SystemExit('PTP flag missing')
    if 'r8125_ptp.o' not in link:
        raise SystemExit('PTP object missing from link command')
print('Verified NAPI, RSS, multiple TX, page reuse, DASH and selected PTP flags/objects')
PY
cp -- "$repo/src/r8125.ko" "$output/r8125.ko"
modinfo "$output/r8125.ko" | tee "$output/modinfo.txt"
target_release=$(cat "$kdir/include/config/kernel.release")
vermagic=$(modinfo -F vermagic "$output/r8125.ko")
[[ "${vermagic%% *}" == "$target_release" ]] || {
    echo "Module vermagic does not match target headers" >&2; exit 1;
}
{
    printf 'Validation: compile-only; no installation, module loading or hardware tests\n'
    printf 'Source HEAD: %s\n' "${SOURCE_REVISION:-$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unknown)}"
    printf 'Kernel release: %s\n' "$target_release"
    printf 'PTP: %s\n' "$ptp"
    "$compiler" --version | head -1
    sha256sum "$output/r8125.ko" "$repo/src/Makefile" "$repo/src/r8125_n.c" "$repo/src/r8125.h" "$repo/dkms.conf"
} > "$output/manifest.txt"
