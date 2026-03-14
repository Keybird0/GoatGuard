# -*- coding: UTF-8 -*-
"""
Solidity Pattern Scanner — 独立版
12 项安全检查，无需编译，直接分析源代码文本

用法:
    python3 pattern_scanner.py --source ./src/ --output ./results.json
    python3 pattern_scanner.py --file ./Token.sol
"""
import argparse
import json
import os
import re
from pathlib import Path
from typing import List, Dict, Any, Optional


# ============================================================
# 内置精简版扫描器（当完整版不可用时使用）
# ============================================================
def _extract_contract_only_code(source_code: str) -> str:
    """提取只有实际合约实现的代码，排除 interface/library/abstract"""
    if not source_code:
        return source_code

    lines = source_code.split('\n')
    result_lines = []
    skip_depth = 0
    in_skip_block = False

    interface_pattern = re.compile(r'^\s*interface\s+\w+')
    library_pattern = re.compile(r'^\s*library\s+\w+')
    abstract_pattern = re.compile(r'^\s*abstract\s+contract\s+\w+')

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('//'):
            if not in_skip_block:
                result_lines.append(line)
            continue

        if not in_skip_block:
            if interface_pattern.match(stripped) or library_pattern.match(stripped) or abstract_pattern.match(stripped):
                in_skip_block = True
                skip_depth = stripped.count('{') - stripped.count('}')
                if skip_depth <= 0 and '{' in stripped:
                    in_skip_block = False
                continue
            else:
                result_lines.append(line)
        else:
            skip_depth += stripped.count('{') - stripped.count('}')
            if skip_depth <= 0:
                in_skip_block = False

    return '\n'.join(result_lines)


def _check_reentrancy(lines: List[str]) -> List[Dict]:
    """检查重入攻击模式"""
    issues = []
    in_function = False
    function_name = None
    has_external_call = False
    has_state_change_after = False
    ext_call_line = None

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'function ' in stripped and '{' in stripped:
            in_function = True
            has_external_call = False
            has_state_change_after = False
            m = re.search(r'function\s+(\w+)', stripped)
            function_name = m.group(1) if m else "unknown"
            continue
        if in_function:
            if re.search(r'\.(call|send|transfer|call\.value)', stripped):
                has_external_call = True
                ext_call_line = i
            if has_external_call and re.search(r'(\w+)\s*=\s*[^=]', stripped) and not stripped.startswith('//'):
                if not re.search(r'(memory|storage|calldata)\s+\w+\s*=', stripped):
                    has_state_change_after = True
            if stripped == '}' or (stripped.endswith('}') and '{' not in stripped):
                if has_external_call and has_state_change_after:
                    issues.append({
                        'severity': 'HIGH', 'title': '潜在的重入攻击风险',
                        'description': f'函数 {function_name} 外部调用后修改状态变量',
                        'line': ext_call_line or i,
                        'recommendation': '使用 ReentrancyGuard 或 CEI 模式'
                    })
                in_function = False
    return issues


def _check_tx_origin(lines: List[str]) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        if 'tx.origin' in line and not line.strip().startswith('//'):
            issues.append({
                'severity': 'MEDIUM', 'title': '使用 tx.origin 身份验证',
                'description': 'tx.origin 可被钓鱼合约利用', 'line': i,
                'recommendation': '使用 msg.sender 替代'
            })
    return issues


def _check_delegatecall(lines: List[str]) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'delegatecall(' in stripped and not stripped.startswith('//'):
            issues.append({
                'severity': 'HIGH', 'title': 'delegatecall 使用',
                'description': 'delegatecall 可能导致存储冲突或任意代码执行', 'line': i,
                'recommendation': '确保目标地址不可控'
            })
    return issues


def _check_selfdestruct(lines: List[str]) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if ('selfdestruct(' in stripped or 'suicide(' in stripped) and not stripped.startswith('//'):
            issues.append({
                'severity': 'HIGH', 'title': 'selfdestruct 使用',
                'description': '合约可自毁，销毁所有代码和余额', 'line': i,
                'recommendation': '移除或严格限制 selfdestruct 的调用权限'
            })
    return issues


