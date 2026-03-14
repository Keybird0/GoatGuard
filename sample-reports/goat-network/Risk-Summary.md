# Risk Summary

- **项目**: `Goat Network (GOATED)`
- **合约地址**: `0x5d7909f951436d4e6974d841316057df3a622962`
- **链**: Ethereum Mainnet (EIP-1967 Transparent Proxy)
- **评分**: 73/100 / 评级 `A`
- **审计日期**: 2026-03-14

---

## 主要依据

1. GOAT Network 是基于 BitVM2 的 Bitcoin L2 ZK Rollup 项目，具有完整的技术文档和白皮书
2. L1 代币部署为 EIP-1967 Transparent Proxy，实现合约地址 `0x6227...a919`，代理管理员 `0x0b9a...2f5d` 可随时升级实现
3. GoPlus 未检测到蜜罐、黑名单、暂停、自毁等恶意标记；买卖税均为 0%
4. 极高持仓集中度（Top 10 持有 98.35%），仅 53 个持有者，处于早期分发阶段
5. 流动性主要集中在 UniswapV4（约 600 ETH 分布于 5 个池），LP 未锁定
6. 存在第三方安全审计（Hacken，2024年10月）
7. GitHub 仓库包含 L2 预部署合约（GoatToken, Bridge, Locking, Relayer），代码质量良好，基于 OpenZeppelin

## 合约安全概要

| 检查项 | 结论 | 备注 |
| --- | --- | --- |
| 蜜罐 (Honeypot) | N/A | GoPlus 未返回此字段 |
| 可增发 (Mintable) | N/A | GoPlus 未返回；L2 源码 GoatToken 无 mint 函数（仅构造函数铸造） |
| 代理/可升级 (Proxy) | **是** | GoPlus: is_proxy=1；RPC 确认 EIP-1967 Transparent Proxy |
| 暂停转账 (Pausable) | N/A | GoPlus 未返回；L2 源码 GoatToken 无 pause 功能 |
| 黑名单 (Blacklist) | N/A | GoPlus 未返回；L2 源码 GoatToken 无 blacklist 功能 |
| 隐藏 Owner | N/A | GoPlus 未返回 |
| 自毁 (Selfdestruct) | N/A | GoPlus 未返回；L2 Burner.sol 有 selfdestruct 但仅用于 BTC 燃烧 |
| 外部调用 | N/A | GoPlus 未返回 |
| 可夺回所有权 | N/A | GoPlus 未返回 |
| Owner 可改余额 | N/A | GoPlus 未返回 |
| 源码已验证 | 是 | GoPlus: is_open_source=1 |
| 无法买入 | 正常 | GoPlus: cannot_buy=0 |
| 无法全部卖出 | N/A | GoPlus 未返回 |
| 滑点可修改 | N/A | GoPlus 未返回 |
| 创建者蜜罐记录 | 无 | GoPlus: honeypot_with_same_creator=0 |
| 已上 DEX | 是 | GoPlus: is_in_dex=1（UniswapV4, 5 个池） |
| 买入税 | 0% | GoPlus: buy_tax=0 |
| 卖出税 | 0% | GoPlus: sell_tax=0 |
| Owner 状态 | **活跃** | Proxy Admin: 0x0b9a...2f5d；Implementation Owner: 0x0166...a43d |

## 持仓集中度

| 排名 | 地址 | 占比 | 说明 |
| --- | --- | --- | --- |
| 1 | 0x1372...cd0e | 28.35% | EOA，未锁定 |
| 2 | 0xcd92...a7e4 | 22.24% | EOA，未锁定 |
| 3 | 0x85fa...0c35c | 14.61% | EOA，未锁定 |
| 4 | 0x4634...9758 | 12.55% | EOA，未锁定 |
| 5 | 0x9642...5d4e | 8.81% | EOA，未锁定 |
| 6 | 0x0d07...92fe | 5.08% | EOA，未锁定 |
| 7 | 0xb05b...5109 | 2.48% | EOA，未锁定 |
| 8 | 0xcffa...0703 | 2.01% | EOA，未锁定 |
| 9 | 0xea61...b902 | 1.60% | EOA，未锁定 |
| 10 | 0xfc89...dec3 | 0.62% | EOA，未锁定 |
| **Top 10 合计** | **—** | **98.35%** | **极高集中度** |

## 流动性分析

| DEX | 类型 | 流动性 (ETH) | 备注 |
| --- | --- | --- | --- |
| UniswapV4 Pool #1 | UniV4 | 296.96 | 主池，Pool Manager: 0x0000...8A90 |
| UniswapV4 Pool #2 | UniV4 | 197.14 | |
| UniswapV4 Pool #3 | UniV4 | 100.00 | |
| UniswapV4 Pool #4 | UniV4 | 5.96 | |
| UniswapV4 Pool #5 | UniV4 | 0.004 | 微型池 |
| **总计** | | **~600.07 ETH** | |

- **LP 持有者**: 1 个（合约 0xafa3...32cd，持有 100% LP）
- **LP 锁定状态**: 未锁定
- **LP NFT**: ID #144635，价值 ~296.94 ETH

## Owner 权限分析

| 角色 | 地址 | 说明 |
| --- | --- | --- |
| Proxy Admin | 0x0b9a9ac2f546aa2c328f7ccdc8fd7518945d2f5d | 可升级代理实现合约 |
| Implementation Owner | 0x01663c7f4bd52da2c00ea6fbb55a004b2aa3a43d | 实现合约的 owner() |
| Creator | 0xfa6383e0190148062c6abb357c38f6a59bd6f257 | 部署者，当前余额 0 |

- Proxy Admin 拥有最高权限，可随时升级实现合约至任意代码
- 未检测到 Timelock 或 Multisig 治理
- Creator 当前持有 0 代币

## 风险标签

| 类别 | 标签 |
| --- | --- |
| FATAL | 无 |
| HIGH | 代理合约可升级（Admin 活跃） |
| ATTENTION | 极高集中度 (98.35%)；LP 未锁定；GoPlus 多字段缺失 |

## 关注项

1. L1 代币为 EIP-1967 Transparent Proxy，Proxy Admin 可无需 Timelock 或 Multisig 审批直接升级实现合约，存在单点控制风险
2. Top 10 持有者控制 98.35% 的流通供应量，任一大户抛售可造成严重价格冲击
3. 所有前 10 持有者均为 EOA 且未锁定，无 Vesting 或 Lock 约束
4. LP 仅由 1 个合约地址持有且未锁定，存在流动性撤离风险
5. GoPlus API 未返回多项关键安全检测字段（is_honeypot, is_mintable, transfer_pausable, is_blacklisted 等），无法全面评估
6. GitHub 仓库中的合约为 L2 预部署合约，L1 代理合约的实现源码未在仓库中提供或独立验证
7. 总供应量 7,494,985 GOATED 远低于 L2 GoatToken 构造函数中的 10 亿，差额部分分布情况不明
8. 项目处于极早期阶段（仅 53 个持有者），流动性深度和持仓分散度有待观察
