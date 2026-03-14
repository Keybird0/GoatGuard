#!/usr/bin/env python3
"""
RPC endpoint pools and environment resolution.
"""

from __future__ import annotations

import os
from typing import Iterable, List, Optional


DEFAULT_RPC_POOLS = {
    "ethereum": [
        "https://ethereum-rpc.publicnode.com",
        "https://cloudflare-eth.com",
        "https://eth.llamarpc.com",
    ],
    "bsc": [
        "https://bsc-dataseed.binance.org",
        "https://bsc-rpc.publicnode.com",
        "https://bsc.llamarpc.com",
    ],
    "polygon": [
        "https://polygon-rpc.com",
        "https://polygon-bor-rpc.publicnode.com",
        "https://polygon.llamarpc.com",
    ],
    "arbitrum": [
        "https://arb1.arbitrum.io/rpc",
        "https://arbitrum-one-rpc.publicnode.com",
        "https://arbitrum.llamarpc.com",
    ],
    "optimism": [
        "https://mainnet.optimism.io",
        "https://optimism-rpc.publicnode.com",
        "https://optimism.llamarpc.com",
    ],
    "base": [
        "https://mainnet.base.org",
        "https://base-rpc.publicnode.com",
        "https://base.llamarpc.com",
    ],
    "avalanche": [
        "https://api.avax.network/ext/bc/C/rpc",
        "https://avalanche-c-chain-rpc.publicnode.com",
        "https://avax.meowrpc.com",
    ],
    "solana": [
        "https://api.mainnet-beta.solana.com",
        "https://solana-rpc.publicnode.com",
    ],
    "sui": [
        "https://fullnode.mainnet.sui.io:443",
        "https://rpc.mainnet.sui.io:443",
    ],
}


SINGLE_RPC_ENV = {
    "ethereum": "ETH_RPC_URL",
    "bsc": "BSC_RPC_URL",
    "polygon": "POLYGON_RPC_URL",
    "arbitrum": "ARB_RPC_URL",
    "optimism": "OP_RPC_URL",
    "base": "BASE_RPC_URL",
    "avalanche": "AVAX_RPC_URL",
    "solana": "SOLANA_RPC_URL",
    "sui": "SUI_RPC_URL",
}


MULTI_RPC_ENV = {
    "ethereum": "ETH_RPC_URLS",
    "bsc": "BSC_RPC_URLS",
    "polygon": "POLYGON_RPC_URLS",
    "arbitrum": "ARB_RPC_URLS",
    "optimism": "OP_RPC_URLS",
    "base": "BASE_RPC_URLS",
    "avalanche": "AVAX_RPC_URLS",
    "solana": "SOLANA_RPC_URLS",
    "sui": "SUI_RPC_URLS",
}


def unique(items: Iterable[str]) -> List[str]:
    seen = set()
    ordered: List[str] = []
    for item in items:
        value = item.strip()
        if value and value not in seen:
            ordered.append(value)
            seen.add(value)
    return ordered


def split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return unique(part.strip() for part in value.split(",") if part.strip())


def build_rpc_pool(chain: str, explicit: Optional[str] = None, env: Optional[dict] = None) -> List[str]:
    env_map = env or os.environ
    pool: List[str] = []
    if explicit:
        pool.append(explicit)
    single_env = SINGLE_RPC_ENV.get(chain)
    if single_env and env_map.get(single_env):
        pool.append(env_map[single_env])
    multi_env = MULTI_RPC_ENV.get(chain)
    if multi_env and env_map.get(multi_env):
        pool.extend(split_csv(env_map[multi_env]))
    pool.extend(DEFAULT_RPC_POOLS.get(chain, []))
    return unique(pool)
