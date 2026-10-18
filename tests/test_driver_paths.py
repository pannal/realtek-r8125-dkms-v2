#!/usr/bin/env python3
"""Host-side control-flow tests of extracted driver C, with mocked kernel services.

These exercise failure contracts; they do not emulate DMA, IRQ delivery or hardware.
The module builds separately against real kernel headers to check API compatibility.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(os.environ.get("R8125_SOURCE_ROOT", Path(__file__).resolve().parents[1]))
SOURCE = (ROOT / "src/r8125_n.c").read_text()
HEADER = (ROOT / "src/r8125.h").read_text()


def function(name):
    match = re.search(r"^.*\b" + name + r"\([^;]*?\)\n\{", SOURCE, re.M)
    if not match:
        raise AssertionError(f"Definition missing: {name}")
    end = match.end()
    depth = 1
    while depth:
        depth += (SOURCE[end] == "{") - (SOURCE[end] == "}")
        end += 1
    return SOURCE[match.start():end]


PREAMBLE = r"""
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#define KERNEL_VERSION(a,b,c) (((a)<<16)+((b)<<8)+(c))
#define LINUX_VERSION_CODE KERNEL_VERSION(7,0,0)
#define ETH_ZLEN 60
#define min(a,b) ((a)<(b)?(a):(b))
#define clamp_val(x,a,b) ((x)<(a)?(a):((x)>(b)?(b):(x)))
typedef uint16_t u16;
"""


def run_c(code):
    with tempfile.TemporaryDirectory(prefix="r8125-test-") as temp:
        src = Path(temp) / "probe.c"
        binary = Path(temp) / "probe"
        src.write_text(PREAMBLE + code)
        subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra",
                        "-Werror", "-Wno-unused-parameter", "-Wno-unused-function", str(src), "-o", str(binary)],
                       check=True)
        subprocess.run([str(binary)], check=True)


class DriverPaths(unittest.TestCase):
    def test_padding_failure_keeps_caller_ownership(self):
        run_c(r"""
struct sk_buff { unsigned len; int frees; };
static bool fail_alloc;
static int __skb_put_padto(struct sk_buff *s, unsigned len, bool free_on_error) {
    if (s->len >= len) return 0;
    if (fail_alloc) { s->frees += free_on_error; return -12; }
    s->len = len; return 0;
}
/* Older helpers consume on error; keep both contracts for baseline checks. */
static int skb_padto(struct sk_buff *s, unsigned len) {
    if (s->len >= len || !fail_alloc) return 0;
    s->frees++; return -12;
}
static void skb_put(struct sk_buff *s, unsigned len) { s->len += len; }
static int eth_skb_pad(struct sk_buff *s) { return __skb_put_padto(s, ETH_ZLEN, true); }
""" + function("rtl8125_skb_pad_with_len") + function("rtl8125_skb_pad") + r"""
int main(void) {
    struct sk_buff s = {42, 0};
    fail_alloc = true;
    assert(!rtl8125_skb_pad(&s));
    assert(s.len == 42 && s.frees == 0);
    s.frees++; /* start_xmit's error path remains sole owner */
    assert(s.frees == 1);
    s = (struct sk_buff){42, 0}; fail_alloc = false;
    assert(rtl8125_skb_pad(&s) && s.len == 60 && s.frees == 0);
    assert(rtl8125_skb_pad_with_len(&s, 80) && s.len == 80);
    assert(rtl8125_skb_pad_with_len(&s, 60) && s.len == 80);
    return 0;
}
""")

    def test_irq_allocation_failure_and_fallbacks(self):
        constants = "\n".join(re.findall(r"^#define R8125_(?:MIN|MAX)_MSIX_VEC[^\n]*", HEADER, re.M))
        constants += "\n" + "\n".join(f"#define CFG_METHOD_{i} {i}" for i in range(2, 18))
        run_c(constants + r"""