def _check_hardcoded_secrets(lines: List[str]) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        if re.search(r'(private\s+key|secret|password)\s*=\s*["\']', line, re.IGNORECASE):
            issues.append({
                'severity': 'CRITICAL', 'title': '硬编码敏感信息',
                'description': '检测到可能的硬编码私钥或密码', 'line': i,
                'recommendation': '永远不要在合约中硬编码敏感信息'
            })
    return issues


def _check_access_control(lines: List[str]) -> List[Dict]:
    issues = []
    in_function = False
    func_name = None
    func_line = 0
    has_modifier = False
    is_sensitive = False

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'function ' in stripped:
            if in_function and is_sensitive and not has_modifier:
                issues.append({
                    'severity': 'HIGH', 'title': f'敏感函数缺少权限控制: {func_name}',
                    'description': f'{func_name} 可能缺少 onlyOwner 等权限修饰符',
                    'line': func_line, 'recommendation': '添加适当的权限控制修饰符'
                })
            m = re.search(r'function\s+(\w+)', stripped)
            func_name = m.group(1) if m else "unknown"
            func_line = i
            in_function = True
            has_modifier = bool(re.search(r'(onlyOwner|onlyRole|onlyAdmin|whenNotPaused|nonReentrant|only\w+)', stripped))
            is_sensitive = bool(re.search(r'\b(mint|burn|pause|unpause|setFee|withdraw|upgrade|transfer[Oo]wner|set[A-Z]|update[A-Z])', func_name or ''))
    return issues


def _check_arithmetic_old_version(lines: List[str]) -> List[Dict]:
    issues = []
    for line in lines:
        if 'pragma solidity' in line:
            m = re.search(r'(\d+)\.(\d+)', line)
            if m:
                major, minor = int(m.group(1)), int(m.group(2))
                if major == 0 and minor < 8:
                    issues.append({
                        'severity': 'HIGH', 'title': f'Solidity <0.8 无溢出保护',
                        'description': f'使用 Solidity 0.{minor}，无内置溢出保护',
                        'line': 1, 'recommendation': '升级到 Solidity ≥0.8 或使用 SafeMath'
                    })
            break
    return issues


def _check_unprotected_upgradeable(lines: List[str]) -> List[Dict]:
    issues = []
    has_initializer = False
    has_initialize = False
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if 'initializer' in stripped:
            has_initializer = True
        if re.search(r'function\s+initialize\b', stripped):
            has_initialize = True
            if 'initializer' not in stripped and 'onlyOwner' not in stripped:
                issues.append({
                    'severity': 'HIGH', 'title': '可升级合约 initialize 缺少保护',
                    'description': 'initialize 函数可能被任何人调用',
                    'line': i, 'recommendation': '添加 initializer 修饰符'
                })
    return issues


def _check_missing_zero_address(lines: List[str]) -> List[Dict]:
    issues = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'function\s+(set\w*|update\w*|transfer[Oo]wnership)\s*\(', stripped):
            if 'address' in stripped:
                # 检查后续几行有无 require(xxx != address(0))
                found_check = False
                for j in range(i, min(i + 5, len(lines))):
                    if 'address(0)' in lines[j] or '!= 0x0' in lines[j]:
                        found_check = True
                        break
                if not found_check:
                    m = re.search(r'function\s+(\w+)', stripped)
                    name = m.group(1) if m else 'unknown'
                    issues.append({
                        'severity': 'MEDIUM', 'title': f'缺少零地址校验: {name}',
                        'description': '地址参数未校验是否为 address(0)',
                        'line': i, 'recommendation': '添加 require(addr != address(0))'
                    })
    return issues


def _analyze_mint_functionality(lines: List[str]) -> Optional[Dict]:
    """分析 mint 功能的权限和限制"""
    mint_functions = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.search(r'\b_?mint\s*\(', stripped) and not stripped.startswith('//'):
            has_auth = bool(re.search(r'(onlyOwner|onlyRole|onlyMinter|only\w+|require)', stripped))
            mint_functions.append({'line': i, 'code': stripped[:120], 'has_auth': has_auth})

    if not mint_functions:
        return None

    unprotected = [m for m in mint_functions if not m['has_auth']]
    return {
        'severity': 'INFO', 'title': 'Mint功能分析',
        'description': f'发现 {len(mint_functions)} 处 mint 调用，其中 {len(unprotected)} 处可能缺少权限控制',
        'line': mint_functions[0]['line'],
        'details': {'total_mint_calls': len(mint_functions), 'unprotected': len(unprotected), 'locations': mint_functions[:5]}
    }


