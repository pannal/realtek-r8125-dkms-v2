# RTL8125 9.018 optimized development branch

Experimental Linux driver based on Realtek **9.018.00**, via
[awesometic](https://github.com/awesometic/realtek-r8125-dkms), with selected ideas
from [ewaldc's 9.014 rewrite](https://github.com/ewaldc/realtek-r8125-dkms).
The older `master` and `kernel-7-compat` histories are preserved separately.

RSS and multiple TX queues are enabled at build time. Actual queue counts and
MSI-X use depend on the chip revision and successful vector allocation. The
newer Realtek RX page reuse, DMA lifecycle and offload paths are retained.
Performance improvements have **not** been established on hardware.

This branch is for **build-only development**. Both this fork and the production
awesometic package build `r8125.ko`; they are not safely co-installable merely by
renaming a package. Do not install this branch over a working network driver.
The inherited package-release workflow has been removed, and the legacy
`autorun.sh` / DKMS install/remove helpers exit without changing the system.

## Build without installing

Use a disposable development machine/container with a compiler matching the
target kernel, kernel headers, make, binutils, Python 3 and kmod installed:

```bash
CC=gcc-15 scripts/build-only.sh /usr/src/linux-headers-7.0.0-38-generic build
python3 tests/test_driver_paths.py
```

The script builds the module and checks compiler defines, linked RSS code and
module metadata. Outputs in `build/` include the uninstalled module, build log,
metadata and source/module hashes. Set `ENABLE_PTP_SUPPORT=y` to compile the
optional PTP path. NAPI, RSS, multiple TX queues, page reuse and DASH remain
selected in this build profile. A plain `make` now builds only; installation is
still an explicit inherited target and must not be used on production.

The CI matrix targets Ubuntu 22.04 GA (5.15), 24.04 GA (6.8) and 26.04 GA (7.0),
plus the exact 7.0.0-38 headers with optional PTP. These are compile tests, not a
claim of hardware support. Older kernels are outside this branch's validation
scope; retained legacy conditionals do not establish compatibility.

See the [technical report](docs/RTL8125-9.018-PORT.md) for source comparison,
modifications, validation limits, packaging recommendations and remaining tests.
The [benchmark and rollback plan](docs/BENCHMARK-AND-ROLLBACK.md) requires an
independent, tested recovery route before any live-driver experiment.

## License

GPL-2.0; see [LICENSE](LICENSE). Original Realtek driver notices are retained.
