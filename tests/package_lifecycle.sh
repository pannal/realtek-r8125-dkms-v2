#!/usr/bin/env bash
# Run ONLY inside the disposable namespace/rootfs prepared for this test.
set -euo pipefail
[[ $(cat /.rtl8125-package-test-root 2>/dev/null) == disposable-rtl8125-test ]] || {
    echo 'Refusing: disposable-rootfs marker missing' >&2; exit 1;
}
[[ ! -d /sys/class/net ]] || { echo 'Refusing: live sysfs is visible' >&2; exit 1; }
awk 'NR > 1 && $2 == "00000000" { n++ } END { exit n ? 1 : 0 }' /proc/net/route || {
    echo 'Refusing: test requires an isolated network namespace without a default route' >&2; exit 1;
}
awk -F: 'NR > 2 { gsub(/[ \t]/, "", $1); if ($1 != "lo") exit 1 }' /proc/net/dev || {
    echo 'Refusing: non-loopback network interface visible' >&2; exit 1;
}
candidate=${1:?candidate deb}
stock=${2:?stock deb}
upgrade=${3:?upgrade fixture deb}
kernel=7.0.0-38-generic
[[ $(uname -r) != "$kernel" ]] || { echo 'Refusing: target matches running kernel' >&2; exit 1; }
for config in /etc/dkms/framework.conf /etc/dkms/framework.conf.d/*.conf; do
    [[ ! -f "$config" ]] || . "$config"
done
[[ -z ${modprobe_on_install:-} && -z ${post_transaction:-} ]] || exit 1
[[ -f /lib/modules/$kernel/modules.dep ]] || { echo 'Real kernel layout/index required' >&2; exit 1; }
trap 'echo "FAIL: line $LINENO: $BASH_COMMAND" >&2' ERR
export DEBIAN_FRONTEND=noninteractive
optimized=realtek-r8125-optimized-dkms
apt_local() {
    apt-get -o APT::Sandbox::User=root --no-install-recommends -y install "$1"
}
selected() { modinfo -k "$kernel" -n r8125; }
check_module() {
    local name=$1 version=$2 path built registration_arch=x86_64
    # The published stock postinst explicitly passes dpkg's architecture name.
    [[ "$name" != realtek-r8125 ]] || registration_arch=amd64
    dkms status -m "$name" -v "$version" -k "$kernel" | \
        grep -Fx "$name/$version, $kernel, $registration_arch: installed"
    path=$(selected)
    [[ "$path" == /lib/modules/"$kernel"/updates/dkms/r8125.ko* ]]
    [[ $(modinfo -F version "$path") == "$version"-NAPI-DASH* ]]
    [[ $(modinfo -F vermagic "$path") == "$kernel "* ]]
    mapfile -t installed < <(find /lib/modules/"$kernel" -type f -name 'r8125.ko*')
    [[ ${#installed[@]} == 1 ]]
    mapfile -t built < <(find /var/lib/dkms/"$name"/"$version"/"$kernel" -type f -path '*/module/r8125.ko*')
    [[ ${#built[@]} == 1 ]]
    cmp -- "$path" "${built[0]}"
    [[ -z $(find /var/lib/dkms -type f -path '*/original_module/*' -name 'r8125.ko*') ]]
    [[ -z $(dpkg --audit) ]]
}
clean_provider() {
    local package=$1
    if dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx installed; then
        dpkg --purge "$package"
    fi
}
clean_provider "$optimized"
clean_provider realtek-r8125-dkms
[[ -z $(dkms status) ]]

printf '\nTEST: stock baseline and conflict refusal\n'
dpkg -i "$stock"
check_module realtek-r8125 9.018.00
stock_hash=$(sha256sum "$(selected)" | cut -d' ' -f1)
if dpkg --unpack "$candidate"; then echo 'Conflict was not enforced' >&2; exit 1; fi
check_module realtek-r8125 9.018.00

printf '\nTEST: deliberate stock-to-optimized migration\n'
apt_local "$candidate"
check_module realtek-r8125-optimized 9.018.00+opt1
[[ -z $(dkms status -m realtek-r8125) ]]

printf '\nTEST: reinstall, upstream-version upgrade and downgrade\n'
dpkg -i "$candidate"
check_module realtek-r8125-optimized 9.018.00+opt1
dpkg -i "$upgrade"
check_module realtek-r8125-optimized 9.018.00+opt2
[[ -z $(dkms status -m realtek-r8125-optimized -v 9.018.00+opt1) ]]
dpkg -i "$candidate"
check_module realtek-r8125-optimized 9.018.00+opt1
[[ -z $(dkms status -m realtek-r8125-optimized -v 9.018.00+opt2) ]]

printf '\nTEST: rollback to the actual stock package\n'
apt_local "$stock"
check_module realtek-r8125 9.018.00
[[ $(sha256sum "$(selected)" | cut -d' ' -f1) == "$stock_hash" ]]
[[ -z $(dkms status -m realtek-r8125-optimized) ]]
dpkg --remove realtek-r8125-dkms
[[ -z $(dkms status -m realtek-r8125) ]]
dpkg --purge realtek-r8125-dkms
[[ ! -e /usr/src/realtek-r8125-9.018.00 ]]

printf '\nTEST: no headers, actual header-package hook, second ABI hook\n'
# Older header trees are compile fixtures, not dpkg-installed kernel packages.
for old in 5.15.0-199-generic 6.8.0-147-generic; do
    [[ -L /lib/modules/$old/build && ! -e /lib/modules/$old/build.lifecycle-hidden ]]
    mv /lib/modules/"$old"/build /lib/modules/"$old"/build.lifecycle-hidden
done
restore_links() {
    for old in 5.15.0-199-generic 6.8.0-147-generic; do
        if [[ -L /lib/modules/$old/build.lifecycle-hidden ]]; then
            mv /lib/modules/"$old"/build.lifecycle-hidden /lib/modules/"$old"/build
        fi
    done
}
trap restore_links EXIT
dpkg --remove linux-headers-7.0.0-38-generic linux-headers-7.0.0-38
dpkg -i "$candidate"
[[ $(dkms status -m realtek-r8125-optimized -v 9.018.00+opt1) == *': added' ]]
[[ -z $(find /lib/modules -type f -name 'r8125.ko*') ]]
dpkg -i /var/cache/apt/archives/linux-headers-7.0.0-38_7.0.0-38.38_all.deb \
    /var/cache/apt/archives/linux-headers-7.0.0-38-generic_7.0.0-38.38_amd64.deb
check_module realtek-r8125-optimized 9.018.00+opt1
restore_links
/etc/kernel/header_postinst.d/dkms 6.8.0-147-generic
dkms status -m realtek-r8125-optimized -v 9.018.00+opt1 -k 6.8.0-147-generic | grep ': installed$'

printf '\nTEST: remove and purge leave no candidate or stale registration\n'
dpkg --remove "$optimized"
[[ -z $(dkms status -m realtek-r8125-optimized) ]]
[[ -z $(find /lib/modules -type f -name 'r8125.ko*') ]]
dpkg --purge "$optimized"
[[ ! -e /usr/src/realtek-r8125-optimized-9.018.00+opt1 ]]
[[ ! -e /usr/src/realtek-r8125-optimized-9.018.00+opt2 ]]
[[ -z $(dpkg --audit) ]]
printf '\nPASS: real dpkg/DKMS lifecycle; no module loading or hardware tests\n'
