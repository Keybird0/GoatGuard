# -*- coding: UTF-8 -*-
"""
Sui Move 安全扫描器 — 独立版

15 类安全检查，无需编译，直接分析 Move 源代码/标准化模块 JSON

用法:
    python3 sui_scanner.py --package-dir ./workdir/sui/ --output ./results.json
    python3 sui_scanner.py --module-json ./sui-modules.json --package 0x123...
    python3 sui_scanner.py --source ./my_module.move --package 0x123...
"""
import argparse
import json
import os
import re
from pathlib import Path
import sys
from typing import List, Dict, Any, Optional


# ============================================================
# 内置扫描器（15 类检查）
# ============================================================

def _check_init_function(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    in_init = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'fun\s+init\s*\(', stripped):
            in_init = True
            if re.search(r'0x[a-fA-F0-9]{64}', stripped):
                issues.append({
                    "severity": "HIGH", "title": "init 中硬编码地址",
                    "description": "init 函数含硬编码地址，可能为固定管理员",
                    "line": i, "module": module_name, "function": "init",
                    "recommendation": "确认硬编码地址是否预期"
                })
            if 'mint' in stripped.lower() or 'TreasuryCap' in stripped:
                issues.append({
                    "severity": "INFO", "title": "init 中含 mint/TreasuryCap 操作",
                    "description": "init 中设置铸币能力",
                    "line": i, "module": module_name, "function": "init",
                    "recommendation": "验证铸币权限控制"
                })
        if in_init and (stripped == '}' or (stripped.endswith('}') and '{' not in stripped)):
            in_init = False
    return issues


def _check_access_control(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    current_func = None
    func_line = 0
    has_cap = False
    sensitive_keywords = ['transfer', 'mint', 'burn', 'pause', 'unpause', 'set', 'update', 'change', 'admin', 'withdraw']

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        m = re.search(r'fun\s+(\w+)\s*\(', stripped)
        if m:
            if current_func and not has_cap:
                if any(k in current_func.lower() for k in sensitive_keywords):
                    issues.append({
                        "severity": "HIGH", "title": f"关键函数 {current_func} 可能缺少访问控制",
                        "description": f"{current_func} 未检测到 Cap 权限参数",
                        "line": func_line, "module": module_name, "function": current_func,
                        "recommendation": "添加 AdminCap/TreasuryCap 等权限对象"
                    })
            current_func = m.group(1)
            func_line = i
            has_cap = bool(re.search(r'(AdminCap|TreasuryCap|OwnerCap|MintCap|Cap)', stripped))
        if current_func and any(k in stripped for k in ['AdminCap', 'TreasuryCap', 'OwnerCap', 'assert', 'abort']):
            has_cap = True
    return issues


def _check_mintable(lines: List[str], module_name: str, token_info: Optional[Dict] = None) -> List[Dict]:
    issues = []
    has_mint = False
    mint_in_init = False
    mint_func_exists = False
    has_max_supply = False
    mint_access_control = False
    fixed_supply = False
    mint_line = 0

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'fun\s+init\s*\(', stripped):
            # scan init body
            for j in range(i, min(len(lines) + 1, i + 50)):
                body = lines[j - 1].strip() if j <= len(lines) else ''
                if 'mint' in body.lower() or 'TreasuryCap' in body:
                    has_mint = True
                    mint_in_init = True
                    if not mint_line:
                        mint_line = j
                if 'make_supply_fixed' in body.lower() or 'FixedSupply' in body:
                    fixed_supply = True
                    mint_access_control = True
                if body == '}' or (body.endswith('}') and '{' not in body):
                    break

        if re.search(r'fun\s+mint', stripped, re.IGNORECASE):
            has_mint = True
            mint_func_exists = True
            if not mint_line:
                mint_line = i
            if re.search(r'(TreasuryCap|MintCap|AdminCap)', stripped):
                mint_access_control = True
            else:
                for j in range(i, min(len(lines), i + 30)):
                    if '}' in lines[j]:
                        break
                    if re.search(r'(TreasuryCap|MintCap|AdminCap)', lines[j]):
                        mint_access_control = True
                        break

        if re.search(r'\b(maxSupply|max_supply|MAX_SUPPLY)\b', stripped, re.IGNORECASE):
            has_max_supply = True

    if not has_mint:
        return issues

    if mint_in_init and not mint_func_exists:
        mint_type = "仅部署时一次性铸造"
    elif mint_in_init and mint_func_exists:
        mint_type = "部署时铸造 + 运行态可铸造"
    elif mint_func_exists:
        mint_type = "运行态可铸造"
    else:
        mint_type = "未知"

    if fixed_supply:
        access_info = "有权限控制（固定供应量）"
    elif mint_access_control:
        access_info = "有权限控制"
    elif mint_in_init and not mint_func_exists:
        access_info = "init 中 mint（相对安全，init 仅调用一次）"
    else:
        access_info = "缺少权限控制"

    issues.append({
        "severity": "HIGH" if not mint_access_control and not fixed_supply else "INFO",
        "title": "Mint功能分析",
        "description": f"铸造形式: {mint_type}\n最大值限制: {'有' if has_max_supply else '无'}\n权限控制: {access_info}",
        "line": mint_line, "module": module_name, "function": "mint",
        "mint_analysis": {
            "mint_type": mint_type,
            "has_max_supply": has_max_supply,
            "access_control": access_info,
            "mint_in_init": mint_in_init,
            "mint_function_exists": mint_func_exists,
            "fixed_supply": fixed_supply
        },
        "recommendation": "确认 mint 权限控制和最大供应量限制"
    })
    return issues


