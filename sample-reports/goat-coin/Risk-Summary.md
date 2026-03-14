# Risk Summary

- **项目**: `GOAT Coin (GOAT)`
- **合约地址**: `0x37611b28aca5673744161dc337128cfdd2657f69`
- **链**: `Ethereum Mainnet`
- **评分**: `92/100` / 评级 `S`
- **审计日期**: `2026-03-13`

---

## 主要依据

1. GoPlus 全量安全检测未命中任何致命标签（蜜罐/假币/空投诈骗）。
2. 合约源码已在 Etherscan 验证，不可增发、不可暂停、无代理/可升级模式。
3. 合约为典型 RFI (Reflect Finance) 模式，2% 转账费硬编码在合约中不可修改。
4. Owner 未放弃（地址 `0xad99...1362`），但 Owner 特权函数风险有限（仅 exclude/include 账户）。
5. 流动性极低（~23 ETH），LP 未锁定，需关注。

## 合约安全概要

| 检查项 | 结论 | 备注 |
| --- | --- | --- |
| 蜜罐 (Honeypot) | PASS | GoPlus: is_honeypot=0 |
| 可增发 (Mintable) | PASS | GoPlus: is_mintable=0, 合约无 mint 函数 |
| 代理/可升级 (Proxy) | PASS | GoPlus: is_proxy=0, RPC 确认无代理 |
| 暂停转账 (Pausable) | PASS | GoPlus: transfer_pausable=0, 合约无 pause |
| 黑名单 (Blacklist) | PASS | GoPlus: is_blacklisted=0, RPC 确认无黑名单函数 |
| 隐藏 Owner | PASS | GoPlus: hidden_owner=0 |
| 自毁 (Selfdestruct) | PASS | GoPlus: selfdestruct=0 |
| 外部调用 | PASS | GoPlus: external_call=0 |
| 可夺回所有权 | PASS | GoPlus: can_take_back_ownership=0 |
| Owner 可改余额 | PASS | GoPlus: owner_change_balance=0 |
| 源码已验证 | PASS | GoPlus: is_open_source=1 |
| 无法买入 | PASS | GoPlus: cannot_buy=0 |
| 无法全部卖出 | PASS | GoPlus: cannot_sell_all=0 |
| 滑点可修改 | PASS | GoPlus: slippage_modifiable=0 |
| 创建者蜜罐记录 | PASS | GoPlus: honeypot_with_same_creator=0 |
| 已上 DEX | PASS | GoPlus: is_in_dex=1 (UniswapV2) |
| 买入税 | 2.00% | GoPlus: buy_tax=0.02 (RFI 反射税) |
| 卖出税 | 1.62% | GoPlus: sell_tax=0.0162 |
| Owner 状态 | **FAIL** | Owner 未放弃: `0xad99...1362` |

## 持仓集中度

| 排名 | 地址 | 占比 | 说明 |
| --- | --- | --- | --- |
| 1 | `0x5626...10a1` | 18.57% | EOA，最大持有者 |
| 2 | `0xad99...1362` | 16.21% | EOA，Owner/Creator |
| 3 | `0xd343...4819` | 5.81% | EOA |
| 4 | `0x0000...dead` | 5.06% | 销毁地址 (锁定) |
| 5 | `0x753e...a4c7` | 3.45% | EOA |
| 6 | `0xcf3d...6c7f` | 3.27% | EOA |
| 7 | `0xffbc...8672` | 2.06% | EOA |
| 8 | `0x1942...b362` | 1.75% | EOA |
| 9 | `0x3761...f69` | 1.59% | 合约自身 |
| 10 | `0xc707...7e82` | 1.57% | 合约 |
| **Top 10 合计** | **-** | **59.32%** | **中等集中度** |

## 流动性分析

| 指标 | 值 | 评估 |
| --- | --- | --- |
| DEX | UniswapV2 | UniV2 AMM |
| 交易对 | `0x66fb...3e3a` | GOAT/ETH |
| 流动性 | 23.05 ETH (~$48,400) | **极低** |
| LP 持有者数 | 2 | 高度集中 |

**LP 持有者分布**:

| 地址 | 占比 | 锁定状态 |
| --- | --- | --- |
| `0xf604...e507` | 99.99% | **未锁定** |
| `0x0000...0000` (Null Address) | ~0.00% | 锁定 |

> LP 几乎全部由单一 EOA 持有且未锁定，存在 Rug Pull 风险。

## Owner 权限分析

- **Owner 地址**: `0xAd995aF5719a78f49c50e55ee63Fcc30c0E31362`
- **Owner 持币**: 16,240,462 GOAT (16.24%)
- **Owner 状态**: 未放弃

**Owner 特权函数**（AI 源码审查）:

| 函数 | 风险等级 | 说明 |
| --- | --- | --- |
| `excludeAccount(address)` | 中 | 将地址排除出反射分红，影响经济分配 |
| `includeAccount(address)` | 低 | 将地址重新纳入反射分红 |
| `renounceOwnership()` | - | 可放弃所有权（继承自 Ownable，尚未调用） |
| `transferOwnership(address)` | 低 | 可转移所有权 |

> Owner 无法铸币、暂停转账、修改税率或冻结账户。特权仅限于控制反射分红排除列表，风险有限。

## 风险标签

- 无致命标签 (FATAL)
- 无高风险标签 (HIGH)

**注意项**:
- Owner 未放弃（ATTENTION）
- LP 未锁定（ATTENTION）
- 流动性极低（ATTENTION）

## 关注项

1. **LP 未锁定且高度集中** — 99.99% LP 由单一 EOA 持有，无锁仓保护，存在撤池风险。
2. **流动性极低** — 仅 23 ETH 流动性，大额交易将导致严重滑点。
3. **Owner 未放弃** — Owner 可执行 `excludeAccount` 将任意地址排除出分红，虽然无法直接窃取资金，但可操纵分红分配。
4. **持仓集中度较高** — Top 2 地址合计持有 34.78%，大户抛售将产生显著市场影响。
5. **RFI 模式固有风险** — `_getCurrentSupply` 遍历排除列表的 O(n) 复杂度，极端情况下可能导致 Gas 异常。
6. **无 GitHub 仓库** — 无法追踪开发活动和代码变更历史。

