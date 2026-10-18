# RTL8125 validation, PPA deployment and rollback plan

This is a proposed lab/deployment procedure, not an execution record. It grants
no permission to modify the production server. During development, keep the
working package, module, network, routes, offloads and IRQ affinity untouched.

## Recovery gate before a live-driver experiment

Arrange a console that does not depend on the tested NIC, for example verified
BMC/KVM or a person at a local console. An SSH session over the same NIC is not
out-of-band access. Verify console login, elevation, access during network loss,
and access to recovery boot media/kernel entries before scheduling a swap.
Record the exact running kernel, installed provider/package version, DKMS state,
module selection/path/hash, Secure Boot state, firmware and network configuration
in private diagnostic artifacts. Keep host addresses and credentials out of the
source repository and CI artifacts.

Obtain the exact known-good `.deb`, required dependencies, working module and
recovery kernel/initramfs locally on the test system and an independent machine.
Do not rely on Internet/package downloads after the NIC fails. A copied module
alone is insufficient for durable rollback if package/DKMS/initramfs state differs.
Preserve and verify the old module signature and matching kernel vermagic.

On a disposable equivalent system, rehearse both directions:

1. Install the candidate through its intended package path; confirm conflicts
   deliberately remove the old provider and no duplicate DKMS/module selection
   remains. Test all installed kernels that might be booted.
2. Deliberately fail connectivity and restore the exact known-good package,
   DKMS registration, module selection, relevant initramfs and boot choice using
   the independent console. Reboot/reload only under that lab's authorization.
3. Verify restored connectivity, driver identity, module path/hash, link speed,
   default route and workload before declaring rollback tested.
4. If unattended rollback is wanted, implement and test a local, reboot-aware
   deadline mechanism that restores the full known-good state. Test its failure
   path with the NIC unreachable and its cancellation after acceptance. A
   timer that only reboots into the candidate is not rollback.

Record actual rehearsal results and failure triggers. This plan is not a tested
rollback tool. If recovery cannot be demonstrated, stop before any production
write, package installation, unload, rebind or reboot. Each proposed write to the
production host requires explicit approval for that operation.

## Establish a reproducible baseline in the lab

### First activation before reboot

After the recovery gate passes, test the candidate by a separately approved
controlled module reload from the independent console. Keep the exact known-good
package and recovery assets available offline. Installing a package changes the
module on disk; it does not prove that the running module changed. Check the
loaded driver's `+opt1` version, actual queue/vector counts, kernel messages,
connectivity and counters, then run the traffic checks below. Restore the stock
driver immediately if identity, connectivity or error checks fail.

Do not reboot into the candidate before this initial hardware check passes.
A successful reload still leaves boot/initramfs selection and cold-start
behavior unverified; test those later in a separately approved maintenance step.

### Traffic baseline

Use a representative RTL8125 silicon revision and IOMMU configuration, the
production kernel ABI, the known-good 9.018 driver, a peer that sustains more than
2.5 Gbit/s, and a known-good cable/switch path. Record CPU, PCIe link, firmware,
MTU, topology, kernel/toolchain, driver source/artifact hashes and thermal state.
Read and record advertised/active queues, vectors, RSS key/table/hash policy,
coalescing, EEE/ASPM, offloads and CPU/IRQ policy. Keep those settings identical
between A and B; any tuning is a separate experiment.

Use the same network path and peer placement for every run. Keep background
traffic/load controlled and use a fixed warm-up followed by at least five
60–120-second measurements per cell. Alternate baseline/candidate order, then
repeat after a cold boot to expose state/order effects. Retain raw measurements
privately and report median, spread, sample count and interruptions.

| Workload | Measurements and purpose |
| --- | --- |
| TCP single stream, upload and reverse/download | Goodput, retransmissions, driver/NIC drops, CPU time per transferred GiB, per-core softirq cost |
| TCP 4/8 parallel streams and simultaneous bidirectional traffic | Queue distribution, IRQ distribution, aggregate CPU cost, completion/queue stop-wake correctness |
| UDP multiple flows at stepped rates and packet sizes | Loss, reordering, jitter and packet rate; keep default UDP RSS policy unchanged for the first comparison |
| Small packets, mixed sizes and many short-lived connections | Allocation pressure, TX padding/checksum paths, descriptor wrap and RSS flow distribution |
| Idle plus ping/request latency under saturated traffic | p50/p95/p99 latency and latency-throughput tradeoff, rather than judging only bulk goodput |
| Large verified file transfers in both directions | End-to-end content hashes, not only transport throughput |
| Extended mixed workload, then link loss/recovery | At least a 24-hour lab soak; watchdogs, DMA faults, resets, leaks, queue stalls and recovery |

