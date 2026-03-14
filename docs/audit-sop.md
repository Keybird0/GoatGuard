# 通用代币安全审计标准操作流程 (SOP)
> 适用于通用代币安全审计流程，覆盖 EVM 链（Ethereum/BSC/Polygon/Arbitrum 等）+ Solana + Sui。审计输入可能为合约地址、代码仓库、白皮书、项目官网中的一项或多项，本 SOP 覆盖所有输入组合场景。
>

## 适用范围
+ 通用代币安全审计（主流程）
+ 已上线代币的安全复审
+ 与代币项目方合作/投资前的技术尽职调查
+ 交易所 上币前技术风控评估

## 审核输入与输出
输入（审计输入，以下一种或多种）：

| 输入类型 | 示例 |
| --- | --- |
| 链上合约地址 | `0xB8c77482e45F1F44dE1745F52C74426C631bDD52` 或浏览器链接 `https://etherscan.io/token/0xB8c7...` |
| 代码仓库地址 | `https://github.com/xxx/yyy` |
| 白皮书/官方文档 | PDF 文件 或 `https://docs.xxx.io/` |
| 项目官网 | `https://xxx.network/` |
| 内部投研简报 | PDF/文档 |


输出（存放于 `./{Token-Ticker-Name}/security-review/`）：

| 文件 | 用途 |
| --- | --- |
| `{Token-Ticker-Name}-Token-Security-Assessment.md` | 综合安全评估（完整版） |
| `{Token-Ticker-Name}-Audit-Checklist-Evaluation.md` | 参考Solodit Blockchain Security Audit Checklist完整 Checklist 逐项评估 |

---

## 阶段零：环境准备
目标：搭建完整的审计工具链。首次执行后，后续审核可跳过（仅需步骤 0.7 验证）。

### 步骤 0.1 — 基础依赖
```bash
# Homebrew（macOS 包管理器，如未安装）
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Git
git --version
# 如未安装：brew install git

# Node.js + npm（部分合约项目需要）
node --version && npm --version
# 如未安装：brew install node

# Python 3
python3 --version
# macOS 自带；如需更新：brew install python3
```

### 步骤 0.2 — 安装 Foundry (forge, cast, anvil)
Foundry 用于合约编译、测试，`cast` 用于 RPC 链上数据读取。

```bash
curl -L https://foundry.paradigm.xyz | bash
source ~/.zshenv   # 或 source ~/.bashrc
foundryup

# 验证
forge --version
cast --version
anvil --version
```

常见问题：

+ `foundryup: command not found` → 关闭并重新打开终端，或执行 `source ~/.zshenv`
+ 网络问题导致下载失败 → 配置代理或使用 GitHub release 手动下载

### 步骤 0.3 — 安装 Slither
```bash
brew install pipx
pipx ensurepath
source ~/.zshrc
pipx install slither-analyzer

# 验证
slither --version
```

常见问题：

+ `pip install` 报 `externally-managed-environment` → Python 3.12+ 必须使用 pipx
+ `pipx: command not found` → `brew install pipx && pipx ensurepath` 后重新打开终端
+ 升级 → `pipx upgrade slither-analyzer`

### 步骤 0.4 — 安装 Solana 工具链（审核 Solana 链代币时需要）
```bash
# 安装 Solana CLI
sh -c "$(curl -sSfL https://release.anza.xyz/stable/install)"
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
# 添加到 ~/.zshrc 持久化

# 验证
solana --version        # 应输出 solana-cli x.x.x

# 安装 Anchor CLI（Solana 合约框架，审核 Anchor 项目时需要）
# 需要先安装 Rust
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
source "$HOME/.cargo/env"

# 安装 avm (Anchor Version Manager)
cargo install --git https://github.com/coral-xyz/anchor avm --force
avm install latest
avm use latest

# 验证
anchor --version        # 应输出 anchor-cli x.x.x
```

常见问题：

+ `solana: command not found` → 执行 `export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"` 或重新打开终端
+ Rust 编译失败 → `rustup update stable`
+ Anchor 版本不匹配 → 检查项目的 `Anchor.toml` 中要求的版本，`avm install <version> && avm use <version>`

### 步骤 0.4-SUI — 安装 Sui 工具链（审核 Sui 链代币时需要）
```bash
# 安装 Sui CLI（mainnet 分支）
cargo install --locked --git https://github.com/MystenLabs/sui.git --branch mainnet sui

# 配置 Sui mainnet RPC
sui client new-env --alias mainnet --rpc https://fullnode.mainnet.sui.io:443
sui client switch --env mainnet

# 验证环境
sui client envs
sui --version
```

常见问题：

+ `sui: command not found` → 检查 `$HOME/.cargo/bin` 是否在 PATH
+ `new-env` 重复创建失败 → 改用新 alias，如 `mainnet2`
+ RPC 超时 → 更换公共 fullnode 或企业节点

### 步骤 0.5 — 安装辅助工具与扫描器
```bash
# === 必需工具 ===
# jq — JSON 处理（解析 GoPlus API 返回、Checklist JSON）
brew install jq

# gh — GitHub CLI（浏览仓库、查看 issue/PR）【推荐】
brew install gh
gh auth login

# Graphviz — Slither 合约关系图生成【可选】
brew install graphviz

# === EVM 扫描器（阶段三使用）===

# Aderyn (Cyfrin) — Rust 实现的快速静态分析器【推荐】
# 与 Slither 互补：擅长 gas 级 pattern、命名规范、低级别发现
cargo install aderyn
# 验证
aderyn --version

# 4naly3er — C4/Sherlock 竞赛向 analyzer【推荐】
# 覆盖 Low/NC/Gas 级发现，输出格式与审计报告兼容
npm install -g @4naly3er/cli 2>/dev/null || echo "4naly3er: 见 https://github.com/Picodes/4naly3er 手动安装"

# Semgrep — 自定义规则引擎【可选，适合编写项目特定扫描规则】
brew install semgrep

# === EVM 深度工具（可选，复杂 DeFi 代币/Vault/Rebase 场景）===
# Mythril — 符号执行（发现条件性重入、整数溢出的实际可触发条件）
pipx install mythril
# Echidna — 基于属性的 Fuzzing
# brew install echidna 或 https://github.com/crytic/echidna/releases
# Halmos — 符号执行（形式化验证关键不变量）
pipx install halmos

# === Solana 扫描器 ===
# cargo-geiger — 检查 unsafe 代码比例【推荐】
cargo install cargo-geiger
# Trident (Ackee) — Anchor 程序 Fuzzing【可选】
# cargo install trident-cli

# === Sui 扫描器 ===
# Move Prover — 形式化验证（可选深度工具）
# 随 Sui CLI 安装，验证：sui move prove --help
```

常见问题：

+ `aderyn: command not found` → 确保 `$HOME/.cargo/bin` 在 PATH
+ `mythril` 安装慢 → 依赖 z3-solver 编译，耐心等待或使用 Docker: `docker pull mythril/myth`
+ `semgrep` 规则集 → 推荐 `p/smart-contracts` 和自行编写代币特定规则

### 步骤 0.6 — 配置 API Key
审核流程依赖多个外部 API，建议在 shell 配置文件（`~/.zshrc`）中持久化：

```bash
# --- EVM 区块浏览器 API Key（用于 cast 下载源码、读取合约信息）---
# Etherscan: https://etherscan.io/myapikey
export ETHERSCAN_API_KEY="<your_key>"

# BscScan: https://bscscan.com/myapikey
export BSCSCAN_API_KEY="<your_key>"

# PolygonScan / Arbiscan / BaseScan 等类似，按需申请

# --- GoPlus API（免费，无需 Key，但有速率限制）---
# 无需配置，直接调用即可
# 如有企业版 Key：export GOPLUS_API_KEY="<your_key>"
```

### 步骤 0.7 — 配置 RPC 节点
链上数据读取需要 RPC 端点。建议在 `~/.zshrc` 中持久化：

```bash
# --- EVM 链 ---
export ETH_RPC_URL="https://eth.llamarpc.com"
export BSC_RPC_URL="https://bsc-dataseed.binance.org"
export POLYGON_RPC_URL="https://polygon-rpc.com"
export ARB_RPC_URL="https://arb1.arbitrum.io/rpc"
export OP_RPC_URL="https://mainnet.optimism.io"
export BASE_RPC_URL="https://mainnet.base.org"
export AVAX_RPC_URL="https://api.avax.network/ext/bc/C/rpc"

# --- Solana ---
export SOLANA_RPC_URL="https://api.mainnet-beta.solana.com"
# 配置 Solana CLI 默认 RPC
solana config set --url $SOLANA_RPC_URL

# --- Sui ---
export SUI_RPC_URL="https://fullnode.mainnet.sui.io:443"
# 免费公共节点有速率限制，生产环境建议用 Helius / QuickNode / Alchemy
# export SUI_RPC_URL="https://mainnet.helius-rpc.com/?api-key=<your_key>"
```

常用公共 RPC 和浏览器参考：

EVM 链：

| 链 | Chain ID | 免费 RPC | 浏览器 API 域名 |
| --- | --- | --- | --- |
| Ethereum | 1 | `https://eth.llamarpc.com` | `api.etherscan.io` |
| BSC | 56 | `https://bsc-dataseed.binance.org` | `api.bscscan.com` |
| Polygon | 137 | `https://polygon-rpc.com` | `api.polygonscan.com` |
| Arbitrum | 42161 | `https://arb1.arbitrum.io/rpc` | `api.arbiscan.io` |
| Optimism | 10 | `https://mainnet.optimism.io` | `api-optimistic.etherscan.io` |
| Base | 8453 | `https://mainnet.base.org` | `api.basescan.org` |
| Avalanche | 43114 | `https://api.avax.network/ext/bc/C/rpc` | `api.snowscan.xyz` |


Solana：

| 网络 | RPC | 浏览器 |
| --- | --- | --- |
| Mainnet | `https://api.mainnet-beta.solana.com` | Solscan: `https://solscan.io` / Solana Explorer: `https://explorer.solana.com` |
| Devnet | `https://api.devnet.solana.com` | `https://explorer.solana.com/?cluster=devnet` |


