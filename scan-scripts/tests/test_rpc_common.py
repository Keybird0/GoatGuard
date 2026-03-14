import sys
import unittest
from pathlib import Path


SCAN_SCRIPT_DIR = Path(__file__).resolve().parents[1]
if str(SCAN_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_SCRIPT_DIR))

from rpc_common import QueryError, attempt_provider_operation


class RpcCommonTests(unittest.TestCase):
    def test_attempt_provider_operation_falls_back_on_retryable_error(self):
        providers = ["rpc-1", "rpc-2"]

        def operation(provider: str):
            if provider == "rpc-1":
                raise QueryError("timeout", retryable=True, kind="transport")
            return "ok"

        result = attempt_provider_operation(providers, "health", operation)
        self.assertTrue(result["success"])
        self.assertEqual(result["provider"], "rpc-2")
        self.assertEqual(len(result["attempts"]), 2)
        self.assertFalse(result["attempts"][0]["success"])
        self.assertTrue(result["attempts"][1]["success"])

    def test_attempt_provider_operation_stops_on_non_retryable_error(self):
        providers = ["rpc-1", "rpc-2"]

        def operation(provider: str):
            if provider == "rpc-1":
                raise QueryError("revert", retryable=False, kind="business")
            return "ok"

        result = attempt_provider_operation(providers, "call", operation)
        self.assertFalse(result["success"])
        self.assertEqual(result["provider"], "rpc-1")
        self.assertEqual(len(result["attempts"]), 1)


if __name__ == "__main__":
    unittest.main()
