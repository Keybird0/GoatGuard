# Risk Summary

- **项目**: `Ethernaut Delegation (Level 6)`
- **源码**: [OpenZeppelin/ethernaut — Delegation.sol](https://github.com/OpenZeppelin/ethernaut/blob/master/contracts/src/levels/Delegation.sol)
- **链**: EVM (Solidity ^0.8.0)
- **评分**: `8/100` / 评级 `D`
- **审计日期**: `2026-03-14`

---

## 主要依据

1. 合约包含 **CRITICAL** 级别的 `delegatecall` 所有权劫持漏洞，任何外部账户可在单笔交易中接管合约所有权。
2. `fallback()` 函数将任意用户输入 (`msg.data`) 直接作为 `delegatecall` 参数，无任何过滤或访问控制。
3. `Delegate` 和 `Delegation` 的 `owner` 变量位于相同存储槽 (slot 0)，导致 delegatecall 执行时存储碰撞。
4. Slither 检测到 `controlled-delegatecall` 高危发现，AI 确认为**真阳性**。
5. 合约为 OpenZeppelin Ethernaut CTF 教学用例，**非生产级合约**。

## 合约安全概要

| 检查项 | 结果 | 备注 |
| --- | --- | --- |
| delegatecall 可控 | **FAIL** | Slither: controlled-delegatecall，fallback 中 msg.data 直传 |
| 访问控制 | **FAIL** | fallback 无 onlyOwner 或白名单限制 |
| 函数选择器过滤 | **FAIL** | 任意函数签名均可通过 delegatecall 执行 |
| 存储布局一致性 | **FAIL** | Delegate.owner 与 Delegation.owner 同处 slot 0，设计缺陷 |
| 零地址校验 | **FAIL** | Delegate 构造函数未校验 `_owner` 零地址 |
| 冗余语句 | **FAIL** | `this;` 为无操作表达式 |
| 事件日志 | **FAIL** | 无任何 event 定义，所有权变更不可追踪 |
| Solidity 版本 | **ATTENTION** | `^0.8.0` 允许包含已知 bug 的旧版编译器 |

## Owner 权限分析

- **Owner 变量**: `Delegation.owner`，在构造函数中设置为 `msg.sender`
- **Owner 保护**: **无** — 合约未实现 Ownable 模式，`owner` 变量仅在构造函数赋值
- **劫持路径**: 任何外部账户向 `Delegation` 发送 `abi.encodeWithSignature("pwn()")` 即可将 `owner` 覆写为自身地址

**Owner 特权函数**: 无。合约中 `owner` 仅作为公共状态变量存在，未绑定任何权限函数。但在继承或组合场景下，`owner` 被劫持后的影响取决于上层合约设计。

## 风险标签

- **CRITICAL**: `controlled-delegatecall` — 所有权劫持 (任意用户可接管)
- **HIGH**: 无访问控制、无函数选择器白名单
- **MEDIUM**: 无事件日志、零地址校验缺失

## 关注项

1. **delegatecall 所有权劫持** — `Delegation.fallback()` 将 `msg.data` 完整传递给 `Delegate.delegatecall()`，攻击者发送 `pwn()` 选择器 (`0xdd365b8b`) 即可成为 Owner，无需任何前置条件。
2. **无访问控制** — `fallback()` 函数完全开放，任何 EOA 或合约均可触发 delegatecall 执行。
3. **存储槽碰撞** — `Delegate.owner` 和 `Delegation.owner` 均位于 storage slot 0，delegatecall 上下文中对 `owner` 的写入直接影响 `Delegation` 的存储。
4. **无事件追踪** — Owner 变更无 event 发出，链上监控工具无法捕获所有权劫持。
5. **冗余代码** — `fallback()` 中 `this;` 为无操作语句，降低代码可读性且浪费 gas。
6. **教学合约** — 该合约为 Ethernaut CTF Level 6，设计目的是演示 delegatecall 漏洞，不适合任何生产环境部署。