Example **lab-only** iperf3 client runs (replace the peer placeholder):

```text
iperf3 -c LAB_PEER -t 120 -O 10 -P 1 --json
iperf3 -c LAB_PEER -t 120 -O 10 -P 1 -R --json
iperf3 -c LAB_PEER -t 120 -O 10 -P 4 --json
iperf3 -c LAB_PEER -t 120 -O 10 -P 4 -R --json
iperf3 -c LAB_PEER -t 120 -O 10 --bidir --json
```

Measure counters before and after each run, including `ethtool -S`, link/interface
statistics, per-vector `/proc/interrupts`, softirq counters and CPU utilization.
Inspect `ethtool -l`/`-x` where supported, but validate distribution with observed
traffic and counters rather than treating configuration output as delivery proof.
The driver may expose fewer queue statistics than needed; record that limitation
or add separately reviewed lab instrumentation. Do not change production affinity,
routes or offloads to make a comparison look better.

The historical approximately 2.37 Gbit/s is a reference report, not a new
baseline; its MTU was not supplied. Ethernet/TCP overhead means 2.5 Gbit/s line rate is not an application
goodput target at that MTU. First require data integrity, stable connectivity, no
new errors/stalls and no meaningful CPU/latency/goodput regression. Claim a gain
only if it exceeds run-to-run variation and survives the reversed A/B order.

## Fault and feature coverage

On expendable hardware, cover 1/2/3/4/8 CPU availability, supported RX/TX queue
counts, scarce-vector fallback, no usable IRQ allocation, reset and interface
open/close cycles. Use supported fault injection/debug kernels for allocation
and DMA errors, memory pressure and concurrency; host mocks do not replace this.
Verify power-of-two RSS selection and every indirection entry against the actual
active rings. Do not force the known-invalid CP 49-vector layout.

Exercise MTU 1500 first; test jumbo end to end separately. Add IPv4/IPv6 TCP/UDP,
VLAN, fragmented packets, checksum/segmentation offloads, link-speed changes,
EEE/ASPM and wake features as separate controlled cells. Optional PTP requires
actual timestamp/clock validation. A PTP-enabled compilation is not PTP success.

## Proposed PPA distribution and production installation

Use a dedicated Launchpad PPA with an explicitly named optimized DKMS package.
Start with an opt-in testing archive; promote only validated source versions to
a stable archive. Pin accepted source commits and publish a changelog including
hardware-tested kernels/revisions and known limitations. Source-package signatures
and APT archive verification are separate from Secure Boot module signing.

Before any upload, finalize package identity/versioning, conflict/migration rules,
source provenance and generated maintainer scripts; validate the complete DKMS
lifecycle in disposable Ubuntu environments. Do not enable an automated publishing
workflow while runtime acceptance is outstanding. The current CI retains uninstalled `.ko` build evidence and separately builds
and inspects unsigned packages. It does not install, release or upload packages
to an APT repository or PPA.

For the production server, prepare exact commands from the resulting validated
package and observed installed state. The eventual maintenance window consists of
separately approved operations: stage offline recovery assets, add the verified
PPA/key configuration, install the chosen exact package version as a deliberate
replacement, and activate it from the independent console. Package install and
driver activation are separate effects; a successful APT operation does not prove
the running module changed. Verify the loaded candidate identity and queue/IRQ
behavior before acceptance or cancellation of any tested rollback deadline.

Do not run inherited `autorun.sh` or ad hoc module replacement over SSH. The
legacy install/remove helpers on this branch are disabled. Explicit `make install`
and Debian/DKMS maintainer operations are still state-changing and are outside
this development task. Experimental PPA publication is authorized with the
pre-publication runtime gate explicitly waived; production writes remain subject
to individual approval. No production operation in this procedure has been performed.
