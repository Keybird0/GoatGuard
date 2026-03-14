# Audit Checklist Evaluation

## 基本信息

| 项目 | 内容 |
| --- | --- |
| Token 名称 | GOAT Coin (GOAT) |
| 合约地址 | `0x37611b28aca5673744161dc337128cfdd2657f69` |
| 链 | Ethereum Mainnet |
| 标准 | ERC-20（RFI 自定义转账） |
| 部署时间 | 2021-03-19 |

---

## 一、合约安全检测

| 检查项 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 非蜜罐 | PASS | GoPlus: is_honeypot=0 | 可正常买卖 |
| 不可增发 | PASS | GoPlus: is_mintable=0 | 合约无 mint 函数，供应量硬编码 |
| 非代理/不可升级 | PASS | GoPlus: is_proxy=0, RPC: implementation=0x0 | 无代理模式 |
| 不可暂停 | PASS | GoPlus: transfer_pausable=0 | 合约无 pause 函数 |
| 无黑名单 | PASS | GoPlus: is_blacklisted=0, RPC: 函数不存在 | 无黑名单机制 |
| 无隐藏 Owner | PASS | GoPlus: hidden_owner=0 | Owner 地址公开可查 |
| 无自毁 | PASS | GoPlus: selfdestruct=0 | 合约无 selfdestruct |
| 无外部调用 | PASS | GoPlus: external_call=0 | 无外部合约调用 |
| 可正常买入 | PASS | GoPlus: cannot_buy=0 | 买入功能正常 |
| 可全部卖出 | PASS | GoPlus: cannot_sell_all=0 | 卖出功能正常 |
| 滑点不可修改 | PASS | GoPlus: slippage_modifiable=0 | 税率硬编码 |
| Owner 不可修改余额 | PASS | GoPlus: owner_change_balance=0 | 无余额修改函数 |
| 创建者无蜜罐记录 | PASS | GoPlus: honeypot_with_same_creator=0 | 无历史蜜罐关联 |
| 源码已验证 | PASS | GoPlus: is_open_source=1 | Etherscan 已验证 |
| 已在 DEX 上市 | PASS | GoPlus: is_in_dex=1 | UniswapV2 交易对存在 |
| 反射税率不可修改 | PASS | AI 源码审查: `_getTValues` 硬编码 2% | `tFee = (tAmount.mul(2)).div(100)` |
| 无 reentrancy 风险 | PASS | AI 源码审查: 无外部调用 | 纯内部状态更新 |
| Slither 无 High/Critical | PASS | Slither: 16 findings (0 High, 0 Critical) | 最高为 Low (shadowing-local, costly-loop) |
| Pattern Scanner 误报已排除 | PASS | P-1 "Solidity <0.8 无溢出保护" = 误报 | 合约使用 SafeMath 全覆盖 |

## 二、权限与治理

| 检查项 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| Owner 已放弃 | **FAIL** | owner=0xAd99...1362 | Owner 仍为 EOA，未调用 renounceOwnership |
| 无法夺回所有权 | PASS | GoPlus: can_take_back_ownership=0 | 合约无夺回所有权函数 |
| Owner 特权有限 | PASS | AI 源码审查 | 仅 excludeAccount/includeAccount，无高危操作 |
| 合约评分 | PASS | 92/100 (S) | 评分 ≥ 61 |
| 多签治理 | **FAIL** | Owner 为 EOA | 无多签保护 |
| 时间锁 | **FAIL** | RPC: timelock_delay=N/A | 无时间锁 |

## 三、市场与流动性

| 检查项 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 流动性充足 | **FAIL** | UniswapV2: 23.05 ETH (~$48,400) | 远低于 100 ETH 基准线 |
| LP 已锁定 | **FAIL** | 主要 LP (99.99%) 由 0xf604...e507 持有，未锁定 | 存在撤池风险 |
| 持仓分散 | **FAIL** | Top 10 集中度: 59.32% | 超过 50% 阈值 |
| 买入税合理 | PASS | 2.00% | 在合理范围内 |
| 卖出税合理 | PASS | 1.62% | 在合理范围内 |

## 四、项目合规

| 检查项 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 仓库/源码可得 | **FAIL** | 无 GitHub 仓库 | Etherscan 已验证源码，但无公开代码仓库 |
| 项目官网可达 | PASS | https://goatcoin.net | 官网可访问 |
| 第三方审计 | **FAIL** | Etherscan 标注: "No Contract Security Audit Submitted" | 无第三方审计报告 |

## 五、链特有检查（EVM）

| 检查项 | 状态 | 证据 | 备注 |
| --- | --- | --- | --- |
| 非代理合约 | PASS | RPC: EIP-1967 slots 均为 0x0 | 非可升级合约 |
| RPC 数据与 GoPlus 一致 | PASS | owner/supply/proxy 全部一致 | 交叉验证通过 |
| Solidity 版本 ≥ 0.8 | **FAIL** | v0.6.12 | 使用旧版 Solidity，依赖 SafeMath |
| 编译器 Bug 无影响 | PASS | AI 评估 3 个 medium-severity 告警 | 均不影响合约功能 |
| _excluded 数组有界 | **FAIL** | 无上限检查 | Low 级别设计缺陷 |

---

## 统计

| 类别 | 数量 |
| --- | --- |
| PASS | 28 |
| FAIL | 10 |
| TODO | 0 |
| N/A | 0 |

## 风险分类汇总

### 合约级风险

- **低风险**: Owner 特权函数仅限 exclude/include 账户，不涉及资金操作。
- **低风险**: `_excluded` 数组无上限但实际影响极小。
- **低风险**: 编译器版本较旧（v0.6.12），但使用 SafeMath 库弥补。
- **信息**: RFI 模式 2% 反射税率硬编码，不可修改。

### 运营级风险

- **中风险**: Owner 未放弃，无多签/时间锁保护。但 Owner 特权范围窄。
- **低风险**: 无 GitHub 仓库，无法追踪代码变更。
- **中风险**: 无第三方审计报告。

### 市场级风险

- **高风险**: LP 未锁定，99.99% 由单一 EOA 持有。
- **高风险**: 流动性极低 (~23 ETH)，大额交易将造成严重滑点。
- **中风险**: 持仓集中度 59.32%，前两大地址持有 34.78%。
