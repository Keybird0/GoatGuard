#!/usr/bin/env python3
"""
Solana RPC query with provider failover.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from rpc_common import (
    QueryError,
    attempt_provider_operation,
    flatten_attempts,
    json_rpc_request,
    run_subprocess,
    write_json,
    write_text,
)
from rpc_endpoints import build_rpc_pool


def probe_provider(rpc_url: str) -> Any:
    return json_rpc_request(rpc_url, "getSlot", [], timeout=10)


def looks_like_url(value: Optional[str]) -> bool:
    return bool(value) and str(value).startswith(("http://", "https://"))


def collect(mint: str, out_dir: Path | str, rpc_url: Optional[str] = None) -> Dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    providers = build_rpc_pool("solana", explicit=rpc_url or os.environ.get("RPC_URL"))
    report: Dict[str, Any] = {
        "chain": "solana",
        "mint": mint,
        "providers": providers,
        "selected_rpc": None,
        "health_checks": [],
        "operations": {},
        "warnings": [],
    }

    health = attempt_provider_operation(providers, "health:getSlot", probe_provider)
    report["health_checks"] = health["attempts"]
    if not health["success"]:
        report["warnings"].append(f"所有 Solana RPC 不可用: {health['error']}")
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
        error: QueryError = outcome["error"]
        if error.retryable:
            report["warnings"].append(f"{op_name} 失败: {error}")
        raise error

    try:
        mint_info = perform("getAccountInfo", "getAccountInfo", [mint, {"encoding": "jsonParsed"}])
        mint_parsed = (((mint_info or {}).get("value") or {}).get("data") or {}).get("parsed", {}).get("info")
    except QueryError as exc:
        report["warnings"].append(f"Solana 查询失败: {exc}")
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

    try:
        holders = perform("getTokenLargestAccounts", "getTokenLargestAccounts", [mint]) or {}
        holders_value = holders.get("value", [])
    except QueryError as exc:
        report["warnings"].append(f"getTokenLargestAccounts 失败，已降级: {exc}")
        holders_value = []

    try:
        supply = perform("getTokenSupply", "getTokenSupply", [mint]) or {}
        supply_value = supply.get("value", {})
    except QueryError as exc:
        report["warnings"].append(f"getTokenSupply 失败，已降级: {exc}")
        supply_value = {}

    write_json(out_path / "mint-account-info.json", mint_parsed or {})
    write_json(out_path / "holders-top20.json", holders_value)
    write_json(out_path / "token-supply.json", supply_value)

    if run_subprocess(["which", "spl-token"])["returncode"] == 0:
        spl = run_subprocess(
            ["spl-token", "display", mint, "--url", report["selected_rpc"]],
            timeout=30,
        )
        if spl["returncode"] == 0:
            write_text(out_path / "spl-token-display.txt", spl["stdout"])
        else:
            report["warnings"].append("spl-token display 执行失败")
    else:
        report["warnings"].append("spl-token 未安装，已跳过 display 输出")

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
            "mint_account_info": str(out_path / "mint-account-info.json"),
            "holders": str(out_path / "holders-top20.json"),
            "supply": str(out_path / "token-supply.json"),
        },
        "data": {
            "mint_account_info": mint_parsed or {},
            "holders": holders_value,
            "supply": supply_value,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Solana RPC 链上数据直读")
    parser.add_argument("mint", help="Mint 地址")
    parser.add_argument("arg2", nargs="?", default=None, help="兼容参数: RPC URL 或输出目录")
    parser.add_argument("arg3", nargs="?", default=None, help="兼容参数: 输出目录")
    args = parser.parse_args()
    args.rpc_url = None
    args.out_dir = "."
    if args.arg3 is not None:
        args.rpc_url = args.arg2
        args.out_dir = args.arg3
    elif looks_like_url(args.arg2):
        args.rpc_url = args.arg2
    elif args.arg2 is not None:
        args.out_dir = args.arg2
    return args


def main() -> int:
    args = parse_args()
    result = collect(args.mint, args.out_dir, rpc_url=args.rpc_url)
    if not result["success"]:
        for warning in result["warnings"]:
            print(f"⚠️  {warning}")
        return 1
    mint_info = result["data"]["mint_account_info"]
    print("═══════════════════════════════════════════")
    print("  Solana RPC 链上数据直读")
    print(f"  Mint: {args.mint}")
    print(f"  RPC:  {result['selected_rpc']}")
    print("═══════════════════════════════════════════")
    print("")
    print(f"Mint Authority: {mint_info.get('mintAuthority') or '(not set)'}")
    print(f"Freeze Authority: {mint_info.get('freezeAuthority') or '(not set)'}")
    print(f"输出目录: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
