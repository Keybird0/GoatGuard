#!/usr/bin/env bash
# -*- coding: UTF-8 -*-

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$SCRIPT_DIR/solana_rpc_query.py" "$@"