### 步骤 0.8 — 环境验证
```bash
echo "=== 审计工具链环境检查 ==="
echo ""
echo "--- 基础工具 ---"
echo "Git:      $(git --version 2>&1 || echo '未安装')"
echo "Node:     $(node --version 2>&1 || echo '未安装')"
echo "Python:   $(python3 --version 2>&1 || echo '未安装')"
echo "jq:       $(jq --version 2>&1 || echo '未安装')"
echo "gh:       $(gh --version 2>&1 | head -1 || echo '未安装 (可选)')"
echo ""
echo "--- EVM 工具链 ---"
echo "Forge:    $(forge --version 2>&1 || echo '未安装')"
echo "Cast:     $(cast --version 2>&1 || echo '未安装')"
echo "Slither:  $(slither --version 2>&1 || echo '未安装')"
echo ""
echo "--- Solana 工具链 ---"
echo "Solana:   $(solana --version 2>&1 || echo '未安装')"
echo "Anchor:   $(anchor --version 2>&1 || echo '未安装 (按需)')"
echo "Rust:     $(rustc --version 2>&1 || echo '未安装')"
echo "Cargo:    $(cargo --version 2>&1 || echo '未安装')"
echo ""
echo "--- API Key ---"
echo "ETHERSCAN:  ${ETHERSCAN_API_KEY:+已配置}${ETHERSCAN_API_KEY:-未配置}"
echo ""
echo "--- RPC ---"
echo "ETH_RPC:    ${ETH_RPC_URL:+已配置}${ETH_RPC_URL:-未配置}"
echo "SOLANA_RPC: ${SOLANA_RPC_URL:+已配置}${SOLANA_RPC_URL:-未配置}"
echo "SUI_RPC:    ${SUI_RPC_URL:+已配置}${SUI_RPC_URL:-未配置}"
echo ""
echo "=== 检查完成 ==="
```

EVM 审核必需：Git, Python, Forge, Cast, Slither, jq。  
Solana 审核必需：Git, Solana CLI, Rust/Cargo；如项目使用 Anchor 框架还需 Anchor CLI。

### 步骤 0.9 — 创建工作目录
```bash
# 创建标准工作目录
mkdir -p ./{Token-Ticker-Name}/{code,docs,info-gathering,security-review}

cd ./{Token-Ticker-Name}/
```

初始目录结构：

```plain
<Token-Ticker-Name>/
├── code/              # 合约代码（克隆仓库、浏览器下载源码）
├── docs/              # 审计输入的材料（简报、白皮书、审计报告等）
├── info-gathering/    # 信息采集过程文件（API 返回、RPC 快照、浏览器补充记录）
└── security-review/   # 审计产出物（报告、扫描结果、分析结论）
```

输出物：工具链就绪，API Key 和 RPC 已配置，工作目录创建完成。

---

## 阶段一：信息收集与链上数据采集
目标：无论审计输入何种信息，都尽可能还原完整的代币安全画像。

### 步骤 1.1 — 判断输入类型，确定执行路径
收到项目方材料后，先分类标记：

```plain
收到的输入：
[ ] A — 链上合约地址（一个或多个）
[ ] B — 代码仓库地址
[ ] C — 白皮书 / 官方文档 / 项目官网 / 投研报告
```

同时判断目标链类型：

```plain
链类型：
[ ] EVM 链（Ethereum / BSC / Polygon / Arbitrum / Base 等）→ 步骤 1.2 + 1.6
[ ] Solana                                                  → 步骤 1.2-SOL + 1.6-SOL
[ ] Sui                                                     → 步骤 1.2-SUI + 1.6-SUI
```

执行规则：

+ 拥有哪种输入就执行对应步骤（1.2 ~ 1.4）
+ EVM 链执行步骤 1.2（EVM）+ 1.6（EVM RPC）；Solana 链执行步骤 1.2-SOL + 1.6-SOL；Sui 链执行步骤 1.2-SUI + 1.6-SUI
+ 无论链类型，步骤 1.5（GoPlus 安全检测）是必选步骤（GoPlus 同时支持 EVM、Solana、Sui）
+ 最后执行步骤 1.7 交叉补全

### 步骤 1.2 — 从链上合约地址提取信息
#### 1.2.1 确定目标链
根据地址来源判断目标链：

| 来源 URL 特征 | 链 | Chain ID / 标识 |
| --- | --- | --- |
| etherscan.io | Ethereum | 1 |
| bscscan.com | BSC | 56 |
| polygonscan.com | Polygon | 137 |
| arbiscan.io | Arbitrum | 42161 |
| optimistic.etherscan.io | Optimism | 10 |
| basescan.org | Base | 8453 |
| snowscan.xyz | Avalanche | 43114 |
| solscan.io / explorer.solana.com | Solana | solana |
| 未知 / 自建 L2 | 查 chainlist.org | — |


地址格式快速判断：

+ EVM 地址：`0x` 开头，40 个十六进制字符（如 `0xB8c77482e45F1F44dE1745F52C74426C631bDD52`）
+ Solana 地址：Base58 编码，32-44 个字符，无 `0x` 前缀（如 `So11111111111111111111111111111111111111112`）
+ Sui 类型：`<PACKAGE_ID>::<MODULE>::<TYPE>`（如 `0x03cd...::lineup::LINEUP`）
+ Sui package/object 地址：`0x` + 64 位十六进制（总长 66）

如果是 Solana 地址 → 跳转到步骤 1.2-SOL。  
如果是 Sui 地址或 Coin 类型 → 跳转到步骤 1.2-SUI。  
如果提供的是裸地址且无法判断链，询问审计输入方确认。

#### 1.2.2 优先使用 RPC / API 采集信息，浏览器仅作补充
默认顺序：先用 RPC、官方 API、GoPlus API 采集；仅当以下信息无法通过接口直接获得，或需要人工核对展示状态时，再打开区块浏览器页面补充。

建议将所有原始采集结果统一落盘到 `info-gathering/`，例如：

```plain
info-gathering/
├── goplus-token-security.json
├── rpc-basic-info.json
├── rpc-governance-info.json
├── holders-top10.json
└── browser-notes.md      # 仅在接口无法覆盖时补充
```

优先通过 RPC / API 采集并记录：

```plain
必收集：
- 代币名称 (Name)
- 代币符号 (Symbol)
- 精度 (Decimals)
- 总供应量 (Total Supply)
- 持有者数量 (Holders)
- 合约创建者地址 (Creator)
- 合约创建交易哈希 (Creation Tx)
- 合约是否已验证（Code tab 有绿色勾）
- 是否为代理合约 (Proxy) — 如是，记录 Implementation 地址
- 前 10 大持有者地址和占比 (Holders tab)
- 是否在 DEX 有交易对 (DEX Tracker)

选收集：
- 转账次数 (Transfers)
- 合约余额（是否持有 ETH 或其他代币）
```

采集原则：

+ `name` / `symbol` / `decimals` / `totalSupply` / `owner` / `proxy` / `implementation` 等，优先使用 RPC
+ `creator` / `creation tx` / `源码验证状态` / `DEX 展示信息`，优先使用浏览器 API；无 API 时再人工打开页面
+ `holders` / `holder_count` / `dex` / `buy_tax` / `sell_tax`，优先使用 GoPlus API 或链上 RPC；浏览器仅作交叉核对

#### 1.2.3 获取已验证源代码
方式一：`cast` 命令下载（推荐）

```bash
cast etherscan-source <合约地址> --chain <链名> -d ./code/<合约名>-source
```

方式二：浏览器 API

```bash
curl "https://api.etherscan.io/api?module=contract&action=getsourcecode&address=<地址>&apikey=$ETHERSCAN_API_KEY" \
  | jq '.result[0]' > contract-info.json

# 关键字段：SourceCode, ContractName, CompilerVersion, Proxy, Implementation
```

方式三：手动从浏览器 "Contract" → "Code" 页面复制/下载。

#### 1.2.4 处理代理合约
```bash
# 读取 Implementation 地址（EIP-1967 标准槽位）
cast implementation <代理地址> --rpc-url $ETH_RPC_URL

# 读取 Admin 地址
cast admin <代理地址> --rpc-url $ETH_RPC_URL

# 下载 Implementation 源码
cast etherscan-source <Implementation地址> --chain <链名> -d ./code/<合约名>-impl
```

记录 Proxy 类型：Transparent / UUPS / Beacon / Diamond / 自定义。

#### 1.2.5 合约未验证的处理
```bash
# 获取字节码
cast code <合约地址> --rpc-url $ETH_RPC_URL > bytecode.hex

# 反编译
cast disassemble <合约地址> --rpc-url $ETH_RPC_URL
```

在线反编译：

