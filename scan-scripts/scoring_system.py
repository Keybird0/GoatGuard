# -*- coding: UTF-8 -*-
"""
业务安全评分系统 — 独立版（100分扣分制）

用法:
    # 作为 CLI
    python3 scoring_system.py --goplus ./goplus.json --mint "可增发" --owner 0x123... --top10 0.87
    # 作为模块
    from scoring_system import calculate_business_security_score
    score, rating, explanation = calculate_business_security_score(mint_status="不可增发", ...)
"""
import argparse
import json
import re
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

def normalize_mint_status(raw_status: str) -> str:
    """归一化增发情况为 '可增发' / '不可增发'"""
    if not raw_status or not isinstance(raw_status, str):
        return "不可增发"
    s = raw_status.lower()
    non_mint = ["不可增发", "仅部署时一次性铸造", "一次性铸造", "固定供应", "已撤销", "已放弃", "无mint", "no mint", "not mintable"]
    for k in non_mint:
        if k.lower() in s:
            return "不可增发"
    mint = ["可增发", "运行态可铸造", "可铸造", "有mint", "mintable", "部署时铸造 + 运行态可铸造"]
    for k in mint:
        if k.lower() in s:
            return "可增发"
    return "不可增发"


def get_rating_description(rating: str) -> str:
    descs = {
        "D": "危险 - 存在严重业务风险，建议暂不上线",
        "C": "较危险 - 存在较多风险需要修复或改进",
        "B": "中等安全 - 存在中等风险需要关注",
        "A": "较安全 - 存在少量风险但不影响主要功能",
        "S": "安全 - 所有业务风险都在可控范围内"
    }
    return descs.get(rating, "未知评级")


