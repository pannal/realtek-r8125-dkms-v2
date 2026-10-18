#!/usr/bin/env bash
# Build unsigned Debian source/binary artifacts; no install, sign or upload.
set -euo pipefail
repo=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
output=$(realpath -m -- "${1:-$repo/packages}")
mkdir -p -- "$output"
scratch=$(mktemp -d "$output/.source.XXXXXX")
trap 'rm -rf -- "$scratch"' EXIT
source_name=$(dpkg-parsechangelog -l"$repo/debian/changelog" -S Source)
version=$(dpkg-parsechangelog -l"$repo/debian/changelog" -S Version)
upstream=${version%-*}
epoch=$(dpkg-parsechangelog -l"$repo/debian/changelog" -S Timestamp)
tree="$scratch/$source_name-$upstream"
mkdir -- "$tree"
while IFS= read -r relative; do
    [[ "$relative" && "$relative" != /* && "$relative" != *..* ]] || exit 1
    [[ -f "$repo/$relative" && ! -L "$repo/$relative" ]] || {
        echo "Missing/nonregular manifest input: $relative" >&2; exit 1;
    }
    mkdir -p -- "$tree/$(dirname -- "$relative")"
    cp -p -- "$repo/$relative" "$tree/$relative"
done < "$repo/debian/source-manifest"
(
    cd -- "$scratch"
    tar --sort=name --mtime="@$epoch" --owner=0 --group=0 --numeric-owner \
        --exclude="$source_name-$upstream/debian" -cJf \
        "${source_name}_${upstream}.orig.tar.xz" "$source_name-$upstream"
    cd -- "$tree"
    dpkg-checkbuilddeps
    dpkg-buildpackage -us -uc -b
    dpkg-buildpackage -us -uc -S -sa
) 2>&1 | tee "$output/build-packages.log"
shopt -s nullglob
artifacts=("$scratch"/*.deb "$scratch"/*.dsc "$scratch"/*.tar.xz \
           "$scratch"/*.changes "$scratch"/*.buildinfo)
(( ${#artifacts[@]} >= 6 )) || { echo 'Missing package artifacts' >&2; exit 1; }
cp -- "${artifacts[@]}" "$output/"
sha256sum -- "${artifacts[@]}" | sed "s|$scratch/||" > "$output/SHA256SUMS"
printf 'Unsigned package artifacts: %s\n' "$output"