def _check_pause_function(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'fun\s+(pause|unpause|set_paused)', stripped, re.IGNORECASE):
            has_cap = bool(re.search(r'(AdminCap|OwnerCap)', stripped))
            if not has_cap:
                for j in range(i, min(len(lines), i + 20)):
                    if '}' in lines[j]:
                        break
                    if re.search(r'(AdminCap|OwnerCap)', lines[j]):
                        has_cap = True
                        break
            issues.append({
                "severity": "HIGH" if not has_cap else "MEDIUM",
                "title": f"检测到暂停功能{'（缺少权限控制）' if not has_cap else ''}",
                "description": "合约含暂停交易功能", "line": i, "module": module_name,
                "recommendation": "确保暂停功能有 AdminCap 权限控制"
            })
    return issues


def _check_transfer_functions(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'fun\s+transfer', stripped, re.IGNORECASE):
            has_cap = bool(re.search(r'(AdminCap|TreasuryCap)', stripped))
            if not has_cap:
                for j in range(i, min(len(lines), i + 20)):
                    if '}' in lines[j]:
                        break
                    if re.search(r'(AdminCap|TreasuryCap|assert|abort)', lines[j]):
                        has_cap = True
                        break
            if not has_cap:
                issues.append({
                    "severity": "MEDIUM", "title": "转账函数可能缺少权限控制",
                    "line": i, "module": module_name,
                    "recommendation": "确认是否预期公开"
                })
    return issues


def _check_hardcoded_secrets(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'0x[a-fA-F0-9]{64}', stripped) and 'fun' not in stripped:
            issues.append({
                "severity": "CRITICAL", "title": "硬编码私钥或敏感信息",
                "line": i, "module": module_name,
                "recommendation": "移除硬编码敏感信息"
            })
    return issues


