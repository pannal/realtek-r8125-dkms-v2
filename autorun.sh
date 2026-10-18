#!/bin/sh
# SPDX-License-Identifier: GPL-2.0-only
printf '%s\n' 'This development branch supports build-only validation.' \
    'Installation/removal helpers are disabled; see docs/BENCHMARK-AND-ROLLBACK.md.' >&2
exit 1
