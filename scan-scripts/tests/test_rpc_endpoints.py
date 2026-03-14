import sys
import unittest
from pathlib import Path


SCAN_SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_SCRIPT_DIR))

from rpc_endpoints import DEFAULT_RPC_POOLS, build_rpc_pool


class RpcEndpointTests(unittest.TestCase):
    def test_build_rpc_pool_respects_priority_and_dedupes(self):
        env = {
            "ETH_RPC_URL": "https://single.example",
            "ETH_RPC_URLS": "https://multi-one.example,https://single.example,https://multi-two.example",
        }
        pool = build_rpc_pool("ethereum", explicit="https://explicit.example", env=env)
        self.assertEqual(
            pool[:4],
            [
                "https://explicit.example",
                "https://single.example",
                "https://multi-one.example",
                "https://multi-two.example",
            ],
        )
        self.assertTrue(any(item in pool for item in DEFAULT_RPC_POOLS["ethereum"]))

    def test_build_rpc_pool_uses_defaults_when_env_missing(self):
        pool = build_rpc_pool("solana", explicit=None, env={})
        self.assertEqual(pool, DEFAULT_RPC_POOLS["solana"])


if __name__ == "__main__":
    unittest.main()