def _check_unchecked_return(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        if re.search(r'\.(unwrap|expect)', line.strip()):
            issues.append({
                "severity": "MEDIUM", "title": "可能未检查的返回值 (unwrap/expect)",
                "line": i, "module": module_name,
                "recommendation": "使用 match 或 if 处理错误"
            })
    return issues


def _check_unbounded_loops(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if ('while' in stripped or stripped.startswith('loop')) and 'length' not in stripped and 'break' not in stripped:
            issues.append({
                "severity": "MEDIUM", "title": "未限制的循环",
                "line": i, "module": module_name,
                "recommendation": "限制循环最大迭代次数"
            })
    return issues


def _check_unsafe_type_casting(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        if ' as ' in line.strip() and 'assert' not in line and 'abort' not in line:
            issues.append({
                "severity": "MEDIUM", "title": "不安全的类型转换",
                "line": i, "module": module_name,
                "recommendation": "转换前添加范围检查"
            })
    return issues


def _check_shared_object(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'shared' in stripped.lower() and ('struct' in stripped or 'share_object' in stripped):
            issues.append({
                "severity": "MEDIUM", "title": "共享对象 — 需审查权限约束",
                "line": i, "module": module_name,
                "recommendation": "敏感对象不应无约束共享"
            })
    return issues


def _check_upgrade_permissions(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'fun\s+(upgrade|migrate)', stripped, re.IGNORECASE):
            has_cap = bool(re.search(r'(AdminCap|UpgradeCap)', stripped))
            if not has_cap:
                issues.append({
                    "severity": "HIGH", "title": "升级函数缺少权限控制",
                    "line": i, "module": module_name,
                    "recommendation": "添加 UpgradeCap 权限验证"
                })
    return issues


def _check_missing_events(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if any(k in stripped for k in ['transfer', 'mint', 'burn', 'pause']):
            has_event = any('event' in lines[j].lower() for j in range(max(0, i - 30), min(len(lines), i + 30)))
            if not has_event:
                issues.append({
                    "severity": "LOW", "title": "重要操作可能缺少事件记录",
                    "line": i, "module": module_name,
                    "recommendation": "为关键操作添加 event"
                })
    return issues


def _check_resource_management(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'Coin' in stripped and 'destroy' not in stripped and 'transfer' not in stripped and 'merge' not in stripped:
            if re.search(r'let\s+\w+\s*=.*Coin', stripped):
                issues.append({
                    "severity": "MEDIUM", "title": "可能的 Coin 资源泄漏",
                    "line": i, "module": module_name,
                    "recommendation": "确保 Coin 被正确 transfer/destroy/merge"
                })
    return issues


def _check_arithmetic(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if '/' in stripped and not stripped.startswith('//') and not stripped.startswith('/*'):
            if '*' in stripped and stripped.index('/') < stripped.index('*'):
                issues.append({
                    "severity": "MEDIUM", "title": "先除后乘 — 可能精度损失",
                    "line": i, "module": module_name,
                    "recommendation": "调整运算顺序为先乘后除"
                })
    return issues


def _check_function_visibility(lines: List[str], module_name: str) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'public\s+fun', stripped):
            m = re.search(r'fun\s+(\w+)', stripped)
            if m:
                name = m.group(1).lower()
                if any(k in name for k in ['get', 'read', 'view', 'query', 'is_', 'has_']):
                    if 'entry' not in stripped:
                        issues.append({
                            "severity": "LOW", "title": f"只读函数 {m.group(1)} 可考虑用 entry",
                            "line": i, "module": module_name,
                            "recommendation": "外部调用函数用 entry 可节省 gas"
                        })
    return issues


def scan_sui_move_code(source_code: Dict[str, str], package_address: str,
                       token_info: Optional[Dict] = None) -> Dict[str, Any]:
    """扫描 Sui Move 代码 — 15 类检查"""
    all_issues = []
    for module_name, code in source_code.items():
        lines = code.split('\n')
        all_issues.extend(_check_init_function(lines, module_name))
        all_issues.extend(_check_access_control(lines, module_name))
        all_issues.extend(_check_mintable(lines, module_name, token_info))
        all_issues.extend(_check_pause_function(lines, module_name))
        all_issues.extend(_check_transfer_functions(lines, module_name))
        all_issues.extend(_check_hardcoded_secrets(lines, module_name))
        all_issues.extend(_check_unchecked_return(lines, module_name))
        all_issues.extend(_check_unbounded_loops(lines, module_name))
        all_issues.extend(_check_unsafe_type_casting(lines, module_name))
        all_issues.extend(_check_shared_object(lines, module_name))
        all_issues.extend(_check_upgrade_permissions(lines, module_name))
        all_issues.extend(_check_missing_events(lines, module_name))
        all_issues.extend(_check_resource_management(lines, module_name))
        all_issues.extend(_check_arithmetic(lines, module_name))
        all_issues.extend(_check_function_visibility(lines, module_name))

    critical = [i for i in all_issues if i.get('severity') == 'CRITICAL']
    high = [i for i in all_issues if i.get('severity') == 'HIGH']
    medium = [i for i in all_issues if i.get('severity') == 'MEDIUM']
    info = [i for i in all_issues if i.get('severity') == 'INFO']

    return {
        "package_address": package_address,
        "issues": critical + high + medium + info,
        "critical": critical, "high": high, "medium": medium, "low": [], "info": info,
        "summary": {
            "total_issues": len(critical + high + medium + info),
            "critical": len(critical), "high": len(high),
            "medium": len(medium), "low": 0, "info": len(info)
        }
    }


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Sui Move 安全扫描器')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--package-dir', help='Sui 工作目录（含 package_info/normalized-modules.json）')
    group.add_argument('--module-json', help='直接提供 normalized modules JSON 文件')
    group.add_argument('--source', help='扫描单个 .move 文件')
    parser.add_argument('--package', default='unknown', help='Package 地址')
    parser.add_argument('--output', '-o', help='输出 JSON 路径')
    parser.add_argument('--deep', action='store_true', help='启用深度扫描（目前与标准扫描相同）')
    args = parser.parse_args()

    source_code = {}

    if args.source:
        p = Path(args.source)
        source_code[p.stem] = p.read_text(encoding='utf-8', errors='ignore')
    elif args.module_json:
        with open(args.module_json, 'r', encoding='utf-8') as f:
            modules_data = json.load(f)
        # normalized modules JSON 结构: { "result": { "module_name": { ... } } } 或直接 { "module_name": { ... } }
        if 'result' in modules_data:
            modules_data = modules_data['result']
        for mod_name, mod_data in modules_data.items():
            # 尝试提取可读源码（如果有）
            if isinstance(mod_data, str):
                source_code[mod_name] = mod_data
            elif isinstance(mod_data, dict):
                # 从 normalized module 构建伪源码用于模式分析
                source_code[mod_name] = _reconstruct_from_normalized(mod_name, mod_data)
    elif args.package_dir:
        pkg_dir = Path(args.package_dir)
        # 尝试读取 normalized-modules.json
        norm_file = pkg_dir / "package_info" / "normalized-modules.json"
        if not norm_file.exists():
            norm_file = pkg_dir / "sui-modules.json"
        if norm_file.exists():
            with open(norm_file, 'r', encoding='utf-8') as f:
                modules_data = json.load(f)
            if 'result' in modules_data:
                modules_data = modules_data['result']
            for mod_name, mod_data in modules_data.items():
                if isinstance(mod_data, str):
                    source_code[mod_name] = mod_data
                elif isinstance(mod_data, dict):
                    source_code[mod_name] = _reconstruct_from_normalized(mod_name, mod_data)
        # 同时扫描 code/ 下的 .move 文件
        code_dir = pkg_dir / "code"
        if code_dir.exists():
            for move_file in code_dir.rglob('*.move'):
                mod_name = move_file.stem
                source_code[mod_name] = move_file.read_text(encoding='utf-8', errors='ignore')

    if not source_code:
        print("❌ 未找到可扫描的 Move 代码")
        sys.exit(1)

    results = scan_sui_move_code(source_code, args.package)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"✅ 结果已保存: {args.output}")
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))

    # 终端摘要
    s = results.get('summary', {})
    print(f"\n--- Sui Move 扫描摘要 ---")
    print(f"模块数: {len(source_code)}  总发现: {s.get('total_issues', 0)}")
    for sev in ['critical', 'high', 'medium', 'info']:
        c = s.get(sev, 0)
        if c > 0:
            print(f"  {sev.upper()}: {c}")


def _reconstruct_from_normalized(module_name: str, mod_data: Dict) -> str:
    """从 normalized module 数据重建伪 Move 源码，用于模式匹配分析"""
    lines = [f"module {module_name} {{"]

    # 结构体
    for struct_name, struct_data in mod_data.get('structs', {}).items():
        abilities = struct_data.get('abilities', {}).get('abilities', [])
        ab_str = ', '.join(abilities) if abilities else ''
        lines.append(f"  struct {struct_name} has {ab_str} {{")
        for field in struct_data.get('fields', []):
            lines.append(f"    {field.get('name', '?')}: ???,")
        lines.append("  }")

    # 函数
    for func_name, func_data in mod_data.get('exposed_functions', {}).items():
        vis = func_data.get('visibility', 'Private')
        is_entry = func_data.get('is_entry', False)
        prefix = 'public ' if vis == 'Public' else ('public(package) ' if vis == 'Friend' else '')
        entry_str = 'entry ' if is_entry else ''
        params = ', '.join([f"arg{i}: ???" for i in range(len(func_data.get('parameters', [])))])
        lines.append(f"  {prefix}{entry_str}fun {func_name}({params}) {{")
        lines.append("  }")

    lines.append("}")
    return '\n'.join(lines)


if __name__ == '__main__':
    main()
