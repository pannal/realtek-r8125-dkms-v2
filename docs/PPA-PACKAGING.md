# PPA package preparation

This milestone prepares an unsigned source-only DKMS package for Ubuntu 26.04.
Experimental PPA publication was explicitly authorized on 2026-10-18, waiving
the original requirement for runtime validation before publication. This is not
production acceptance; no production installation is authorized by this file.
Local package lifecycle evidence and remaining limitations are recorded below. Hardware, boot, Secure Boot trust and recovery remain
separate requirements.

The package is `realtek-r8125-optimized-dkms`; its DKMS identity is
`realtek-r8125-optimized/9.018.00+opt1`. It still builds `r8125.ko` and deliberately
conflicts with `realtek-r8125-dkms` and `r8125-dkms`. An arbitrary unmanaged module
or differently named third-party DKMS provider is not excluded by these names;
preflight must inspect actual module selection and registrations.

The opt revision is included in MODULE_VERSION, so module metadata can identify
the candidate. Package revision updates retain that upstream/DKMS version;
changes to driver releases must update the header, DKMS version and changelog
consistently. Debian lifecycle scripts are generated once by dh-sequence-dkms.
No custom script unloads modules, blacklists r8169 or modifies network policy.
DKMS framework settings and kernel hooks can still change installation behavior.

Build prerequisites are normal Debian packaging tools, debhelper compatibility
level 13 and dh-sequence-dkms. From the source root:

```bash
scripts/build-packages.sh packages
```

This builds an `_all.deb`, unsigned `.dsc`, `.orig.tar.xz`, `.debian.tar.xz`,
`.changes` and `.buildinfo` in the chosen output directory. It does not compile,
install, sign or upload the module. Only the audited manifest is copied into a
pristine source tree. DKMS compilation happens during package installation.

The initial publication target is Ubuntu 26.04 (resolute). Module compile tests
also cover older Ubuntu kernels, but package lifecycle acceptance on those Ubuntu
releases is not implied. BUILD_EXCLUSIVE_KERNEL_MIN requires DKMS >=3.0.11;
Ubuntu 22.04's stock older DKMS is therefore not an initial package target.

A Launchpad account, matching Ubuntu One login, registered signing key and chosen
PPA are publication prerequisites. The archive owner and authorized signing identity must be confirmed before
publication.
Confirm the signing identity and archive access before signing or uploading.
Use an explicitly experimental archive until hardware acceptance is complete.

## Observed local validation

Version: `9.018.00+opt1-0ppa1`, distribution `resolute`. The artifact set includes
the `_all.deb`, unsigned `.dsc`, orig/debian tarballs, binary/source `.changes`
and `.buildinfo`, with complete SHA256SUMS. Lintian reported no errors or warnings.
No source/package signatures have been added.

Hosted GitHub Actions run
[39098921676](https://github.com/pannal/realtek-r8125-dkms-v2/actions/runs/39098921676)
also passed all four module build profiles and the unsigned package checks at
`fa955dc` on 2026-10-18. These jobs do not install or load the driver.

The disposable Ubuntu 26.04 root filesystem used real dpkg/APT, DKMS 3.2.2,
Ubuntu 7.0.0-38 headers/image/modules and GCC 15. Older 5.15/6.8 header/compiler
trees were additional compile fixtures. An unprivileged user/PID/network namespace
and fakeroot ownership emulation isolated test state; live sysfs was absent and
no module was loaded. This is not a booted VM or hardware test.

| Check | Observation |
| --- | --- |
| Artifact contents | Exact audited C/header/Makefile/config payload; no .ko/.o/build debris; source bytes, permissions and all eight checksums checked; .dsc extracted |
| Maintainer scripts | One standard generated DKMS lifecycle, distinct name/version, both known provider conflicts |
| Stock baseline | Published awesometic 9.018.00-1 `.deb` installed through real dpkg/DKMS |
| Conflict refusal | Direct unpack of optimized package refused while stock was installed; stock remained selected |
| APT migration | Explicit local install removed stock registration/module and installed the optimized provider |
| Reinstall | Real DKMS remove/rebuild/install passed; selected module matched DKMS's built bytes |
| Upstream-version upgrade | A test-only `+opt2` source/version fixture replaced `+opt1`; old registration disappeared |
| Downgrade | Reinstall of `+opt1` removed `+opt2` and selected the expected module |
| Rollback | APT restored the actual stock package; selected stock module hash matched the baseline exactly |
| No headers | Package registered as added, with no installed module |
| Header availability | Installation of the real 7.0.0-38 header packages invoked the standard hook and installed the candidate |
| Second ABI | Actual DKMS header hook built/installed against 6.8.0-147 as well |
| Removal/purge | No candidate source tree, registration or installed r8125 file remained; dpkg audit clean |

Module path, version, vermagic, matching built bytes, provider state and absence
of unexpected archived collisions were asserted at each relevant step. The
published stock helper uses DKMS architecture label `amd64`; standard generated
optimized packaging uses `x86_64`. Migration/removal tests covered both labels.
The `+opt2` artifact is solely an upgrade test fixture, not a release candidate.

The local-file APT migration uses ordinary `apt-get install /path/package.deb`
inside an offline namespace. A `--no-download` local-file attempt failed in this
APT version, so that flag is not used for the verified path. Package dependencies
must already be present or included in offline recovery assets.

The rootfs lacked update-secureboot-policy and produced unsigned modules. Secure
Boot acceptance is unverified. A PPA signature would not change that fact.
Package rollback here proves filesystem/DKMS state restoration, not successful
network recovery through a tested independent console on production.

## Reproducing lifecycle checks safely

`tests/package_lifecycle.sh` refuses to run without a disposable-root marker,
without isolated networking, with live sysfs, or when the tested ABI equals the
running kernel. Invoke it only in a prepared expendable root filesystem through
bubblewrap with `--unshare-user --unshare-pid --unshare-net`, an isolated `/dev`
and `/proc`, and no host `/sys`, `/boot` or `/lib/modules` mounts. The root marker
is `/.rtl8125-package-test-root` containing `disposable-rtl8125-test`.

Supply the optimized candidate, public stock package and separately built
version-bump fixture as three local `.deb` arguments. The test expects the
specific header fixtures shown above and real cached 7.0.0-38 header `.deb`s.
It performs destructive package operations **inside that disposable filesystem**;
never run it on a normal workstation or production installation.

Before promoting to stable or replacing a working production driver, complete
booted-system/hardware tests, establish a worthwhile measured benefit over stock
and rehearse independent recovery. Publication authorization permits only an
experimental PPA while those checks remain outstanding. Confirm the Launchpad
archive and registered signing identity before upload. The working production
driver remains the recommendation pending hardware acceptance.
