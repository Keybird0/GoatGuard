#!/usr/bin/env python3
"""
GoPlus token security query with structured outputs.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Optional

from rpc_common import QueryError, request_json, write_json


GOPLUS_API_BASE = "https://api.gopluslabs.io/api/v1"
CHAIN_IDS = {
    "ethereum": "1",
    "bsc": "56",
    "polygon": "137",
    "arbitrum": "42161",
    "optimism": "10",
    "base": "8453",
    "avalanche": "43114",
    "solana": "solana",
    "sui": "sui",
}
CHAIN_ALIASES = {
    "1": "ethereum",
    "56": "bsc",
    "137": "polygon",
    "42161": "arbitrum",
    "10": "optimism",
    "8453": "base",
    "43114": "avalanche",
    "solana": "solana",
    "sui": "sui",
}


def detect_chain(token_address: str) -> str:
    addr = token_address.strip()
    if "::" in addr:
        return "sui"
    if addr.startswith("0x") and len(addr) == 66:
        return "sui"
    if not addr.startswith("0x") and 32 <= len(addr) <= 44:
        return "solana"
    if addr.startswith("0x") and len(addr) == 42:
        return "ethereum"
    return "unknown"


def build_url(chain: str, address: str) -> str:
    if chain == "solana":
        return f"{GOPLUS_API_BASE}/solana/token_security?contract_addresses={address}"
    if chain == "sui":
        return f"{GOPLUS_API_BASE}/sui/token_security?contract_addresses={address}"
    chain_id = CHAIN_IDS.get(chain)
    if not chain_id:
        raise ValueError(f"unsupported chain: {chain}")
    return f"{GOPLUS_API_BASE}/token_security/{chain_id}?contract_addresses={address}"


def normalize_chain(chain: str) -> str:
    normalized = str(chain or "").strip().lower()
    if normalized == "auto":
        return "auto"
    return CHAIN_ALIASES.get(normalized, normalized)


def extract_record(raw_result: Any, address: str) -> Dict[str, Any]:
    if isinstance(raw_result, dict):
        for key in (address, address.lower(), address.upper()):
            if key in raw_result and isinstance(raw_result[key], dict):
                return raw_result[key]
        first = next((value for value in raw_result.values() if isinstance(value, dict)), None)
        if isinstance(first, dict):
            return first
    return {}


def collect(token_address: str, chain: str, out_dir: Path | str) -> Dict[str, Any]:
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    requested_chain = normalize_chain(chain)
    resolved_chain = detect_chain(token_address) if requested_chain == "auto" else requested_chain
    url = build_url(resolved_chain, token_address)
    report_path = out_path / "goplus-request-report.json"
    token_security_path = out_path / "goplus-token-security.json"
    error_path = out_path / "goplus-token-security-error.json"

    report: Dict[str, Any] = {
        "token_address": token_address,
        "requested_chain": requested_chain,
        "resolved_chain": resolved_chain,
        "success": False,
        "warnings": [],
    }
    try:
        url = build_url(resolved_chain, token_address)
    except ValueError as exc:
        report["warnings"].append(str(exc))
        report_path = out_path / "goplus-request-report.json"
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": [str(exc)],
            "outputs": {"request_report": str(report_path)},
            "data": None,
        }
    report["url"] = url

    try:
        payload = request_json(url, timeout=20)
    except QueryError as exc:
        report["warnings"].append(str(exc))
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": [f"GoPlus 查询失败: {exc}"],
            "outputs": {"request_report": str(report_path)},
            "data": None,
        }

    if str(payload.get("code")) != "1":
        message = payload.get("message") or "未知错误"
        report["warnings"].append(message)
        write_json(error_path, payload)
        write_json(report_path, report)
        return {
            "success": False,
            "warnings": [f"GoPlus 返回异常: {message}"],
            "outputs": {
                "request_report": str(report_path),
                "error": str(error_path),
            },
            "data": payload,
        }

    result = payload.get("result") or {}
    write_json(token_security_path, result)
    record = extract_record(result, token_address)
    report["success"] = True
    report["fatal_flags"] = [
        label
        for key, label in [
            ("is_honeypot", "疑似蜜罐"),
            ("is_airdrop_scam", "疑似空投诈骗"),
            ("fake_token", "疑似假币"),
            ("cannot_sell_all", "疑似无法全部卖出"),
        ]
        if str(record.get(key, "0")) == "1"
    ]
    write_json(report_path, report)
    return {
        "success": True,
        "warnings": [],
        "outputs": {
            "token_security": str(token_security_path),
            "request_report": str(report_path),
        },
        "data": {
            "chain": resolved_chain,
            "result": result,
            "record": record,
            "fatal_flags": report["fatal_flags"],
        },
    }


def print_summary(result: Dict[str, Any]) -> None:
    if not result["success"]:
        for warning in result.get("warnings", []):
            print(f"⚠️  {warning}")
        return
    record = result["data"]["record"]
    fatal_flags = result["data"].get("fatal_flags", [])
    print("═══════════════════════════════════════════")
    print("  GoPlus 致命标签检查")
    print("═══════════════════════════════════════════")
    if fatal_flags:
        for item in fatal_flags:
            print(f"🚨 {item}")
    else:
        print("✅ 无致命风险标签")
    print("")
    print("--- 业务数据摘要 ---")
    print(f"代币名称: {record.get('token_name', 'N/A')}")
    print(f"代币符号: {record.get('token_symbol', 'N/A')}")
    print(f"总供应量: {record.get('total_supply', 'N/A')}")
    print(f"持有者数: {record.get('holder_count', 'N/A')}")
    print(f"买入税率: {record.get('buy_tax', 'N/A')}")
    print(f"卖出税率: {record.get('sell_tax', 'N/A')}")
    print(f"Owner: {record.get('owner_address', 'N/A')}")
    print(f"Creator: {record.get('creator_address', 'N/A')}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GoPlus Token Security API 查询")
    parser.add_argument("token_address", help="合约地址或代币标识")
    parser.add_argument("chain", nargs="?", default="auto", help="链名，默认 auto")
    parser.add_argument("out_dir", nargs="?", default=".", help="输出目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = collect(args.token_address, args.chain, args.out_dir)
    print_summary(result)
    if result["success"]:
        print("")
        print(f"完成。原始数据: {result['outputs']['token_security']}")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