#define RTL_USE_NEW_INTR_API
#define RTL_FEATURE_MSIX 1
#define RTL_FEATURE_MSI 2
#define PCI_IRQ_MSIX 1
#define PCI_IRQ_ALL_TYPES 7
struct pci_dev { int dev; };
struct rtl8125_private {
    struct pci_dev *pci_dev;
    unsigned mcfg, hw_supp_irq_nvecs, max_irq_nvecs, min_irq_nvecs;
    unsigned irq_nvecs, features;
};
static int calls, results[2], msi_enabled;
static int pci_alloc_irq_vectors(struct pci_dev *p, unsigned minv, unsigned maxv, int flags) {
    assert(minv > 0 && maxv > 0);
    return results[calls++];
}
static int pci_dev_msi_enabled(struct pci_dev *p) { return msi_enabled; }
#define dev_info(...) ((void)0)
""" + function("rtl8125_try_msi") + r"""
int main(void) {
    struct pci_dev p = {0};
    struct rtl8125_private t = {.pci_dev=&p, .mcfg=CFG_METHOD_4};
    results[0]=-28; results[1]=-12;
    assert(rtl8125_try_msi(&t) == -12 && calls == 2 && t.features == 0);
    calls=0; results[0]=32;
    assert(rtl8125_try_msi(&t) == 32 && calls == 1 && t.features == RTL_FEATURE_MSIX);
    t.features=0; calls=0; results[0]=-28; results[1]=1; msi_enabled=1;
    assert(rtl8125_try_msi(&t) == 1 && calls == 2 && t.features == RTL_FEATURE_MSI);
    t.features=0; calls=0; msi_enabled=0;
    assert(rtl8125_try_msi(&t) == 1 && calls == 2 && t.features == 0 && t.irq_nvecs == 1);
    return 0;
}
""")

    def test_aux_napi_budget_and_completion_ownership(self):
        run_c(r"""
struct napi_struct { int unused; };
struct net_device { int unused; };
struct rtl8125_private { struct net_device *dev; };
struct r8125_napi { struct napi_struct napi; struct rtl8125_private *priv; int index; };
typedef struct napi_struct *napi_ptr;
typedef int napi_budget;
static int completes, rearms, work, allow_complete;
#define RTL_GET_PRIV(n, type) ((type *)(n))
#define RTL_GET_NETDEV(p) struct net_device *dev = (p)->dev;
#define RTL_NAPI_QUOTA(b,d) (b)
static bool complete(int done) { completes++; work=done; return allow_complete; }
#define RTL_NETIF_RX_COMPLETE(d,n,w) complete(w)
static void rtl8125_enable_hw_interrupt_v2(struct rtl8125_private *t, int i) { rearms++; }
""" + function("rtl8125_poll_msix_other") + r"""
int main(void) {
    struct rtl8125_private t={0}; struct r8125_napi n={.priv=&t};
    assert(rtl8125_poll_msix_other(&n.napi,0) == 0 && completes == 0 && rearms == 0);
    assert(rtl8125_poll_msix_other(&n.napi,64) == 0 && completes == 1 && rearms == 0 && work == 0);
    allow_complete=1;
    assert(rtl8125_poll_msix_other(&n.napi,64) == 0 && completes == 2 && rearms == 1 && work == 0);
    return 0;
}
""")

    def test_software_checksum_failure_is_rejected(self):
        start = SOURCE.index("        if (sw_calc_csum) {")
        end = SOURCE.index("\n}", start)
        run_c(r"""
static int result, calls;
static int skb_checksum_help(void *skb) { calls++; return result; }
static bool prepare(void) {
    bool sw_calc_csum=true; void *skb=0; unsigned opts[2]={0}, csum_cmd=0;
""" + SOURCE[start:end] + r"""
}
int main(void) {
    result=-12; assert(!prepare() && calls==1);
    result=0; assert(prepare() && calls==2);
    return 0;
}
""")

    def test_rss_queue_encoding_and_indirection_bounds(self):
        # Compile the actual selection block rather than a rewritten algorithm.
        start = SOURCE.index("                u16 rss_queue_num = netif_get_num_default_rss_queues();")
        end = SOURCE.index("\n        }", start)
        block = SOURCE[start:end]
        run_c(r"""
