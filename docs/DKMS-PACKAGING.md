# DKMS packaging and production deployment safety

## Status

The `kernel-7-compat` branch has compiled as an out-of-tree module on Ubuntu 26.04 / kernel 7.0.0-38 using `make modules`. This is **not** runtime validation, package validation, or an endorsement to load it on a production NIC.

The upstream-derived `debian/control` still declares `realtek-r8125-dkms`, the same binary package name as the existing standard Realtek DKMS package. The module produced by both drivers is called `r8125.ko`. Merely renaming the Debian package or DKMS `PACKAGE_NAME` cannot prevent both builds from targeting the same module path and modprobe alias. Do not publish or install the existing Debian packaging as a co-installable alternative.

## Packaging work before release

- Decide whether to offer an **explicitly mutually exclusive** replacement package, using accurate `Conflicts`/`Replaces` semantics, rather than claiming side-by-side module activation is safe.
- Audit `debian/control`, `debian/rules`, maintainer scripts, `dkms.conf`, source directory/version metadata, module installation destination, and initramfs interactions together.
- Set a fork-specific source and package version and update maintainer/homepage metadata; do not present old upstream changelog values as the new driver version.
- Verify DKMS add/build/install/removal and recovery on **disposable test hosts**, including across a kernel update and reboot.
- Review secure-boot signing requirements, r8169 blacklist state, and firmware/PCI-ID coverage.
- Publish packages only after tested hardware bring-up, including RSS, MSI-X, multiple TX queues, ethtool offloads and throughput under load.

## Production deployment safeguards

- Preserve a known-good copy of the existing package and module, the current DKMS configuration, and out-of-band recovery.
- Never unload/rebind `r8125` across the only SSH management connection without an independently tested, time-triggered rollback.
- Benchmark new vs existing drivers on the same host and compare errors, missed RX packets, throughput and CPU cost.
- Keep CI **build-only**: no `make install`, `dkms install`, `modprobe`, or changes to the host's network device.

## Continuous integration

`.github/workflows/kernel-build.yml` compiles against headers installed on hosted Ubuntu runners. Runner kernels and header-package versions need not match the production kernel. A green workflow is therefore a compilation smoke test, not proof of kernel 7.0.0-38 or RTL8125 runtime compatibility.