+ Dedaub: [https://app.dedaub.com/decompile](https://app.dedaub.com/decompile)
+ Heimdall: [https://heimdall.rs/](https://heimdall.rs/)
+ ethervm.io: [https://ethervm.io/decompile](https://ethervm.io/decompile)

合约未验证 = 高风险红旗，在报告中必须标注。

### 步骤 1.2-SOL — 从 Solana 链上地址提取信息
当目标代币部署在 Solana 链时，使用以下流程替代步骤 1.2。

#### 1.2-SOL.1 浏览器信息提取
Solana 主要浏览器：

+ Solscan: `https://solscan.io/token/<mint地址>`
+ Solana Explorer: `https://explorer.solana.com/address/<mint地址>`
+ SolanaFM: `https://solana.fm/address/<mint地址>`

在浏览器中记录：

```plain
必收集：
- Mint 地址 (Token Mint Address)
- 代币名称 / 符号
- 精度 (Decimals)
- 总供应量 (Supply)
- 持有者数量 (Holders)
- Mint Authority（是否仍存在 = 可增发）
- Freeze Authority（是否仍存在 = 可冻结账户）
- Update Authority（Metadata 更新权限）
- 代币标准：SPL Token / Token-2022 (Token Extensions)
- 创建者地址和创建交易

选收集：
- 前 N 大持有者地址和占比
- 是否有交易对（Raydium / Jupiter / Orca 等）
- Token Extensions 启用列表（如使用 Token-2022）
```

#### 1.2-SOL.2 Solana CLI 链上数据读取
```bash
RPC=$SOLANA_RPC_URL
MINT="<Mint地址>"

# --- 代币基本信息 ---
# 查看 Mint Account 详情（supply, decimals, mint authority, freeze authority）
spl-token display $MINT --url $RPC

# 或使用 solana account 查看原始数据
solana account $MINT --url $RPC --output json | jq '.data'
```

#### 1.2-SOL.3 关键权限检查（Solana 特有）
Solana SPL Token 有三个关键权限，是风险判定核心关注点：

```bash
# 查看 Mint Account 的 authority 信息
spl-token display $MINT --url $RPC

# 输出中关注：
# - Mint authority: <地址> 或 (not set)
#   → 有值 = 可增发（高风险）; (not set) = 已放弃增发权限（安全）
#
# - Freeze authority: <地址> 或 (not set)
#   → 有值 = 可冻结任意持有者账户（高风险）; (not set) = 安全
```

Authority 判定规则（风险判定）：

| Authority | 状态 | 风险等级 | 判定 |
| --- | --- | --- | --- |
| Mint Authority | (not set) | 低 | 安全，不可增发 |
| Mint Authority | 存在 (EOA) | 高 | 单人可无限增发 |
| Mint Authority | 存在 (Multisig) | 中 | 需确认多签配置 |
| Freeze Authority | (not set) | 低 | 安全 |
| Freeze Authority | 存在 | 高 | 可冻结用户资产 |


#### 1.2-SOL.4 Token-2022 (Token Extensions) 检查
如果代币使用 Token-2022 标准，需要额外检查启用的 Extensions：

```bash
# 查看 Token-2022 账户的 extensions
spl-token display $MINT --url $RPC --program-id TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb

# 高风险 Extensions：
# - TransferFee           → 有转账税（买入/卖出可能收费）
# - PermanentDelegate     → 永久委托人可随时转走任何人的代币（极高风险）
# - TransferHook          → 自定义转账钩子（可能隐藏恶意逻辑）
# - ConfidentialTransfer  → 隐私转账（合规风险）
# - NonTransferable       → 不可转让（灵魂绑定代币）
#
# 中性/低风险 Extensions：
# - MetadataPointer       → 链上 Metadata
# - InterestBearingConfig → 计息配置
# - DefaultAccountState   → 默认账户状态（可能默认冻结）
# - MintCloseAuthority    → 可关闭 Mint 账户
# - GroupPointer          → 代币分组
```

#### 1.2-SOL.5 持有者集中度分析
```bash
# 查看代币最大持有者（Solana RPC 原生支持）
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getTokenLargestAccounts",
  "params": ["'$MINT'"]
}' | jq '.result.value[:10]'

# 返回格式：[{address, amount, decimals, uiAmount, uiAmountString}]

# 查看特定地址的代币余额
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getTokenAccountsByOwner",
  "params": [
    "<持有者地址>",
    {"mint": "'$MINT'"},
    {"encoding": "jsonParsed"}
  ]
}' | jq '.result.value[].account.data.parsed.info'
```

#### 1.2-SOL.6 程序（合约）源码获取
Solana 程序的源码验证与 EVM 不同：

```bash
# 检查程序是否已在 Solana Explorer 上验证（Anchor Verified）
# 访问: https://explorer.solana.com/address/<程序ID>
# 或: https://solscan.io/account/<程序ID>

# 检查程序是否可升级
solana program show $MINT --url $RPC 2>/dev/null
# 如果是程序账户，输出中关注：
# - Authority: <地址> 或 none
#   → 有 Authority = 程序可升级（类似 EVM proxy）
#   → none = 不可升级（immutable）
```

注意：多数 Solana SPL 代币使用标准的 Token Program 或 Token-2022 Program，无需审计程序代码本身，重点关注 Mint/Freeze Authority 和 Token Extensions。仅当代币有自定义程序逻辑时，才需要深入代码审查。

### 步骤 1.2-SUI — 从 Sui 链上地址提取信息
当目标代币部署在 Sui 链时，使用以下流程替代步骤 1.2。

#### 1.2-SUI.1 浏览器信息提取
Sui 常用浏览器：

+ SuiScan: `https://suiscan.xyz/mainnet/object/<package>`
+ SuiVision: `https://suivision.xyz/object/<package>`
+ Sui Explorer: `https://suiexplorer.com/object/<package>`

记录以下字段：

```plain
必收集：
- Coin 类型（Coin<T> 的 T）
- Package 地址、模块名、类型名
- CoinMetadata 对象状态
- 总供应量（suix_getTotalSupply）
- TreasuryCap 是否存在、持有者类型
- UpgradeCap 是否存在、policy 值
- Package 版本与升级历史

选收集：
- 关键对象 owner 类型（AddressOwner/ObjectOwner/Shared/Immutable）
- 是否存在 shared_object 敏感配置
- Move 模块函数可见性（public/public(package)/entry）
```

#### 1.2-SUI.2 Sui RPC/CLI 链上读取
```bash
RPC=${SUI_RPC_URL:-https://fullnode.mainnet.sui.io:443}
COIN_TYPE="<COIN_TYPE>"
PACKAGE_ID="<PACKAGE_ID>"
OBJECT_ID="<OBJECT_ID>"

# Coin 元数据
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"suix_getCoinMetadata","params":["'"$COIN_TYPE"'"]}'

# 总供应量
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"suix_getTotalSupply","params":["'"$COIN_TYPE"'"]}'

# 对象详情（TreasuryCap / UpgradeCap / CoinMetadata）
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getObject","params":["'"$OBJECT_ID"'",{"showType":true,"showOwner":true,"showContent":true}]}'

# 标准化模块
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getNormalizedMoveModulesByPackage","params":["'"$PACKAGE_ID"'"]}'

# CLI 辅助
sui client object $OBJECT_ID --json
sui client objects <ADDRESS> --json
sui client balance <ADDRESS>

# GoPlus Sui Token Security
curl "https://api.gopluslabs.io/api/v1/sui/token_security?contract_addresses=$COIN_TYPE"
```

#### 1.2-SUI.3 Authority 风险判定

| 对象/能力 | 状态 | 风险等级 | 风险判定 |
| --- | --- | --- | --- |
| TreasuryCap | Owner=AddressOwner(EOA) | 高 | 单点可继续铸币 |
| TreasuryCap | Owner=ObjectOwner | 中 | 需继续审计父对象权限 |
| TreasuryCap | Owner=Shared | 高 | 共享铸币能力，风险极高 |
| TreasuryCap | 已销毁 | 低 | 铸币权锁死 |
| UpgradeCap | policy=0 | 高 | 兼容升级，可改逻辑 |
| UpgradeCap | policy=128 | 中 | 仅加法升级 |
| UpgradeCap | policy=192 (DEP_ONLY) | 低 | 仅依赖变更 |
| UpgradeCap | 已 make_immutable() / UpgradeCap 已销毁 | 极低 | 不可升级 |
| CoinMetadata | Owner=Immutable | 低 | 元数据冻结 |
| CoinMetadata | Owner=AddressOwner | 中 | 元数据可变更 |

### 步骤 1.3 — 从代码仓库收集信息
```bash
# 快速了解仓库概况（无需先克隆）
gh api repos/<owner/repo> | jq '{name, description, language, default_branch, created_at, updated_at, license}'

# 最近提交活动
gh api repos/<owner/repo>/commits --jq '.[0:5] | .[] | {date: .commit.author.date, message: .commit.message}'

# 检查 audit/ 目录
gh api repos/<owner/repo>/contents/audit 2>/dev/null | jq '.[].name'
```

从仓库 README 中提取：项目描述、依赖库版本、合约地址、审计报告链接、关联仓库。

### 步骤 1.4 — 项目背景信息收集：从白皮书/官方文档/项目官网/内部投研报告收集信息
优先阅读并交叉整理以下材料：

+ 白皮书 / Litepaper
+ 官方文档 / Docs
+ 项目官网
+ 内部投研报告 / 项目简报

逐页阅读核心文档页：

+ Overview / 项目概述
+ Tokenomics / 代币经济模型
+ Security / 安全概述
+ Risk / 风险说明
+ Governance / 治理架构
+ Contract Addresses / 合约地址
+ 桥/Vault/核心应用机制说明（如有）

记录要点：

+ 代币标准和特殊功能（通胀、锁定、质押、销毁等）
+ 角色与权限设计
+ 多签配置与 timelock
+ 第三方依赖清单
+ 已知风险和缓解措施
+ 所有合约地址和对应链
+ 团队构成与背景
+ 融资历史和估值
+ 代币分配比例与解锁计划
+ 做市商信息
+ 已识别的业务风险

### 步骤 1.5 — GoPlus 安全检测（必选）
GoPlus 提供自动化的代币安全风险标签检测，是风险判定的核心数据源之一。

#### 1.5.1 Token Security API
```bash
# 代币安全检测（核心 API）
# EVM 链使用数字 Chain ID，Solana 使用字符串 "solana"
CHAIN_ID=1          # EVM: 1/56/137/42161/10/8453... Solana: "solana"
TOKEN_ADDR="<合约地址>"

curl -s "https://api.gopluslabs.io/api/v1/token_security/${CHAIN_ID}?contract_addresses=${TOKEN_ADDR}" \
  | jq '.result' > info-gathering/goplus-token-security.json
```

返回字段及风险判定关注重点：

```plain
致命风险标签（任一命中 → 判定为高风险）：
- is_honeypot: "1"                 → 蜜罐代币，用户买入后无法卖出
- is_airdrop_scam: "1"            → 空投诈骗代币
- is_true_token: "0"              → 假冒代币（假 USDT / 假 BNB 等）

高风险标签（中风险，需深入分析确认）：
- is_open_source: "0"             → 合约未开源（无法审计）
- is_proxy: "1"                   → 代理合约（可升级 = 可改逻辑）
- is_mintable: "1"                → 可增发（需检查限制条件）
- owner_change_balance: "1"       → Owner 可直接修改余额
- can_take_back_ownership: "1"    → 可取回已放弃的所有权
- hidden_owner: "1"               → 存在隐藏 Owner
- selfdestruct: "1"               → 合约可自毁
- external_call: "1"              → 存在外部调用（可能隐藏恶意逻辑）

注意标签（需人工确认具体实现）：
- is_blacklisted: "1"             → 有黑名单功能（不等于恶意）
- transfer_pausable: "1"          → 转账可暂停
- cannot_sell_all: "1"            → 不能一次性卖出全部
- cannot_buy: "1"                 → 无法买入
- trading_cooldown: "1"           → 交易冷却期
- is_anti_whale: "1"              → 有反鲸鱼机制
- anti_whale_modifiable: "1"      → 反鲸鱼参数可修改
- slippage_modifiable: "1"        → 滑点可修改
- personal_slippage_modifiable: "1" → 可针对个人设置滑点

业务数据字段（纳入报告）：
- token_name / token_symbol       → 代币名称/符号
- total_supply                    → 总供应量
- holder_count                    → 持有者数量
- lp_holder_count                 → LP 持有者数量
- lp_total_supply                 → LP 总供应量
- buy_tax / sell_tax              → 买入/卖出税率
- owner_address                   → Owner 地址
- creator_address                 → 创建者地址
- holders                         → 前 N 大持有者（地址 + 占比 + 是否合约 + 是否锁定）
- lp_holders                      → LP 持有者（地址 + 占比 + 是否锁定）
- dex                             → 上线的 DEX 列表（名称 + 流动性）
```

#### 1.5.2 地址安全 API（检查 Owner 和大户地址）
```bash
# 检查 Owner 地址是否关联恶意行为
curl -s "https://api.gopluslabs.io/api/v1/address_security/${TOKEN_OWNER_ADDR}?chain_id=${CHAIN_ID}" \
  | jq '.result'

# 返回字段：
# - malicious_address: 是否恶意地址
# - contract_address: 是否合约地址（多签判断线索）
```

#### 1.5.3 合约安全 API（可选，补充检测）
```bash
# 合约安全检测（功能与 token_security 有重叠，但额外检查恶意行为）
curl -s "https://api.gopluslabs.io/api/v1/contract_security/${TOKEN_ADDR}?chain_id=${CHAIN_ID}" \
  | jq '.result'
```

#### 1.5.4 批量处理（多个代币同时审核）
```bash
# GoPlus 支持一次查询多个合约地址（逗号分隔，最多 100 个）
ADDRS="0xaaa...,0xbbb...,0xccc..."
curl -s "https://api.gopluslabs.io/api/v1/token_security/${CHAIN_ID}?contract_addresses=${ADDRS}" \
  | jq '.result'
```

### 步骤 1.6 — RPC 链上数据直接读取（必选）
GoPlus 数据存在延迟和覆盖不全的情况，RPC 直读链上状态是验证和补全的必要手段。
除非接口无法提供，否则不应以手工打开浏览器页面作为首选采集方式。

#### 1.6.1 代币基本信息读取
```bash
RPC=$ETH_RPC_URL   # 按目标链修改
ADDR="<合约地址>"

# --- 基本信息 ---
cast call $ADDR "name()(string)" --rpc-url $RPC
cast call $ADDR "symbol()(string)" --rpc-url $RPC
cast call $ADDR "decimals()(uint8)" --rpc-url $RPC
cast call $ADDR "totalSupply()(uint256)" --rpc-url $RPC
```

#### 1.6.2 权限与治理读取
```bash
# --- Owner / Admin ---
# Ownable 模式
cast call $ADDR "owner()(address)" --rpc-url $RPC 2>/dev/null

# AccessControl 模式 — 检查 DEFAULT_ADMIN_ROLE 持有者
# DEFAULT_ADMIN_ROLE = 0x0000...0000
cast call $ADDR "hasRole(bytes32,address)(bool)" "0x0000000000000000000000000000000000000000000000000000000000000000" "<待检查地址>" --rpc-url $RPC

# Proxy — Implementation 和 Admin
cast implementation $ADDR --rpc-url $RPC 2>/dev/null
cast admin $ADDR --rpc-url $RPC 2>/dev/null

# Timelock — 读取最小延迟
cast call $ADDR "getMinDelay()(uint256)" --rpc-url $RPC 2>/dev/null
```

#### 1.6.3 代币功能特性读取
```bash
# --- Mint / Burn / Pause ---
# 检查暂停状态
cast call $ADDR "paused()(bool)" --rpc-url $RPC 2>/dev/null

# 检查是否有 cap（供应量上限）
cast call $ADDR "cap()(uint256)" --rpc-url $RPC 2>/dev/null

# 检查税率（自定义代币常见）
cast call $ADDR "buyTax()(uint256)" --rpc-url $RPC 2>/dev/null
cast call $ADDR "sellTax()(uint256)" --rpc-url $RPC 2>/dev/null
cast call $ADDR "transferFee()(uint256)" --rpc-url $RPC 2>/dev/null

# 检查黑名单/白名单函数是否存在（call 失败说明函数不存在）
cast call $ADDR "isBlacklisted(address)(bool)" "0x0000000000000000000000000000000000000001" --rpc-url $RPC 2>/dev/null
cast call $ADDR "isWhitelisted(address)(bool)" "0x0000000000000000000000000000000000000001" --rpc-url $RPC 2>/dev/null
```

#### 1.6.4 持有者集中度分析
```bash
# 查询指定地址余额
cast call $ADDR "balanceOf(address)(uint256)" "<持有者地址>" --rpc-url $RPC

# 批量查询前 N 大持有者（地址优先从 GoPlus/API 获取，浏览器 Holders tab 仅作补充）
for holder in 0xAAA 0xBBB 0xCCC; do
  balance=$(cast call $ADDR "balanceOf(address)(uint256)" $holder --rpc-url $RPC)
  echo "$holder: $balance"
done

# 检查某地址是否为合约（EOA vs Contract）
cast code <持有者地址> --rpc-url $RPC
# 返回 "0x" 表示 EOA，否则是合约
```

#### 1.6.5 存储槽直读（高级）
当合约接口信息不完整时，直接读取存储槽：

```bash
# EIP-1967 标准槽位
# Implementation 槽: 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
cast storage $ADDR 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc --rpc-url $RPC

# Admin 槽: 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
cast storage $ADDR 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103 --rpc-url $RPC

# Ownable owner 通常在 slot 0
cast storage $ADDR 0 --rpc-url $RPC
```

#### 1.6.6 GoPlus 与 RPC 数据交叉验证
将 GoPlus 返回数据与 RPC 直读结果对比，标记差异：

| 字段 | GoPlus 值 | RPC 直读值 | 是否一致 |
| --- | --- | --- | --- |
| totalSupply | — | — | — |
| owner_address | — | — | — |
| is_proxy | — | — | — |
| paused | — | — | — |


差异项需在报告中说明，以 RPC 直读结果为准。

### 步骤 1.6-SOL — Solana 链上数据直接读取（Solana 代币必选）
当目标代币在 Solana 链上时，使用以下步骤替代步骤 1.6。

#### 1.6-SOL.1 代币基本信息
```bash
RPC=$SOLANA_RPC_URL
MINT="<Mint地址>"

# 完整 Mint Account 信息（supply, decimals, authority）
spl-token display $MINT --url $RPC

# 通过 RPC JSON-RPC 获取（可解析更多字段）
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getAccountInfo",
  "params": ["'$MINT'", {"encoding": "jsonParsed"}]
}' | jq '.result.value.data.parsed.info'

# 返回字段：mintAuthority, supply, decimals, isInitialized, freezeAuthority
```

#### 1.6-SOL.2 权限状态
```bash
# 确认 Mint Authority（是否可增发）
spl-token display $MINT --url $RPC | grep -i "mint authority"

# 确认 Freeze Authority（是否可冻结）
spl-token display $MINT --url $RPC | grep -i "freeze authority"

# 如果代币有关联程序（非标准 SPL Token），检查程序升级权限
PROGRAM_ID="<程序地址>"
solana program show $PROGRAM_ID --url $RPC
# 关注 Authority 字段: 有值=可升级, none=不可升级
```

#### 1.6-SOL.3 持有者集中度
```bash
# 前 20 大持有者
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getTokenLargestAccounts",
  "params": ["'$MINT'"]
}' | jq '.result.value'

# Token Supply（总供应量）
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getTokenSupply",
  "params": ["'$MINT'"]
}' | jq '.result.value'
```

#### 1.6-SOL.4 Token-2022 Extensions 详细信息
```bash
# 如果是 Token-2022 代币，获取 extension 详情
curl -s $RPC -X POST -H "Content-Type: application/json" -d '{
  "jsonrpc": "2.0", "id": 1,
  "method": "getAccountInfo",
  "params": ["'$MINT'", {"encoding": "jsonParsed"}]
}' | jq '.result.value.data.parsed.info.extensions'

# 关键检查项：
# - TransferFee: 查看 transferFeeBasisPoints（费率）和 maximumFee
# - PermanentDelegate: 检查 delegate 地址（极高风险）
# - TransferHook: 检查 hookProgramId（需审计该程序）
# - DefaultAccountState: 如为 "frozen"，新账户默认冻结
```

#### 1.6-SOL.5 GoPlus 与链上数据交叉验证（Solana 版）
| 字段 | GoPlus 值 | Solana RPC 值 | 是否一致 |
| --- | --- | --- | --- |
| total_supply | — | — | — |
| is_mintable (Mint Authority) | — | — | — |
| owner_address / creator | — | — | — |
| is_open_source | — | — | — |


### 步骤 1.6-SUI — Sui 链上数据直接读取（Sui 代币必选）

#### 1.6-SUI.1 核心对象采集
```bash
RPC=${SUI_RPC_URL:-https://fullnode.mainnet.sui.io:443}
COIN_TYPE="<COIN_TYPE>"
PACKAGE_ID="<PACKAGE_ID>"
TREASURY_CAP_ID="<TREASURY_CAP_OBJECT_ID>"
UPGRADE_CAP_ID="<UPGRADE_CAP_OBJECT_ID>"
METADATA_ID="<COIN_METADATA_OBJECT_ID>"

curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"suix_getCoinMetadata","params":["'"$COIN_TYPE"'"]}' | jq '.'
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"suix_getTotalSupply","params":["'"$COIN_TYPE"'"]}' | jq '.'
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getObject","params":["'"$TREASURY_CAP_ID"'",{"showType":true,"showOwner":true,"showContent":true}]}' | jq '.'
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getObject","params":["'"$UPGRADE_CAP_ID"'",{"showType":true,"showOwner":true,"showContent":true}]}' | jq '.'
curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getObject","params":["'"$METADATA_ID"'",{"showType":true,"showOwner":true,"showContent":true}]}' | jq '.'
```

#### 1.6-SUI.2 模块与升级面读取
```bash
RPC=${SUI_RPC_URL:-https://fullnode.mainnet.sui.io:443}
PACKAGE_ID="<PACKAGE_ID>"

curl -X POST $RPC -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"sui_getNormalizedMoveModulesByPackage","params":["'"$PACKAGE_ID"'"]}' | jq '.' > info-gathering/sui-modules.json

sui client object $PACKAGE_ID --json > info-gathering/sui-package-object.json
```

#### 1.6-SUI.3 GoPlus 与 RPC 交叉验证（Sui 版）
| 字段 | GoPlus 值 | Sui RPC 值 | 是否一致 |
| --- | --- | --- | --- |
| total_supply | — | — | — |
| token_name/symbol | — | — | — |
| TreasuryCap 状态 | — | — | — |
| UpgradeCap policy | — | — | — |
| CoinMetadata owner | — | — | — |

### 步骤 1.7 — 信息交叉补全
无论初始输入类型如何，确保以下信息矩阵尽量完整：

```plain
信息补全清单（通用）：
[ ] 合约/代币地址（所有链）
[ ] 合约/程序源码（已验证 / 仓库 / 反编译 / 未获取）
[ ] 代币基本信息（名称、符号、精度、总量）— 来源：浏览器 + RPC
[ ] GoPlus 安全检测结果（所有风险标签）
[ ] 代币分配与解锁计划 — 来源：白皮书 / 简报
[ ] 持有者分布（前 10 大）— 来源：浏览器 + GoPlus + RPC
[ ] DEX 流动性状态 — 来源：GoPlus + 浏览器
[ ] 已有审计报告 — 来源：仓库 audit/ + 官网
[ ] 团队信息 — 来源：简报 / 官网
[ ] 官方文档/白皮书

EVM 特有：
[ ] 代理合约信息（类型、Implementation 地址）— 来源：RPC + 浏览器
[ ] Owner/Admin 地址及多签配置 — 来源：RPC + GoPlus
[ ] 买入/卖出税率 — 来源：GoPlus + RPC

Solana 特有：
[ ] Mint Authority 状态（放弃 / EOA / 多签）
[ ] Freeze Authority 状态（放弃 / 存在）
[ ] 代币标准（SPL Token / Token-2022）
[ ] Token-2022 Extensions 列表（如适用）
[ ] 程序 Upgrade Authority（自定义程序时）

Sui 特有：
[ ] Coin<T> 类型与 CoinMetadata 一致性
[ ] TreasuryCap 生命周期（存在 / 已销毁 / 持有者类型）
[ ] UpgradeCap policy 与持有者身份
[ ] OTW 模式与唯一 TreasuryCap 校验
[ ] 关键对象 owner 类型（AddressOwner/ObjectOwner/Shared/Immutable）
[ ] Package 模块面（sui_getNormalizedMoveModulesByPackage）
```

反向查找策略：

+ 有地址无仓库 → 浏览器验证页 metadata 找 GitHub 链接；搜索 `site:github.com <合约名>`
+ 有仓库无地址 → 仓库 README / deploy scripts / broadcast/ 目录
+ 有白皮书无地址 → 白皮书尾部"合约地址"章节或官网
+ 有地址无文档 → 合约 Creator 的 ENS 域名或链上活动推断项目方
+ 有地址无 RPC → chainlist.org 按 Chain ID 查找

输出物：GoPlus 检测结果 JSON、RPC 链上数据记录、信息矩阵填写完成。

---

## 阶段二：合约代码获取与环境搭建
目标：将合约代码下载到本地，确保可编译运行。

### 步骤 2.0-SUI — 三链工作目录与步骤编号约定

```plain
workdir/
├── info-gathering/          # API 返回、RPC 快照、浏览器补充记录
├── evm/                  # EVM 链审计数据
├── solana/               # Solana 链审计数据
├── sui/                  # Sui 链审计数据
│   ├── package_info/     # package 信息、模块列表
│   ├── objects/          # TreasuryCap / UpgradeCap / CoinMetadata 快照
│   └── code/             # Move 源码或反编译产物
├── reports/              # 输出报告
└── evidence/             # 审计证据
```

Sui 特有步骤统一使用 `-SUI` 后缀，例如：`步骤 2.4-SUI`、`步骤 3.3-SUI`。

### 步骤 2.1 — 获取合约源码
按优先级选择获取方式：

所有代码统一放入 `code/` 目录：

路径 A — 有 GitHub 仓库（最佳）

```bash
cd code/
git clone <代币合约仓库URL>
git clone <桥/Vault合约仓库URL>
```

确认：commit/tag 与审计目标一致；检查 audit/ 和 certora/ 目录。

**审计版本锚定（所有路径通用）：**

```bash
# 克隆或下载代码后，立即记录审计版本
cd code/<仓库目录>
echo "审计版本: $(git rev-parse HEAD 2>/dev/null || echo 'N/A - 非 Git 仓库')" > ../../security-review/audit-commit.txt
echo "分支/Tag: $(git describe --tags --always 2>/dev/null || echo 'N/A')" >> ../../security-review/audit-commit.txt
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')" >> ../../security-review/audit-commit.txt
cd -
```

路径 B — 仅有地址，合约已验证

```bash
export ETHERSCAN_API_KEY=<key>
cd code/
cast etherscan-source <合约地址> --chain <链名> -d ./<合约名>-source

# 代理合约同时下载 Implementation
cast etherscan-source <Implementation地址> --chain <链名> -d ./<合约名>-impl
```

下载后手动组织为可编译项目：

```bash
cd <合约名>-source
forge init --no-commit --no-git .
# 将源码移入 src/，调整 remappings.txt
```

路径 C — 仅有地址，合约未验证

```bash
cd code/
cast code <合约地址> --rpc-url $ETH_RPC_URL > bytecode.hex
# 使用 Dedaub / Heimdall 反编译
```

Slither 无法分析未验证合约。此场景重点依赖阶段一的 GoPlus + RPC 数据，在报告中标注"合约未验证"为高风险项，要求项目方补充源码。

路径 D — Solana 项目

```bash
cd code/
git clone <Solana 程序仓库URL>
```

注意：多数 Solana SPL 代币使用标准 Token Program 或 Token-2022，无自定义代码。仅当代币有自定义链上程序（如自定义 Transfer Hook、自定义 AMM、质押程序等）时才需要克隆和编译代码。

### 步骤 2.1.1 — 供应链安全检查
代码获取后、编译前，先检查第三方依赖的已知漏洞：

```bash
# EVM (Node 依赖)
npm audit --audit-level=moderate 2>/dev/null || echo "无 package.json"

# Solana / Rust
cargo audit 2>&1 | tee ../../security-review/cargo-audit-<程序名>-output.txt

# 通用：检查 lock 文件完整性（lock 文件未提交 = 依赖版本不可复现）
ls package-lock.json yarn.lock pnpm-lock.yaml Cargo.lock 2>/dev/null || echo "警告：无 lock 文件"
```

### 步骤 2.2 — 识别构建系统
```bash
cd code/<仓库目录>
ls foundry.toml      # Foundry
ls hardhat.config.*  # Hardhat
ls soldeer.lock      # Soldeer 包管理
ls .gitmodules       # git submodule
ls package.json      # Node 依赖
ls remappings.txt    # import 映射
```

### 步骤 2.3 — 安装依赖
```bash
# ---- EVM: Foundry + Soldeer ----
forge soldeer install && npm install && forge build

# ---- EVM: Foundry + git submodule ----
forge install && forge build

# ---- EVM: Hardhat ----
npm install && npx hardhat compile

# ---- EVM: 混合项目 ----
npm install && forge soldeer install && forge build

# ---- Solana: Anchor 项目 ----
anchor build

# ---- Solana: 原生 Rust 项目 ----
cargo build-bpf
```

### 步骤 2.4 — 编译验证
```bash
forge build
# 期望：Compiler run successful
```

常见问题：

| 错误 | 解决方案 |
| --- | --- |
| `forge not found` | 回到阶段零步骤 0.2 |
| import 路径找不到 | 重新 `forge soldeer install` 或 `forge install`，检查 remappings.txt |
| Solidity 版本不匹配 | 检查 foundry.toml 的 `solc_version` |
| `Stack too deep` | `forge build --via-ir` |
| npm 依赖冲突 | `rm -rf node_modules && npm install` |


### 步骤 2.4-SUI — Move 代码获取与落盘
```bash
# 目录准备
mkdir -p workdir/sui/{package_info,objects,code}

# 通过 Sui RPC 获取模块定义
curl -X POST ${SUI_RPC_URL:-https://fullnode.mainnet.sui.io:443}   -H "Content-Type: application/json"   -d '{"jsonrpc":"2.0","id":1,"method":"sui_getNormalizedMoveModulesByPackage","params":["<PACKAGE_ID>"]}'   > workdir/sui/package_info/normalized-modules.json

# 获取 package 对象与 capability 对象
sui client object <PACKAGE_ID> --json > workdir/sui/objects/package.json
sui client object <TREASURY_CAP_OBJECT_ID> --json > workdir/sui/objects/treasury_cap.json
sui client object <UPGRADE_CAP_OBJECT_ID> --json > workdir/sui/objects/upgrade_cap.json
sui client object <COIN_METADATA_OBJECT_ID> --json > workdir/sui/objects/coin_metadata.json
```

输出物：合约编译通过，项目结构清晰。

---

## 阶段三：静态分析扫描
目标：通过自动化工具发现代码级安全问题。采用分层扫描策略，按需逐层深入。

### 扫描分层策略

| 层级 | 耗时 | 工具 | 适用场景 |
| --- | --- | --- | --- |
| **L1 快速扫描** | <5 min | Aderyn + 4naly3er + clippy | 所有项目必跑；快速审查路径仅需此层 |
| **L2 深度扫描** | ~30 min | Slither + Pattern Scanner + cargo-audit | 完整审计必跑 |
| **L3 可选深度** | 1~4 h | Mythril 符号执行 / Echidna Fuzzing / Move Prover | 复杂 DeFi 代币（Vault/Rebase/Fee-on-transfer）或高价值项目按需启用 |

### 步骤 3.1 — L1 快速扫描

EVM 项目：

```bash
cd code/<仓库目录>
OUT=../../security-review

# Aderyn — Rust 实现，极速，输出 Markdown 报告
aderyn . --output $OUT/aderyn-<合约名>-report.md 2>&1 | tee $OUT/aderyn-<合约名>-output.txt

# 4naly3er — 竞赛向，覆盖 Low/NC/Gas 级发现
4naly3er . > $OUT/4naly3er-<合约名>-output.md 2>&1 || echo "4naly3er 未安装，跳过"
```

Solana 项目：

```bash
cd code/<仓库目录>
OUT=../../security-review

# cargo clippy — Rust 官方 linter
cargo clippy --all-targets 2>&1 | tee $OUT/clippy-<程序名>-output.txt

# cargo-geiger — unsafe 代码比例统计
cargo geiger --all-features 2>&1 | tee $OUT/geiger-<程序名>-output.txt || echo "cargo-geiger 未安装，跳过"
```

Sui 项目：

```bash
# L1 使用自研 Pattern Scanner（Scan_Script/sui_scanner.py）
python3 ../Scan_Script/sui_scanner.py --package-dir workdir/sui/ --output $OUT/sui-scan-<项目名>-output.json
```

### 步骤 3.2 — L2 深度扫描

EVM 项目 — Slither：

```bash
cd code/<仓库目录>
OUT=../../security-review

slither . --foundry-compile-all 2>&1 | tee $OUT/slither-<合约名>-output.txt

# Pattern Scanner — 自研 33 项 Solidity 模式匹配（Scan_Script/pattern_scanner.py）
python3 ../Scan_Script/pattern_scanner.py --source ./src/ --output $OUT/pattern-<合约名>-output.json
```

Solana 项目：

```bash
cd code/<仓库目录>
OUT=../../security-review

# cargo audit — 依赖项已知漏洞检查
cargo audit 2>&1 | tee $OUT/cargo-audit-<程序名>-output.txt

# Anchor 项目可运行测试套件
anchor test 2>&1 | tee $OUT/anchor-test-<程序名>-output.txt
```

Sui 项目 — Move 安全扫描 15 类检查：

```bash
# Scan_Script/sui_scanner.py 完整扫描（含深度模式）
python3 ../Scan_Script/sui_scanner.py --package-dir workdir/sui/ --deep --output $OUT/sui-deep-<项目名>-output.json
```

Move 安全扫描 15 类检查项：

1. init 函数分析（含 OTW 初始化模式）
2. 访问控制（AdminCap / TreasuryCap）
3. 铸币能力与上限
4. 暂停功能
5. 转账限制
6. 硬编码敏感信息
7. 未检查返回值
8. 无界循环
9. 不安全类型转换
10. 共享对象权限
11. 升级权限（UpgradeCap）
12. 关键事件缺失
13. 资源管理
14. 算术安全
15. 函数可见性（public/public(package)/entry）

Solana 程序审查更依赖人工代码审计（阶段四），工具覆盖率较低。

### 步骤 3.3 — L3 可选深度扫描（按需）
仅在以下场景启用：复杂 DeFi 代币（Vault/Rebase/Fee-on-transfer）、高价值项目、L1/L2 发现可疑但无法确认时。

EVM 项目：

```bash
cd code/<仓库目录>
OUT=../../security-review

# Mythril — 符号执行（发现条件性重入、整数溢出的实际可触发条件）
myth analyze src/<主合约>.sol --solc-json remappings.json 2>&1 | tee $OUT/mythril-<合约名>-output.txt

# Foundry Fuzz — 基于属性的 Fuzzing（已有 Foundry，零成本启用）
forge test --fuzz-runs 10000 2>&1 | tee $OUT/fuzz-<合约名>-output.txt

# Halmos — 符号执行验证关键不变量（如 totalSupply == sum(balances)）
halmos --contract <合约名> 2>&1 | tee $OUT/halmos-<合约名>-output.txt

# Echidna — 高级 Fuzzing（需编写属性测试）
echidna . --contract <合约名> --config echidna.yaml 2>&1 | tee $OUT/echidna-<合约名>-output.txt

# 存储布局验证（Upgradeable 合约必选）
forge inspect <合约名> storage-layout --json > $OUT/storage-layout-<合约名>.json
```

Solana 项目：

```bash
# Trident — Anchor 程序 Fuzzing
trident fuzz run 2>&1 | tee $OUT/trident-<程序名>-output.txt
```

Sui 项目：

```bash
# Move Prover — 形式化验证（需在源码中编写 spec 块）
sui move prove --path <项目路径> 2>&1 | tee $OUT/move-prover-<项目名>-output.txt

# Move 测试覆盖率
sui move test --coverage --path <项目路径> 2>&1 | tee $OUT/sui-coverage-<项目名>-output.txt
```

### 步骤 3.4 — 分类整理结果
| 严重程度 | 处理方式 |
| --- | --- |
| High | 必须逐条人工研判（真阳/误报） |
| Medium | 必须逐条分析，结合上下文判断 |
| Low | 快速浏览，标记需关注项 |
| Informational | 批量处理，关注代码质量 |


对每条 High/Medium 发现记录：位置、检测器名称、AI 研判结论、实际风险等级、利用条件。

常见误报模式：

+ `arbitrary-send-erc20` — 跨函数 `from` 参数追踪失败
+ `controlled-delegatecall` — Split Contract 模式
+ `incorrect-return` — delegatecall 委托返回
+ `reentrancy-*` — 检查 ReentrancyGuard / nonReentrant
+ `timestamp` — 月级别操作不受矿工操纵影响
+ `too-many-digits` — 数学库常量

输出物：Slither 原始输出文件 + 分类分析。

---

## 阶段四：AI 代码安全审查
目标：利用 AI 深入理解合约逻辑，对阶段三扫描器输出进行误报研判，发现自动化工具无法覆盖的问题。

> **执行方式**：本阶段由 AI 完成，不需要人工逐行审查。AI 读取源码和扫描器输出，交叉验证发现真阳性，标记误报，并输出结构化审查结论。

### 步骤 4.1 — AI 合约概览
AI 阅读合约源码（来自 `code/` 目录或 Etherscan 下载），快速识别：

+ 继承链与合约模式（如 RFI/Rebase/Fee-on-transfer/Vault/Proxy）
+ 状态变量与关键参数（总量、精度、费率、上限等）
+ 角色/权限体系与 modifier
+ 构造函数/初始化参数与默认值
+ 事件定义与触发覆盖率

### 步骤 4.2 — AI 扫描结果误报研判
AI 逐条审查阶段三扫描器（Slither/Aderyn/4naly3er/Pattern Scanner/Sui Scanner）输出的 High/Medium 级发现：

对每条发现记录：

| 字段 | 说明 |
| --- | --- |
| 发现编号 | 扫描器原始编号 |
| 检测器 | 检测器名称（如 `reentrancy-eth`） |
| 位置 | 文件:行号 |
| AI 研判 | **真阳性** / **误报** / **待确认** |
| 理由 | AI 判定理由（引用代码上下文） |
| 实际风险 | Critical / High / Medium / Low / Info / 无 |
| 利用条件 | 触发该漏洞需要的前提条件 |

常见误报模式（AI 应自动识别并标记）：

+ `arbitrary-send-erc20` — 跨函数 `from` 参数追踪失败
+ `controlled-delegatecall` — Split Contract 模式的正常设计
+ `incorrect-return` — delegatecall 委托返回
+ `reentrancy-*` — 已使用 ReentrancyGuard / nonReentrant 保护
+ `timestamp` — 月级别时间操作不受矿工操纵影响
+ `too-many-digits` — 数学库常量

### 步骤 4.3 — AI 核心函数审查
AI 对关键函数进行深度语义分析（不需要人工参与）：

EVM 合约：

| 函数类型 | AI 审查重点 |
| --- | --- |
| mint / inflate | 铸币权限、数量限制、频率限制 |
| burn | 是否只能销毁自己的代币 |
| transfer / _update | 自定义转账限制（锁定、黑名单、暂停、税率） |
| deposit / withdraw | 资产进出逻辑、份额计算、滑点保护 |
| 角色管理 | 两步转移、角色可放弃性 |
| 初始化 | 重初始化保护、参数验证 |
| 升级 | 存储兼容性、升级权限 |
| 紧急操作 | pause / drain / emergency |
| delegatecall | 目标地址控制、存储冲突 |

Solana 程序（如有自定义程序）：

| 指令类型 | AI 审查重点 |
| --- | --- |
| initialize | 是否可重复初始化、Authority 设置是否正确 |
| mint_to | 铸币权限验证、数量限制 |
| transfer / transfer_checked | 自定义限制逻辑、余额校验 |
| burn | signer 验证、是否只能销毁自己的代币 |
| set_authority | Authority 变更验证、是否有时间锁 |
| close_account | lamports 归还、数据清零 |
| CPI 调用 | 目标程序地址硬编码验证、权限传递 |
| Transfer Hook (execute) | 钩子逻辑审查、不可恶意阻止转账 |

### 步骤 4.4 — AI 设计模式识别
AI 自动识别合约使用的设计模式，并评估其安全影响：

EVM 合约模式：

| 模式 | 安全关注点 |
| --- | --- |
| Proxy/Upgradeable | 存储冲突、升级权限、初始化保护 |
| Split Contract (delegatecall) | 存储布局一致性 |
| Diamond Storage (ERC-7201) | 命名空间隔离 |
| ERC-4626 Vault | 份额精度、首存攻击、舍入方向 |
| ReentrancyGuard | 覆盖范围（view 函数不受保护） |
| AccessControl | 角色粒度、admin 权限边界 |
| Permit (EIP-2612) | 签名重放、nonce 管理 |

Solana 程序模式（如有自定义程序）：

| 模式/概念 | 安全关注点 |
| --- | --- |
| Account Validation | 是否对所有传入 Account 做充分校验（owner、discriminator、signer、writable） |
| PDA (Program Derived Address) | seeds 是否唯一、是否验证 bump |
| CPI (Cross-Program Invocation) | 被调用程序地址是否硬编码而非由用户传入 |
| Signer 验证 | 关键操作是否要求正确的 signer |
| 溢出/下溢 | Rust 默认 release 模式不检查溢出，需使用 checked_* 或 Anchor 自带保护 |
| 关闭账户 | 关闭后是否清零 lamports 和数据，防止"复活"攻击 |
| 可升级程序 | 是否有 Upgrade Authority，Authority 是否多签 |
| Token-2022 Hooks | Transfer Hook 程序的逻辑审查 |
| Anchor Constraints | `#[account(...)]` 约束是否充分覆盖所有安全检查 |

### 步骤 4.4-SUI — Sui 特有 AI 审查要点

| 审查点 | 关注重点 |
| --- | --- |
| Ability 配置 | 关键 capability 不应具备 drop ability |
| public(package)+entry | 防止误判权限边界 |
| shared_object 使用 | 敏感对象不应无约束共享 |
| 动态字段键 | 使用强类型键避免碰撞 |
| 升级兼容 | 旧版本入口可达性与绕过风险 |
| Hot Potato 对象 | 无 copy/drop/store 对象是否同交易内消费 |
| 精度与除法 | Move 无浮点，检查截断 |

### 步骤 4.5 — AI 审计报告交叉验证
AI 阅读仓库内已有审计报告并交叉验证：

+ 审计版本与当前版本是否一致
+ 已报告问题的修复状态
+ "Acknowledged"但未修复的问题
+ 各审计方发现的问题数量和分布

输出物：AI 代码审查结论（含误报研判表、合约模式分析、函数权限分析）。

---

## 阶段五：Checklist 逐项评估
目标：系统性覆盖所有已知攻击向量。

### 步骤 5.1 — 获取 Checklist
```bash
curl -o checklist.json https://raw.githubusercontent.com/Cyfrin/audit-checklist/main/checklist.json
```

### 步骤 5.2 — 筛选适用检查项
EVM 合约（Cyfrin Solodit Checklist）：

| 大类 | 适用条件 |
| --- | --- |
| Attacker's Mindset (DOS, Reentrancy, Front-running 等) | 所有合约 |
| Basics (Access Control, Math, Event, Proxy 等) | 所有合约 |
| Centralization Risk | 有权限管理的合约 |
| DeFi (ERC-4626, Oracle, AMM 等) | DeFi 协议合约 |
| External Call | 有外部合约调用的合约 |
| Multi-chain / Cross-chain | 跨链桥、多链部署 |
| Signature | 使用签名验证 (Permit 等) |
| Token: ERC20 | ERC-20 代币合约 |
| Integrations (LayerZero, AAVE 等) | 有特定协议集成 |
| Heuristics | 所有合约 |


Solana 程序（自定义 Checklist，用于有自定义程序的代币）：

| 检查项 | 适用条件 |
| --- | --- |
| Account 验证：所有传入 Account 是否校验 owner、data len、discriminator | 所有 Anchor/Native 程序 |
| Signer 检查：关键操作是否验证 signer | 所有程序 |
| PDA 安全：seeds 唯一性、bump 验证 | 使用 PDA 的程序 |
| CPI 安全：被调用程序地址是否硬编码验证 | 有 CPI 调用的程序 |
| 整数溢出/下溢：是否使用 checked_* 或 Anchor 自动保护 | 所有程序 |
| 账户关闭：lamports 转移、数据清零、防止"复活" | 可关闭账户的程序 |
| Mint/Freeze Authority：是否已放弃或由多签持有 | SPL Token / Token-2022 |
| Token-2022 Extensions：PermanentDelegate、TransferHook 等高危扩展 | Token-2022 代币 |
| 程序可升级性：Upgrade Authority 配置 | 所有可升级程序 |
| Rent Exemption：Account 是否满足免租金要求 | 所有程序 |
| 重入保护：CPI 回调场景是否安全 | 有 CPI 调用的程序 |
| 时间依赖：是否安全使用 Clock sysvar | 依赖时间的程序 |


Sui 合约（Move）补充 Checklist：

| 检查项 | 适用条件 |
| --- | --- |
| Package 是否升级过（version>1） | 所有 Sui package |
| UpgradeCap policy 与持有者 | 可升级 package |
| 是否执行不可变策略（已 make_immutable() 或 UpgradeCap 已销毁） | 可升级 package |
| TreasuryCap 持有者与销毁状态 | Coin<T> |
| 是否出现 Shared TreasuryCap | Coin<T> |
| CoinMetadata owner 是否 Immutable | Coin<T> |
| 是否暴露 metadata update 接口 | 有 metadata 变更逻辑 |
| OTW 约束是否保证单一 TreasuryCap | 使用 one-time witness |
| shared_object 敏感对象是否有版本断言 | 使用共享对象 |
| capability 是否泄漏给外部 | 所有关键 entry |

### 步骤 5.3 — AI 逐项评估
AI 对每个适用检查项标注：PASS / NOTE / FAIL / N/A。每条 NOTE 和 FAIL 附具体说明和代码引用。

输出物：Checklist 评估表（由 AI 直接生成）。

---

## 阶段六：业务风险分析与综合评分
目标：评估代码之外的业务层面风险，并统一输出 D/C/B/A/S 对应风险等级。

### 步骤 6.1 — 代币经济模型分析
| 维度 | 关注指标 |
| --- | --- |
| 供应量 | 初始供应、通胀/通缩机制、硬顶上限 |
| 分配比例 | 团队/基金会/社区/投资者占比 |
| 解锁计划 | cliff 时长、vesting 周期、TGE 释放比例 |
| 稀释指标 | FDV/MC 比值、月释放量占流通比例 |
| 抛压分析 | cliff 解锁节点、大规模释放窗口 |


### 步骤 6.2 — 治理架构分析
| 维度 | 关注指标 |
| --- | --- |
| 多签配置 | 签名者数量/阈值、实体多样性 |
| Timelock | 延迟时长、覆盖范围 |
| 代币治理 | 治理代币控制范围、投票权分布 |
| 透明度 | 会议记录、投票历史、提案流程 |
| 利益冲突 | 多签成员兼任其他角色 |


### 步骤 6.3 — 第三方依赖风险
绘制依赖关系图（Mermaid），评估成熟度、单点故障影响、链条深度（≥4 层需警惕）。

### 步骤 6.4 — 桥/跨链特殊风险（如适用）
| 维度 | 关注指标 |
| --- | --- |
| 准备金模型 | 全额/部分准备金、储备金比例 |
| 提款延迟 | 正常/压力/极端场景 |
| 暂停机制 | 谁可以暂停、恢复条件 |
| 跨链消息验证 | Merkle proof / ZK proof / 乐观 |



### 步骤 6.5 — D/C/B/A/S 评分与风险等级映射（通用）

| 评分 | 等级 | 风险等级语义 |
| --- | --- | --- |
| 0-20 | D | 高风险（存在致命级安全问题） |
| 21-40 | C | 中高风险（存在重大安全隐患） |
| 41-60 | B | 中风险（有待改进的安全问题） |
| 61-80 | A | 低风险（安全状况良好） |
| 81-100 | S | 极低风险（安全标杆） |

Sui 加减分参考（需在综合结论中落地）：

+ `UpgradeCap` 已 `make_immutable()` 或 `UpgradeCap` 已销毁：显著加分
+ `TreasuryCap` 已销毁且供应固定：加分
+ `TreasuryCap` 为 Shared：显著减分
+ `UpgradeCap policy=0` 且 EOA 单持：减分
+ `CoinMetadata` 非 Immutable 且可任意修改：减分

GoPlus 致命标签优先级保持最高：命中时直接归类为高风险。

输出物：业务风险分析笔记。

---

## 阶段七：AI 报告撰写与输出
目标：AI 综合所有采集数据和审查结论，直接生成结构化报告。

> **执行方式**：报告由 AI 直接撰写，不使用 Python 脚本渲染。AI 读取 `audit-manifest.json`、GoPlus JSON、RPC JSON、扫描器输出、阶段四 AI 审查结论等全部证据，参照报告模板（`references/report-templates.md`），生成完整的、可读性高的安全评估报告。

### 步骤 7.1 — AI 生成风险摘要
文件名：`Risk-Summary.md`

AI 综合所有证据，生成面向决策层的风险摘要，包含：

+ 项目元信息卡片（项目名/地址/链/评分/日期）— 不含"结论"字段
+ 合约安全概要表（GoPlus 全量标签 PASS/FAIL 表格）
+ 持仓集中度分析（Top 10 持有者表格 + 集中度判定）
+ 流动性分析（DEX/交易对/LP 持有者/锁定状态）
+ Owner 权限分析（地址/权限/风险等级）
+ 风险标签汇总
+ 编号关注项清单 — 不含"下一步"章节

### 步骤 7.2 — AI 生成综合安全评估报告
文件名：`<项目名>-Token-Security-Assessment.md`

AI 生成 13 节完整报告，所有章节由 AI 基于证据直接撰写：

```plain
报告结构：
1. 审计摘要（关键发现 + 安全亮点 + 主要风险）
2. 项目概述（基本信息 + 技术架构 + 目标链 + 团队融资）
3. 生态架构与资金流向（Mermaid 图）
4. 合约/程序安全评估（AI 代码审查结论，含误报研判）
   - EVM: 智能合约代码审查（AI 分析结论）
   - Solana: Authority 配置 + Token Extensions + 自定义程序审查
5. 静态分析结果（含 AI 误报研判表）
   - EVM: Slither/Aderyn/4naly3er 扫描结果 + AI 研判
   - Solana: Clippy + Cargo Audit 结果
6. GoPlus 安全检测结果（全量字段表格 + 风险标签解读）
7. 链上数据分析（RPC 直读结果 + GoPlus 交叉验证）
8. 代币经济模型分析（分配 + 解锁 + 抛压）
9. 治理架构分析
10. 桥/Vault/跨链风险（如适用）
11. 第三方依赖风险
12. 风险矩阵（可能性 x 严重程度）
13. 建议与缓解措施
```

### 步骤 7.3 — AI 生成 Checklist 评估报告
文件名：`<项目名>-Audit-Checklist-Evaluation.md`

AI 按大类组织 Checklist 表格，每项标注 PASS/FAIL/TODO/N/A 并附证据和备注。末尾包含：

+ PASS/FAIL/TODO/N/A 计数统计
+ 合约级/运营级/市场级风险分类汇总

### 步骤 7.4 — 文件归档
所有审计产出物统一归档。AI 生成的报告直接写入 `security-review/`。

```plain
info-gathering/
├── goplus-token-security.json              # GoPlus 原始返回
├── rpc-basic-info.json                     # RPC 直读的基础字段
├── rpc-governance-info.json                # Owner/Admin/Proxy/Timelock 等
├── holders-top10.json                      # 前 10 大持有者原始数据
├── sui-modules.json                        # Sui 模块面 / 标准化模块
├── sui-package-object.json                 # Sui package 对象快照
└── browser-notes.md                        # 仅接口无法覆盖时补充

security-review/
├── Risk-Summary.md                         # AI 生成：风险摘要
├── <项目名>-Token-Security-Assessment.md   # AI 生成：综合安全评估
├── <项目名>-Audit-Checklist-Evaluation.md  # AI 生成：Checklist 逐项评估
├── slither-<合约名>-output.txt             # EVM: Slither 扫描原始输出
├── aderyn-<合约名>-report.md               # EVM: Aderyn 扫描报告
├── pattern-<合约名>-output.json            # EVM: Pattern Scanner
├── clippy-<程序名>-output.txt              # Solana: Clippy 检查输出
├── cargo-audit-<程序名>-output.txt         # Solana: 依赖漏洞检查输出
├── sui-scan-<项目名>-output.json           # Sui: Scanner 扫描结果
└── audit-commit.txt                        # 审计版本锚定
```

---

## 工作目录标准结构
```plain
Token_Security/<项目名>/
│
├── code/                                   # 合约/程序代码
│   ├── <EVM合约仓库>/                       #   EVM: 克隆的 GitHub 仓库
│   │   ├── src/
│   │   ├── test/
│   │   ├── audit/                          #   仓库自带的审计报告
│   │   └── certora/                        #   形式化验证规范（如有）
│   ├── <Solana程序仓库>/                    #   Solana: 克隆的 Anchor/Native 仓库
│   │   ├── programs/
│   │   ├── tests/
│   │   └── Anchor.toml
│   ├── <关联合约仓库>/                      #   桥/Vault/治理等
│   │   └── ...
│   └── <合约名>-source/                     #   从浏览器下载的已验证源码（无仓库时）
│
├── docs/                                   # 审计输入的原始材料
│   ├── <项目简报>.pdf                       #   内部投研简报
│   ├── <白皮书>.pdf / .docx                 #   项目白皮书
│   ├── <审计报告>.pdf                       #   项目方单独提供的审计报告
│   └── ...                                 #   其他文档
│
├── info-gathering/                         # 信息采集过程文件
│   ├── goplus-token-security.json          #   GoPlus 原始返回
│   ├── rpc-basic-info.json                 #   RPC 基础字段采集
│   ├── rpc-governance-info.json            #   Owner/Admin/Proxy 等
│   ├── holders-top10.json                  #   大户分布原始数据
│   └── browser-notes.md                    #   接口不足时的人工补充记录
│
└── security-review/                        # 审计产出物（全部在此）
    ├── <项目名>-Token-Security-Assessment.md
    ├── <项目名>-Audit-Checklist-Evaluation.md
    
    ├── aderyn-<合约名>-report.md            #   EVM: Aderyn L1 快速扫描
    ├── aderyn-<合约名>-output.txt            #   EVM: Aderyn 控制台输出
    ├── 4naly3er-<合约名>-output.md           #   EVM: 4naly3er L1 扫描
    ├── slither-<合约名>-output.txt           #   EVM: Slither L2 深度扫描
    ├── pattern-<合约名>-output.json          #   EVM: Pattern Scanner L2
    ├── mythril-<合约名>-output.txt           #   EVM: Mythril L3（可选）
    ├── clippy-<程序名>-output.txt            #   Solana: clippy L1
    ├── geiger-<程序名>-output.txt            #   Solana: cargo-geiger L1
    ├── cargo-audit-<程序名>-output.txt       #   Solana: cargo-audit L2
    ├── sui-scan-<项目名>-output.json         #   Sui: Scanner L1/L2
    └── audit-commit.txt                     #   审计版本锚定
```

---

## 质量检查清单
报告提交前逐条确认：

数据采集：

- [ ] GoPlus Token Security API 已查询，致命标签已检查
- [ ] 链上数据采集优先通过 RPC / API 完成：EVM 使用 `cast` / Solana 使用 `spl-token` + JSON-RPC
- [ ] GoPlus 与链上数据交叉验证无重大差异（或差异已说明）
- [ ] 采集过程原始数据已归档到 `info-gathering/`

EVM 特有检查（如适用）：

- [ ] RPC 直读 totalSupply, owner, paused, proxy 状态
- [ ] 代理合约已识别 Implementation 和 Admin

Solana 特有检查（如适用）：

- [ ] Mint Authority 状态已确认（是否已放弃 / 多签持有）
- [ ] Freeze Authority 状态已确认
- [ ] Token-2022 Extensions 已检查（如适用）
- [ ] 程序 Upgrade Authority 已检查（自定义程序）

Sui 特有检查（如适用）：

- [ ] TreasuryCap 生命周期已确认（存在 / 已销毁 / 持有者类型）
- [ ] UpgradeCap policy 与持有者身份已核验
- [ ] CoinMetadata owner 类型已确认（Immutable / AddressOwner）
- [ ] Package 升级历史已检查（version > 1 时审查变更）
- [ ] 关键对象 owner 类型无 Shared 敏感暴露

代码分析（如有源码）：

- [ ] 审计版本已锚定（audit-commit.txt 已记录 commit hash）
- [ ] 供应链检查已完成（npm audit / cargo audit）
- [ ] 所有仓库已克隆并编译通过
- [ ] L1 快速扫描已完成（Aderyn + 4naly3er / clippy + geiger / Sui Scanner）
- [ ] L2 深度扫描已完成（Slither + Pattern Scanner / cargo-audit）
- [ ] L3 可选深度按需执行（Mythril / Echidna / Move Prover）
- [ ] 高/中风险发现都有 AI 研判结论（真阳性/误报/待确认）
- [ ] Checklist 相关检查项已由 AI 逐项评估

报告质量：

- [ ] 结构化报告评分/评级与 AI 审计建议逻辑一致
- [ ] GoPlus 致命标签（蜜罐/空投诈骗/假币）已体现在审计建议中
- [ ] 代码漏洞分析与业务风险分析内容未混杂
- [ ] 综合报告包含风险矩阵
- [ ] 所有审计产出物已归档到 `security-review/`

---

## 快速审查路径（仅有链上地址时）
当项目方仅提供一个合约/代币地址，无源码、无文档时的最小可行审核路径：

### EVM 链快速审查
```plain
步骤 1 → GoPlus Token Security API 查询（Scan_Script/goplus_query.sh）
步骤 2 → RPC 直读链上基本信息（Scan_Script/evm_rpc_query.sh）
步骤 3 → 补充调用浏览器 API；仅在 RPC / API 无法覆盖时再打开页面
步骤 4 → 如合约已验证：下载源码 → L1 快速扫描（Aderyn + 4naly3er）→ AI 代码审查 + 误报研判
         如合约未验证：字节码反编译 + 标注高风险
步骤 5 → GoPlus 致命标签判定（蜜罐/诈骗/假币 → 判定为高风险）
步骤 6 → AI 直接撰写结构化报告
```

### Solana 链快速审查
```plain
步骤 1 → GoPlus Token Security API 查询（chain_id="solana"）
步骤 2 → spl-token display 读取 Mint/Freeze Authority、Supply、Decimals
步骤 3 → RPC getTokenLargestAccounts 检查持有者集中度
步骤 4 → 确认 Token 标准：SPL Token 还是 Token-2022
         如 Token-2022：检查 Extensions（PermanentDelegate / TransferHook = 高风险）
步骤 5 → 如有自定义程序：检查 Upgrade Authority、AI 审查程序逻辑
         如为标准 SPL Token：无需审计程序代码
步骤 6 → GoPlus 致命标签判定 + Authority 综合判定
步骤 7 → AI 直接撰写结构化报告
```

### Sui 链快速审查
```plain
步骤 1 → GoPlus Sui Token Security API 查询
步骤 2 → suix_getCoinMetadata + suix_getTotalSupply 获取代币元数据与总供应量
步骤 3 → sui_getObject 核验 TreasuryCap / UpgradeCap / CoinMetadata owner
步骤 4 → 判断 TreasuryCap 是否仍存在、由谁持有，是否存在 Shared 风险
步骤 5 → 判断 UpgradeCap policy 与持有者身份；如为 EOA 单持且 policy=0，标记高风险
步骤 6 → sui_getNormalizedMoveModulesByPackage 提取模块面；如存在关键 public entry 或 shared_object 敏感路径，AI 深入审查
步骤 7 → GoPlus 结果 + TreasuryCap / UpgradeCap / CoinMetadata 综合判定
步骤 8 → AI 直接撰写结构化报告
```

---

## 附录 A：交易所上币 场景应用映射（仅场景化使用）
以下映射仅用于交易所上线风控场景，不改变主体 SOP 的通用风险结论表达。

| 等级 | 主体风险语言 | 交易所上币场景动作建议 |
| --- | --- | --- |
| D | 高风险 | 拒绝进入上线流程 |
| C | 中高风险 | 人工复核后再决定 |
| B | 中风险 | 补充材料并复核 |
| A | 低风险 | 可进入标准上线流程 |
| S | 极低风险 | 优先处理 |

补充规则：

+ 命中 GoPlus 致命标签（如 `is_honeypot=1`、`is_airdrop_scam=1`、`is_true_token=0`）时，交易所 场景直接走拒绝流程
+ Sui 出现 `TreasuryCap` Shared 或高危 `UpgradeCap` 配置时，至少进入人工复核

## 附录 B：快速审核路径索引

附录 B 的详细步骤已合并至主文「快速审查路径」章节，此处仅保留索引：

+ **EVM 链快速审查** — 6 步：GoPlus → RPC → 浏览器补充 → L1 扫描 → 致命标签判定 → 报告
+ **Solana 链快速审查** — 7 步：GoPlus → Authority → 集中度 → Token-2022 → 自定义程序 → 综合判定 → 报告
+ **Sui 链快速审查** — 8 步：GoPlus → 元数据 → TreasuryCap/UpgradeCap → Shared 风险 → 升级策略 → 模块面 → 综合判定 → 报告

所有快速路径对应的自动化脚本位于 `Scan_Script/` 目录。

## 附录 C：Sui Move 安全审计速查表

### C.1 核心对象与能力
| 名词 | 含义 | 审计重点 |
| --- | --- | --- |
| Coin<T> | Sui 代币对象模型 | T 类型是否与声明一致 |
| CoinMetadata | 名称/符号/图标元数据对象 | owner 是否 Immutable |
| TreasuryCap | 铸币能力对象 | 持有者类型、是否共享、是否销毁 |
| UpgradeCap | 升级能力对象 | policy 与持有者治理 |
| OTW | one-time witness 模式 | 是否保证唯一初始化 |

### C.2 对象 owner 类型
| owner 类型 | 风险语义 |
| --- | --- |
| AddressOwner | 由地址持有，需看是否多签 |
| ObjectOwner | 由对象持有，需追父对象权限 |
| Shared | 全网可访问，敏感对象通常高风险 |
| Immutable | 不可变，通常正向信号 |

### C.3 UpgradeCap policy 速记
| policy | 含义 | 风险趋势 |
| --- | --- | --- |
| 0 | Compatible | 高 |
| 128 | Additive | 中 |
| 192 | DEP_ONLY (dependency-only) | 低 |

说明：`immutable` 不是常规 policy 枚举值；审计中应以 `make_immutable()` 后的不可升级状态或 `UpgradeCap` 销毁状态判定。

### C.4 Ability 系统
| Ability | 含义 | 审计关注点 |
| --- | --- | --- |
| key | 对象可作为链上 key object 存储 | 关键 capability 不应被随意暴露 |
| store | 可被其他对象持有/存储 | 敏感对象带 `store` 时需防误转移 |
| copy | 可复制 | capability 通常不应具备 `copy` |
| drop | 可丢弃 | 关键 capability 不应具备 `drop` |

### C.5 TreasuryCap 生命周期
| 状态 | 描述 | 风险判定 |
| --- | --- | --- |
| creation | `coin::create_currency` / `create_regulated_currency` 产生 TreasuryCap | 需校验初始化路径与 OTW 约束 |
| held | TreasuryCap 由 AddressOwner/ObjectOwner 持有 | AddressOwner 单持偏高风险；ObjectOwner 需审计父对象 |
| shared-risk | TreasuryCap 被 Shared 或可被公共路径访问 | 高风险（共享铸币能力） |
| converted-or-destroyed | 通过 `treasury_into_supply` 或销毁流程使 TreasuryCap 不再可用（铸币生命周期终止） | 低风险到极低风险 |

### C.6 常见 Sui 误区

+ 把 `public(package)` 当成外部不可调用边界
+ 对 `shared_object` 缺少版本断言和权限断言
+ capability 结构体错误赋予 `drop ability`
+ 仅审计最新 package，忽略旧版本入口
+ 忽略整数除法截断与位运算溢出边界
