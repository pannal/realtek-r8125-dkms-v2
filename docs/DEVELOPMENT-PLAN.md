# 9.018 optimization development plan

Task: source port and compile-only validation. No installation, module loading,
production configuration changes, package publication or push is authorized.

Done means an isolated `realtek-9.018-optimized` branch descended from awesometic
9.018, a linked module against Ubuntu 7.0.0-38-generic, build-only CI, bounded
source comparison, packaging guidance, benchmark and recovery procedures.
Hardware correctness and a tested recovery route require separate lab work.

## Evidence and approach

- Baseline: awesometic/master `9a152bf920334aead090d2fb4d91f67a84923123`.
- Donor: ewaldc/master `527bcbe5ed45c67b20abae73dccc683eb6f0dc2b`.
- Historical branch: origin/kernel-7-compat
  `f3f4b5b8298f12a6ef4fc69fda275b24ff9da725`; preserve it.
- Existing port notes were read from that branch; no target checkout existed
  on this workstation. New worktrees isolate both sources.
- 9.018 `src/Makefile` already forwards EXTRA_CFLAGS into ccflags-y. Standardize
  on ccflags-y directly; measure the baseline rather than assuming it fails.
- Keep 9.018 page reuse, newer hardware methods, DMA handles, fragment unwind,
  completion limits, GSO accounting and offload validation. Donor DMA-to-physical
  conversions and broad defaults are unsuitable for a selective forward port.
- Port TX-only NAPI registration and IRQ allocation error propagation; fix the
  RSS power-of-two mismatch and narrowly scoped TX/NAPI failure paths found in
  review. Leave moderation defaults for measurement.

Scope: src/Makefile, src/r8125_n.c, build-only scripts/tests and workflow,
README, legacy installer helpers and docs. Retire the inherited release workflow
on this development branch so it cannot accidentally publish an unvalidated package. No package
rename or installation change implies safe coexistence of modules.

## Checklist

- [x] Inspect target/ref histories and historical notes; create isolated branch.
- [x] Parallel read-only source reviews: queues/IRQ/RSS and DMA/TX/offloads.
- [x] Compile unchanged baseline against exact Ubuntu headers.
- [x] Implement bounded enablement and reliability changes.
- [x] Run module builds and meaningful failure-path regression checks.
- [x] Add Ubuntu kernel matrix without install/load steps.
- [x] Document comparison, evidence, limits, packaging, benchmarks and rollback.
- [x] Independent adversarial review and reproducible final checks.
- [x] Commit verified local changes; preserve 9.014 refs; do not push.

Risks: no target RTL8125 or production access in this session; compiler success
cannot prove RSS distribution, interrupt delivery, DMA safety or performance.
Exact PCI revision/method, Secure Boot policy and independent recovery are not
established by the reported PCI device/subsystem IDs. Do not guess CP vector
layouts or transplant donor defaults without evidence.

Review-driven scope update: making `all` compile-only invalidates autorun.sh's
implicit installation step while it still unloads NIC modules. Replace legacy
install/remove helpers with immediate non-mutating failures. Keep future DKMS
packaging a separately validated, explicitly authorized replacement deployment.

Verification outcome: six executable source-extracted regressions pass and fail
on unchanged baseline; four kernel/PTP profiles link and independent review
reproduced the original five tests and all four builds. The sixth mapping test
was supplied and exercised independently, then included and rerun in the main
suite. Final artifacts are generated from the committed source; hardware,
packaging lifecycle, hosted CI and recovery rehearsal remain pending.

Distribution decision: use a Launchpad PPA after package/lab validation, with a
distinct optimized DKMS package and explicit provider conflicts. Preparing and
validating that package is the next milestone; nothing is published or installed.