def calculate_business_security_score(
    goplus_info: Optional[Dict[str, Any]] = None,
    mint_status: str = "未知",
    owner_address: Optional[str] = None,
    top10_holder_ratio: float = 0.0,
    is_in_dex: bool = False,
    is_open_source: bool = False,
    is_proxy: bool = False,
    blacklist_enabled: bool = False,
    can_be_minted: bool = False,
    **kwargs
) -> Tuple[int, str, str]:
    """
    100分扣分制。返回 (score, rating, explanation)
    评级: D(0-20) C(21-40) B(41-60) A(61-80) S(81-100)
    """
    score = 100
    details = []

    # 0. 严重问题（蜜罐/诈骗，一票否决）
    if goplus_info:
        if goplus_info.get("蜜罐") == "是" or goplus_info.get("is_honeypot") == "1":
            score -= 50; details.append("🚨 蜜罐合约: -50")
        if goplus_info.get("空投诈骗") == "是" or goplus_info.get("is_airdrop_scam") == "1":
            score -= 40; details.append("🚨 空投诈骗: -40")
        if goplus_info.get("假币") == "是" or goplus_info.get("fake_token") == "1":
            score -= 35; details.append("🚨 假币: -35")
        if goplus_info.get("无法全部卖出") == "是" or goplus_info.get("cannot_sell_all") == "1":
            score -= 30; details.append("🚨 无法全部卖出: -30")

    # 1. Mint 风险（最高-20）
    norm = normalize_mint_status(mint_status)
    if norm == "可增发":
        has_max = False
        if goplus_info:
            ms = goplus_info.get("max_supply", "")
            ts = goplus_info.get("total_supply", "")
            if ms and ms != "0" and ms != ts:
                has_max = True
        if not has_max:
            score -= 20; details.append("无限增发: -20")
        else:
            score -= 10; details.append("有限增发: -10")
    else:
        details.append("不可增发: 0")

    # 2. Owner 权限（最高-18）
    owner_risk = 0
    has_owner = bool(owner_address and owner_address not in [
        "已放弃", "无（已放弃）", "-", "0x0000000000000000000000000000000000000000"
    ])
    if has_owner and goplus_info:
        if goplus_info.get("所有者可改变余额") == "是" or goplus_info.get("owner_change_balance") == "1":
            owner_risk += 10; details.append("Owner可改余额: -10")
        if goplus_info.get("隐藏所有者") == "是" or goplus_info.get("hidden_owner") == "1":
            owner_risk += 8; details.append("隐藏Owner: -8")
        if goplus_info.get("可收回所有权") == "是" or goplus_info.get("can_take_back_ownership") == "1":
            owner_risk += 3; details.append("可收回: -3")
        if norm == "可增发":
            owner_risk += 3; details.append("Owner有Mint: -3")
    elif not has_owner:
        details.append("Owner已放弃: 0")
    score -= min(owner_risk, 18)

    # 3. 集中度（最高-20）
    if top10_holder_ratio >= 0.9:
        score -= 20; details.append(f"极高集中度({top10_holder_ratio*100:.1f}%): -20")
    elif top10_holder_ratio >= 0.8:
        score -= 15; details.append(f"很高集中度({top10_holder_ratio*100:.1f}%): -15")
    elif top10_holder_ratio >= 0.7:
        score -= 12; details.append(f"高集中度({top10_holder_ratio*100:.1f}%): -12")
    elif top10_holder_ratio >= 0.5:
        score -= 8; details.append(f"中集中度({top10_holder_ratio*100:.1f}%): -8")
    elif top10_holder_ratio >= 0.3:
        score -= 3; details.append(f"轻微集中({top10_holder_ratio*100:.1f}%): -3")

    # 4. DEX（-3）
    if not is_in_dex:
        score -= 3; details.append("未上DEX: -3")

    # 5. 其他（最高-7）
    other = 0
    if not is_open_source:
        other += 2; details.append("未开源: -2")
    if is_proxy:
        other += 2; details.append("代理合约: -2")
    if blacklist_enabled:
        other += 3; details.append("黑名单: -3")
    score -= min(other, 7)

    # 6. 数据完整性
    unknown = 0
    if mint_status in ["未知", "", None]:
        unknown += 1
    if not owner_address or owner_address == "-":
        unknown += 1
    if top10_holder_ratio == 0.0 and (not goplus_info or not goplus_info.get("holders")):
        unknown += 1
    if unknown:
        score -= unknown; details.append(f"数据不完整({unknown}项): -{unknown}")

    score = max(0, min(100, score))
    rating = "D" if score <= 20 else "C" if score <= 40 else "B" if score <= 60 else "A" if score <= 80 else "S"
    return score, rating, f"评分依据: {' | '.join(details)}"


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='业务安全评分（100分扣分制）')
    parser.add_argument('--goplus', help='GoPlus JSON 文件路径')
    parser.add_argument('--mint', default='未知', help='增发情况描述')
    parser.add_argument('--owner', default=None, help='Owner 地址')
    parser.add_argument('--top10', type=float, default=0.0, help='前10持币占比 (0.0-1.0)')
    parser.add_argument('--dex', action='store_true', help='已在 DEX')
    parser.add_argument('--open-source', action='store_true', help='合约已开源')
    parser.add_argument('--proxy', action='store_true', help='代理合约')
    parser.add_argument('--blacklist', action='store_true', help='黑名单功能')
    parser.add_argument('--output', '-o', help='输出 JSON 路径')
    args = parser.parse_args()

    goplus_info = None
    if args.goplus:
        with open(args.goplus, 'r', encoding='utf-8') as f:
            goplus_info = json.load(f)

    score, rating, explanation = calculate_business_security_score(
        goplus_info=goplus_info,
        mint_status=args.mint,
        owner_address=args.owner,
        top10_holder_ratio=args.top10,
        is_in_dex=args.dex,
        is_open_source=args.open_source,
        is_proxy=args.proxy,
        blacklist_enabled=args.blacklist,
    )

    result = {
        "score": score,
        "rating": rating,
        "rating_description": get_rating_description(rating),
        "explanation": explanation,
    }

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"✅ 结果已保存: {args.output}")

    print(f"\n{'='*40}")
    print(f"  评分: {score}/100  评级: {rating}")
    print(f"  {get_rating_description(rating)}")
    print(f"{'='*40}")
    print(f"  {explanation}")


if __name__ == '__main__':
    main()
