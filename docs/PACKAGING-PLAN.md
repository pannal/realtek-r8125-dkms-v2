# PPA packaging milestone

User authorized preparation and disposable packaging validation after the
source/build milestone. Experimental publication is now explicitly authorized;
production writes remain unauthorized.

Done: a distinct optimized DKMS source/binary package, inspectable PPA source
artifacts, and observed installation, rebuild, upgrade, removal/purge and rollback
behavior in an isolated Ubuntu environment. Any VM/hardware or signing tests not
performed must remain explicit limits. The owner waived the runtime gate for
experimental publication on 2026-10-18; stable promotion still requires acceptance.

Scope: debian/, dkms.conf, package-building/lifecycle tooling, relevant workflow
and documentation. Preserve the verified driver source from f07eec4.

- [x] Start isolated packaging branch from verified source commit.
- [x] Inspect current dh-dkms lifecycle and alternate provider identities.
- [x] Implement distinct package/DKMS identity and conflict/version rules.
- [x] Build binary and unsigned source packages with explicit content selection.
- [x] Exercise real dpkg/DKMS lifecycle in disposable root filesystem.
- [x] Inspect artifacts/maintainer scripts and independently review.
- [x] Update evidence/limitations, commit locally and integrate source branch.

Risks: both packages produce r8125.ko; names cannot establish coexistence.
Namespace/rootfs lifecycle testing cannot prove boot, module loading, Secure Boot,
NIC operation, or a tested production recovery path. No fake module success or
suppressed dependency checks may be reported as package lifecycle validation.

Local rootfs tests passed with real packages and DKMS; no booted VM/hardware test
was substituted or claimed. No measured performance benefit or necessity to
replace the healthy production driver has been established. Local unsigned
artifacts are preparation only; signing/archive access and production recovery
remain outstanding. Test a controlled activation before any reboot into the candidate.