def scan_with_patterns_lite(source_code: str) -> List[Dict[str, Any]]:
    """内置精简版扫描器 — 核心 12 项检查"""
    if not source_code:
        return []

    contract_code = _extract_contract_only_code(source_code)
    lines = contract_code.split('\n')

    issues = []
    issues.extend(_check_reentrancy(lines))
    issues.extend(_check_tx_origin(lines))
    issues.extend(_check_delegatecall(lines))
    issues.extend(_check_selfdestruct(lines))
    issues.extend(_check_hardcoded_secrets(lines))
    issues.extend(_check_access_control(lines))
    issues.extend(_check_arithmetic_old_version(lines))
    issues.extend(_check_unprotected_upgradeable(lines))
    issues.extend(_check_missing_zero_address(lines))

    mint_result = _analyze_mint_functionality(lines)
    if mint_result:
        issues.append(mint_result)

    return issues


# ============================================================
# 统一入口
# ============================================================
def scan(source_code: str) -> List[Dict[str, Any]]:
    """扫描 Solidity 源代码（12 项检查）"""
    return scan_with_patterns_lite(source_code)


def scan_directory(source_dir: str) -> Dict[str, List[Dict]]:
    """扫描目录下所有 .sol 文件"""
    results = {}
    source_path = Path(source_dir)

    for sol_file in sorted(source_path.rglob('*.sol')):
        # 跳过测试和依赖
        rel = str(sol_file.relative_to(source_path))
        if any(skip in rel for skip in ['test/', 'Test.', 'Mock.', 'node_modules/', 'lib/', 'dependencies/']):
            continue

        code = sol_file.read_text(encoding='utf-8', errors='ignore')
        issues = scan(code)
        if issues:
            results[rel] = issues

    return results


# ============================================================
# CLI
# ============================================================
def main():
    parser = argparse.ArgumentParser(description='Solidity Pattern Scanner')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--source', help='扫描目录（递归查找 .sol）')
    group.add_argument('--file', help='扫描单个 .sol 文件')
    parser.add_argument('--output', '-o', help='输出 JSON 路径')
    parser.add_argument('--severity', choices=['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO'], default='MEDIUM',
                        help='最低严重程度过滤 (默认: MEDIUM)')
    args = parser.parse_args()

    severity_order = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'INFO': 0}
    min_sev = severity_order.get(args.severity, 2)

    if args.file:
        code = Path(args.file).read_text(encoding='utf-8', errors='ignore')
        all_issues = scan(code)
        results = {args.file: all_issues}
    else:
        results = scan_directory(args.source)

    # 过滤
    filtered = {}
    for file, issues in results.items():
        kept = [i for i in issues if severity_order.get(i.get('severity', 'INFO'), 0) >= min_sev]
        if kept:
            filtered[file] = kept

    # 统计
    total = sum(len(v) for v in filtered.values())
    by_sev = {}
    for issues in filtered.values():
        for issue in issues:
            s = issue.get('severity', 'INFO')
            by_sev[s] = by_sev.get(s, 0) + 1

    summary = {'total_issues': total, 'by_severity': by_sev, 'files_scanned': len(results), 'files_with_issues': len(filtered)}

    output = {'summary': summary, 'results': filtered}

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"✅ 结果已保存: {args.output}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    # 终端摘要
    print(f"\n--- 扫描摘要 ---")
    print(f"文件数: {summary['files_scanned']}  有问题: {summary['files_with_issues']}  总发现: {summary['total_issues']}")
    for sev in ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']:
        count = by_sev.get(sev, 0)
        if count > 0:
            print(f"  {sev}: {count}")


if __name__ == '__main__':
    main()