struct rtl8125_private { u16 HwSuppNumRxQueues, num_rx_rings, irq_nvecs; bool EnableRss; };
static u16 cpus;
static u16 netif_get_num_default_rss_queues(void) { return cpus; }
static unsigned rounddown_pow_of_two(unsigned n) { assert(n); return 1U << (31-__builtin_clz(n)); }
static void select_queues(struct rtl8125_private *tp) {
""" + block + r"""
}
int main(void) {
    for (unsigned hw=1; hw<=8; hw*=2) for (cpus=0; cpus<=16; cpus++) {
        struct rtl8125_private t={.HwSuppNumRxQueues=hw,.num_rx_rings=1,.irq_nvecs=32};
        select_queues(&t);
        unsigned q=t.num_rx_rings;
        assert(q && !(q & (q-1)) && q<=hw);
        if (cpus) assert(q<=cpus);
        assert(t.EnableRss == (q>=2));
        /* 128-entry default RETA and log2 queue encoding agree. */
        for (unsigned i=0; i<128; i++) assert(i%q < (1U << __builtin_ctz(q)));
    }
    cpus=3; struct rtl8125_private t={.HwSuppNumRxQueues=4,.num_rx_rings=1,.irq_nvecs=32};
    select_queues(&t); assert(t.num_rx_rings == 2);
    cpus=4; t=(struct rtl8125_private){.HwSuppNumRxQueues=4,.num_rx_rings=1,.irq_nvecs=1};
    select_queues(&t); assert(t.num_rx_rings == 1 && !t.EnableRss);
    return 0;
}
""")

    def test_napi_registration_mapping(self):
        run_c(r"""
#define CONFIG_R8125_NAPI
#define RTL_FEATURE_MSIX 1
#define R8125_MAX_RX_QUEUES_VEC_V3 16
#define R8125_NAPI_WEIGHT 64
struct napi_struct { int tx; int (*poll)(struct napi_struct *, int); };
struct rtl8125_private;
struct r8125_napi { struct napi_struct napi; struct rtl8125_private *priv; int index; };
struct rtl8125_private { void *dev; int irq_nvecs, features, HwCurrIsrVer; struct r8125_napi r8125napi[32]; };
#define POLL(name) static int name(struct napi_struct *n, int b) { return 0; }
POLL(rtl8125_poll)
POLL(rtl8125_poll_msix_tx)
POLL(rtl8125_poll_msix_rx)
POLL(rtl8125_poll_msix_ring)
POLL(rtl8125_poll_msix_other)
static void netif_napi_add_tx_weight(void *dev,struct napi_struct *n,int (*p)(struct napi_struct *,int),int w) { n->tx=1;n->poll=p; }
static void normal_add(struct r8125_napi *n,int (*p)(struct napi_struct *,int)) { n->napi.tx=0;n->napi.poll=p; }
#define RTL_NAPI_CONFIG(d,n,p,w) normal_add(n,p)
""" + function("rtl8125_init_napi") + r"""
int main(void) {
    for (int version=1;version<=7;version++) for(int msix=0;msix<=1;msix++) {
        struct rtl8125_private t={.irq_nvecs=32,.features=msix,.HwCurrIsrVer=version};
        rtl8125_init_napi(&t);
        for(int i=0;i<32;i++) {
            struct r8125_napi *n=t.r8125napi+i;
            assert(n->priv==&t && n->index==i);
            int tx=msix&&((version==2&&(i==16||i==18))||(version==5&&(i==16||i==17))||(version==7&&(i==27||i==28)));
            assert(n->napi.tx==tx);
            if(tx) assert(n->napi.poll==rtl8125_poll_msix_tx);
            else if(!msix||version==1||version==6) assert(n->napi.poll==rtl8125_poll);
            else if(i<16) assert(n->napi.poll==((version==3||version==4)?rtl8125_poll_msix_ring:rtl8125_poll_msix_rx));
            else assert(n->napi.poll==rtl8125_poll_msix_other);
        }
    }
    return 0;
}
""")


if __name__ == "__main__":
    unittest.main(verbosity=2)
