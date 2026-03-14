#!/usr/bin/env python3
"""
Sui RPC query with provider failover.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rpc_common import QueryError, attempt_provider_operation, flatten_attempts, json_rpc_request, write_json
from rpc_endpoints import build_rpc_pool


def probe_provider(rpc_url: str) -> Any:
    return json_rpc_request(rpc_url, "sui_getLatestCheckpointSequenceNumber", [], timeout=10)


def looks_like_path(value: Optional[str]) -> bool:
    if not value:
        return False
    text = str(value)
    return "/" in text or text.startswith(".")


def collect(
    coin_type: str,
    package_id: Optional[str],
    out_dir: Path | str,
    *,
    rpc_url: Optional[str] = None,
    treasury_cap_id: Optional[str] = None,
    upgrade_cap_id: Optional[str] = None,
    metadata_id: Optional[str] = None,
) -> Dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    providers = build_rpc_pool("sui", explicit=rpc_url or os.environ.get("RPC_URL"))
    report: Dict[str, Any] = {
        "chain": "sui",
        "coin_type": coin_type,
        "package_id": package_id,
        "providers": providers,
        "selected_rpc": None,
        "health_checks": [],
        "operations": {},
        "warnings": [],
    }

    health = attempt_provider_operation(providers, "health:sui_getLatestCheckpointSequenceNumber", probe_provider)
    report["health_checks"] = health["attempts"]
    if not health["success"]:
        report["warnings"].append(f"所有 Sui RPC 不可用: {health['error']}")
        report_path = out_path / "rpc-provider-report.json"
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": report["warnings"],
            "selected_rpc": None,
            "rpc_attempts": flatten_attempts({"health_checks": report["health_checks"]}),
            "provider_failures": [
                attempt for attempt in report["health_checks"] if (not attempt["success"] and attempt.get("retryable"))
            ],
            "outputs": {"provider_report": str(report_path)},
            "data": None,
        }

    current_index = health["provider_index"]
    report["selected_rpc"] = health["provider"]

    def perform(op_name: str, method: str, params: List[Any], timeout: int = 20) -> Any:
        nonlocal current_index
        outcome = attempt_provider_operation(
            providers,
            op_name,
            lambda provider: json_rpc_request(provider, method, params, timeout=timeout),
            start_index=current_index,
        )
        report["operations"][op_name] = outcome["attempts"]
        if outcome["success"]:
            current_index = outcome["provider_index"]
            report["selected_rpc"] = outcome["provider"]
            return outcome["result"]
        raise outcome["error"]

    try:
        metadata = perform("suix_getCoinMetadata", "suix_getCoinMetadata", [coin_type])
        supply = perform("suix_getTotalSupply", "suix_getTotalSupply", [coin_type])
        write_json(out_path / "sui-coin-metadata.json", {"result": metadata})
        write_json(out_path / "sui-total-supply.json", {"result": supply})

        if treasury_cap_id:
            treasury = perform(
                "sui_getObject:treasury_cap",
                "sui_getObject",
                [treasury_cap_id, {"showType": True, "showOwner": True, "showContent": True}],
            )
            write_json(out_path / "sui-treasury-cap.json", {"result": treasury})
        if upgrade_cap_id:
            upgrade = perform(
                "sui_getObject:upgrade_cap",
                "sui_getObject",
                [upgrade_cap_id, {"showType": True, "showOwner": True, "showContent": True}],
            )
            write_json(out_path / "sui-upgrade-cap.json", {"result": upgrade})
        if metadata_id:
            metadata_object = perform(
                "sui_getObject:metadata",
                "sui_getObject",
                [metadata_id, {"showType": True, "showOwner": True, "showContent": True}],
            )
            write_json(out_path / "sui-coin-metadata-object.json", {"result": metadata_object})
        if package_id:
            modules = perform(
                "sui_getNormalizedMoveModulesByPackage",
                "sui_getNormalizedMoveModulesByPackage",
                [package_id],
                timeout=30,
            )
            write_json(out_path / "sui-modules.json", {"result": modules})
    except QueryError as exc:
        report["warnings"].append(f"Sui 查询失败: {exc}")
        report_path = out_path / "rpc-provider-report.json"
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": report["warnings"],
            "selected_rpc": report["selected_rpc"],
            "rpc_attempts": flatten_attempts({"health_checks": report["health_checks"], **report["operations"]}),
            "provider_failures": [
                attempt
                for attempt in flatten_attempts({"health_checks": report["health_checks"], **report["operations"]})
                if (not attempt["success"] and attempt.get("retryable"))
            ],
            "outputs": {"provider_report": str(report_path)},
            "data": None,
        }

    report_path = out_path / "rpc-provider-report.json"
    write_json(report_path, report)
    return {
        "success": True,
        "warnings": report["warnings"],
        "selected_rpc": report["selected_rpc"],
        "rpc_attempts": flatten_attempts({"health_checks": report["health_checks"], **report["operations"]}),
        "provider_failures": [
            attempt
            for attempt in flatten_attempts({"health_checks": report["health_checks"], **report["operations"]})
            if (not attempt["success"] and attempt.get("retryable"))
        ],
        "outputs": {
            "provider_report": str(report_path),
            "coin_metadata": str(out_path / "sui-coin-metadata.json"),
            "total_supply": str(out_path / "sui-total-supply.json"),
            "modules": str(out_path / "sui-modules.json") if package_id else None,
        },
        "data": {
            "coin_metadata": metadata,
            "total_supply": supply,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sui RPC 链上数据直读")
    parser.add_argument("coin_type", help="COIN_TYPE")
    parser.add_argument("arg2", nargs="?", default=None, help="兼容参数: package ID 或输出目录")
    parser.add_argument("arg3", nargs="?", default=None, help="兼容参数: 输出目录")
    parser.add_argument("--rpc-url", default=None, help="可选单个 RPC URL")
    args = parser.parse_args()
    args.package_id = ""
    args.out_dir = "."
    if args.arg3 is not None:
        args.package_id = args.arg2 or ""
        args.out_dir = args.arg3
    elif looks_like_path(args.arg2):
        args.out_dir = args.arg2 or "."
    elif args.arg2 is not None:
        args.package_id = args.arg2
    return args


def main() -> int:
    args = parse_args()
    result = collect(
        args.coin_type,
        args.package_id or None,
        args.out_dir,
        rpc_url=args.rpc_url or os.environ.get("SUI_RPC_URL") or os.environ.get("RPC_URL"),
        treasury_cap_id=os.environ.get("TREASURY_CAP_ID"),
        upgrade_cap_id=os.environ.get("UPGRADE_CAP_ID"),
        metadata_id=os.environ.get("METADATA_ID"),
    )
    if not result["success"]:
        for warning in result["warnings"]:
            print(f"⚠️  {warning}")
        return 1
    print("═══════════════════════════════════════════")
    print("  Sui RPC 链上数据直读")
    print(f"  CoinType: {args.coin_type}")
    print(f"  RPC:      {result['selected_rpc']}")
    print("═══════════════════════════════════════════")
    print(f"输出目录: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
