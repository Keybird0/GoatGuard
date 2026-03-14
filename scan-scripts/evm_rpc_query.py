#!/usr/bin/env python3
"""
EVM RPC query with provider failover and structured outputs.
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from rpc_common import (
    QueryError,
    attempt_provider_operation,
    classify_text_error,
    flatten_attempts,
    json_rpc_request,
    run_subprocess,
    write_json,
)
from rpc_endpoints import build_rpc_pool


EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"


def probe_provider(rpc_url: str) -> Any:
    return json_rpc_request(rpc_url, "eth_chainId", [], timeout=10)


def cast_supports(subcommand: str) -> bool:
    result = run_subprocess(["cast", subcommand, "--help"], timeout=10)
    return result["returncode"] == 0


def looks_like_url(value: Optional[str]) -> bool:
    return bool(value) and str(value).startswith(("http://", "https://"))


def unwrap_cast_string(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def parse_int_maybe(value: str) -> Optional[int]:
    match = re.match(r"^\s*(\d+)", value or "")
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def normalize_storage_address(value: str) -> str:
    stripped = value.strip().lower()
    if not stripped.startswith("0x") or len(stripped) < 42:
        return "N/A"
    addr = "0x" + stripped[-40:]
    if addr == ZERO_ADDRESS:
        return ZERO_ADDRESS
    return addr


def run_cast(command: Sequence[str], *, timeout: int = 20) -> str:
    result = run_subprocess(command, timeout=timeout, env=os.environ.copy())
    output = (result["stdout"] or "").strip()
    error = (result["stderr"] or "").strip()
    if result["returncode"] != 0:
        message = error or output or "cast command failed"
        raise classify_text_error(message)
    return output


def collect(address: str, chain: str, out_dir: Path | str, rpc_url: Optional[str] = None) -> Dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    providers = build_rpc_pool(chain, explicit=rpc_url or os.environ.get("RPC_URL"))
    report: Dict[str, Any] = {
        "chain": chain,
        "address": address,
        "providers": providers,
        "selected_rpc": None,
        "health_checks": [],
        "operations": {},
        "warnings": [],
        "cast_capabilities": {},
    }

    if not shutil_which_cast():
        report["warnings"].append("cast 未安装，无法执行 EVM RPC 查询")
        report_path = out_path / "rpc-provider-report.json"
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": report["warnings"],
            "selected_rpc": None,
            "rpc_attempts": [],
            "provider_failures": [],
            "outputs": {"provider_report": str(report_path)},
            "data": None,
        }

    report["cast_capabilities"] = {
        "source": cast_supports("source"),
        "etherscan_source": cast_supports("etherscan-source"),
        "implementation": cast_supports("implementation"),
        "admin": cast_supports("admin"),
        "storage": cast_supports("storage"),
    }

    health = attempt_provider_operation(providers, "health:eth_chainId", probe_provider)
    report["health_checks"] = health["attempts"]
    if not health["success"]:
        report["warnings"].append(f"所有 EVM RPC 不可用: {health['error']}")
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

    def perform(op_name: str, func) -> Any:
        nonlocal current_index
        outcome = attempt_provider_operation(providers, op_name, func, start_index=current_index)
        report["operations"][op_name] = outcome["attempts"]
        if outcome["success"]:
            current_index = outcome["provider_index"]
            report["selected_rpc"] = outcome["provider"]
            return outcome["result"]
        error: QueryError = outcome["error"]
        if error.retryable:
            report["warnings"].append(f"{op_name} 失败: {error}")
        raise error

    def cast_call(signature: str, *call_args: str, timeout: int = 20) -> str:
        return perform(
            f"cast_call:{signature}",
            lambda provider: run_cast(
                ["cast", "call", address, signature, *call_args, "--rpc-url", provider],
                timeout=timeout,
            ),
        )

    def cast_direct(subcommand: str, timeout: int = 20) -> str:
        return perform(
            f"cast_{subcommand}",
            lambda provider: run_cast(["cast", subcommand, address, "--rpc-url", provider], timeout=timeout),
        )

    def cast_storage(slot: str, timeout: int = 20) -> str:
        return perform(
            f"cast_storage:{slot}",
            lambda provider: run_cast(["cast", "storage", address, slot, "--rpc-url", provider], timeout=timeout),
        )

    def safe_value(producer, default: Any = "N/A") -> Any:
        try:
            return producer()
        except QueryError as exc:
            if exc.retryable:
                report["warnings"].append(str(exc))
            return default

    name = unwrap_cast_string(safe_value(lambda: cast_call("name()(string)"), "N/A"))
    symbol = unwrap_cast_string(safe_value(lambda: cast_call("symbol()(string)"), "N/A"))
    decimals_raw = safe_value(lambda: cast_call("decimals()(uint8)"), "N/A")
    total_supply_raw = safe_value(lambda: cast_call("totalSupply()(uint256)"), "N/A")
    owner = safe_value(lambda: cast_call("owner()(address)"), "N/A (无 Ownable)")
    timelock = safe_value(lambda: cast_call("getMinDelay()(uint256)"), "N/A")
    paused = safe_value(lambda: cast_call("paused()(bool)"), "N/A")
    cap = safe_value(lambda: cast_call("cap()(uint256)"), "N/A")
    buy_tax = safe_value(lambda: cast_call("buyTax()(uint256)"), "N/A")
    sell_tax = safe_value(lambda: cast_call("sellTax()(uint256)"), "N/A")
    transfer_fee = safe_value(lambda: cast_call("transferFee()(uint256)"), "N/A")

    implementation = "N/A"
    admin = "N/A"
    impl_slot = "N/A"
    admin_slot = "N/A"
    if report["cast_capabilities"]["implementation"]:
        implementation = safe_value(lambda: cast_direct("implementation"), "N/A")
    if report["cast_capabilities"]["admin"]:
        admin = safe_value(lambda: cast_direct("admin"), "N/A")
    if report["cast_capabilities"]["storage"]:
        impl_slot = safe_value(lambda: cast_storage(EIP1967_IMPLEMENTATION_SLOT), "N/A")
        admin_slot = safe_value(lambda: cast_storage(EIP1967_ADMIN_SLOT), "N/A")
    if implementation in {"N/A", ""} and impl_slot != "N/A":
        implementation = normalize_storage_address(impl_slot)
    if admin in {"N/A", ""} and admin_slot != "N/A":
        admin = normalize_storage_address(admin_slot)

    def detect_bool_method(signature: str) -> str:
        try:
            cast_call(signature, ZERO_ADDRESS)
        except QueryError as exc:
            if exc.retryable:
                raise
            return "不存在"
        return "存在"

    blacklist = safe_value(lambda: detect_bool_method("isBlacklisted(address)(bool)"), "unknown")
    whitelist = safe_value(lambda: detect_bool_method("isWhitelisted(address)(bool)"), "unknown")

    data = {
        "address": address,
        "rpc": report["selected_rpc"],
        "name": name,
        "symbol": symbol,
        "decimals": parse_int_maybe(str(decimals_raw)),
        "totalSupply": str(total_supply_raw),
        "owner": owner,
        "proxy_implementation": implementation,
        "proxy_admin": admin,
        "timelock_delay": str(timelock),
        "blacklist_function": blacklist,
        "whitelist_function": whitelist,
        "paused": str(paused),
        "cap": str(cap),
        "buyTax": str(buy_tax),
        "sellTax": str(sell_tax),
        "transferFee": str(transfer_fee),
        "eip1967_implementation_slot": impl_slot,
        "eip1967_admin_slot": admin_slot,
    }
    basic_path = out_path / "rpc-basic-info.json"
    report_path = out_path / "rpc-provider-report.json"
    write_json(basic_path, data)
    write_json(report_path, report)
    all_attempts = flatten_attempts({"health_checks": report["health_checks"], **report["operations"]})
    return {
        "success": True,
        "warnings": report["warnings"],
        "selected_rpc": report["selected_rpc"],
        "rpc_attempts": all_attempts,
        "provider_failures": [attempt for attempt in all_attempts if (not attempt["success"] and attempt.get("retryable"))],
        "outputs": {
            "rpc_basic_info": str(basic_path),
            "provider_report": str(report_path),
        },
        "data": data,
        "cast_capabilities": report["cast_capabilities"],
    }


def shutil_which_cast() -> bool:
    return run_subprocess(["which", "cast"], timeout=5)["returncode"] == 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="EVM 链上数据 RPC 直读")
    parser.add_argument("address", help="合约地址")
    parser.add_argument("arg2", nargs="?", default=None, help="兼容参数: RPC URL 或输出目录")
    parser.add_argument("arg3", nargs="?", default=None, help="兼容参数: 输出目录")
    parser.add_argument("--chain", default="ethereum", help="EVM 链名")
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
    result = collect(args.address, args.chain, args.out_dir, rpc_url=args.rpc_url)
    if not result["success"]:
        for warning in result["warnings"]:
            print(f"⚠️  {warning}")
        return 1
    data = result["data"]
    print("═══════════════════════════════════════════")
    print("  EVM RPC 链上数据直读")
    print(f"  地址: {args.address}")
    print(f"  RPC:  {result['selected_rpc']}")
    print("═══════════════════════════════════════════")
    print("")
    print("--- 基本信息 ---")
    print(f"name: {data['name']}")
    print(f"symbol: {data['symbol']}")
    print(f"decimals: {data['decimals'] if data['decimals'] is not None else 'N/A'}")
    print(f"totalSupply: {data['totalSupply']}")
    print("")
    print("--- 权限与治理 ---")
    print(f"owner: {data['owner']}")
    print(f"proxy.implementation: {data['proxy_implementation']}")
    print(f"proxy.admin: {data['proxy_admin']}")
    print(f"timelock.minDelay: {data['timelock_delay']}")
    print("")
    print("--- 代币功能特性 ---")
    print(f"paused: {data['paused']}")
    print(f"cap: {data['cap']}")
    print(f"buyTax: {data['buyTax']}")
    print(f"sellTax: {data['sellTax']}")
    print(f"transferFee: {data['transferFee']}")
    print(f"blacklist函数: {data['blacklist_function']}")
    print(f"whitelist函数: {data['whitelist_function']}")
    print("")
    print("--- 存储槽直读 (EIP-1967) ---")
    print(f"EIP-1967 implementation slot: {data['eip1967_implementation_slot']}")
    print(f"EIP-1967 admin slot: {data['eip1967_admin_slot']}")
    print("")
    print(f"✅ 已保存: {result['outputs']['rpc_basic_info']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
