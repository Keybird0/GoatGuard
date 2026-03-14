# Scan_Script

代币安全审计脚本集，配合「通用代币安全审计 SOP」和 `Token_Security_Audit_Skills` 使用。

当前数据采集层已经改成 `Python 实现 + shell 兼容包装`：
- `*.py` 是主实现，负责超时控制、结构化 JSON 输出、失败分类和多 RPC 回退。
- `*.sh` 仅作为兼容入口，继续保留旧文件名和常见旧参数顺序。

## 脚本清单

| 脚本 | 语言 | 用途 | SOP 阶段 |
|------|------|------|----------|
| `detect_chain.py` | Python | 自动检测链类型 (EVM / Solana / Sui) | Phase 1 |
| `goplus_query.py` | Python | GoPlus Token Security API 查询，输出结构化结果 | Phase 2 |
| `evm_rpc_query.py` | Python | EVM RPC 直读，支持 `cast` + 多 RPC 回退 | Phase 2 |
| `solana_rpc_query.py` | Python | Solana JSON-RPC 直读，支持多 RPC 回退 | Phase 2 |
| `sui_rpc_query.py` | Python | Sui JSON-RPC 直读，支持多 RPC 回退 | Phase 2 |
| `goplus_query.sh` | Bash | `goplus_query.py` 兼容包装 | Phase 2 |
| `evm_rpc_query.sh` | Bash | `evm_rpc_query.py` 兼容包装 | Phase 2 |
| `solana_rpc_query.sh` | Bash | `solana_rpc_query.py` 兼容包装 | Phase 2 |
| `sui_rpc_query.sh` | Bash | `sui_rpc_query.py` 兼容包装 | Phase 2 |
| `pattern_scanner.py` | Python | Solidity 安全模式扫描 | Phase 3 L1 |
| `sui_scanner.py` | Python | Sui Move 安全扫描 | Phase 3 L1 |
| `scoring_system.py` | Python | 业务安全评分 | Phase 6 |

## 依赖

基础依赖：
- `python3`
- `bash` 或 `zsh`

链级可选依赖：
- `cast`：EVM 直读和源码相关能力
- `spl-token`：Solana 补充展示输出
- `sui`：Sui CLI 相关扩展能力

说明：
- RPC / HTTP 查询主流程仅使用 Python 标准库，不依赖 `requests`、`web3.py`、`eth_abi`。
- EVM 这轮仍依赖 `cast` 做合约调用与部分代理信息读取。

## 多 RPC 回退

每条链都支持 `显式参数 + 环境变量 + 内置默认池` 的组合策略。

优先级：
- 显式参数
- 单值环境变量
- 多值环境变量
- 内置默认公共 RPC

支持的环境变量：
- Ethereum: `ETH_RPC_URL`, `ETH_RPC_URLS`
- BSC: `BSC_RPC_URL`, `BSC_RPC_URLS`
- Polygon: `POLYGON_RPC_URL`, `POLYGON_RPC_URLS`
- Arbitrum: `ARB_RPC_URL`, `ARB_RPC_URLS`
- Optimism: `OP_RPC_URL`, `OP_RPC_URLS`
- Base: `BASE_RPC_URL`, `BASE_RPC_URLS`
- Avalanche: `AVAX_RPC_URL`, `AVAX_RPC_URLS`
- Solana: `SOLANA_RPC_URL`, `SOLANA_RPC_URLS`
- Sui: `SUI_RPC_URL`, `SUI_RPC_URLS`

兼容旧用法：
- `RPC_URL` 仍可作为通用单值 RPC 环境变量使用。

## 输出文件

链上查询除了主结果文件，还会额外输出 provider 报告，便于审计材料归档和回溯：
- `goplus-token-security.json`
- `goplus-request-report.json`
- `rpc-basic-info.json` 或链级主数据文件
- `rpc-provider-report.json`

`rpc-provider-report.json` 记录：
- 配置过的 RPC 池
- 健康探测结果
- 每个操作的尝试顺序
- 失败原因
- 最终命中的节点

## 快速使用

```bash
# 1. 检测链类型
python3 detect_chain.py 0xdAC17F958D2ee523a2206206994597C13D831ec7

# 2. GoPlus 查询
# 兼容旧用法: 第二个参数既支持 ethereum，也支持 1
./goplus_query.sh 0xdAC17F958D2ee523a2206206994597C13D831ec7 1 ./workdir/evm/

# 3. EVM RPC 查询
# 兼容旧 shell 用法: address + out_dir，RPC 从 RPC_URL / ETH_RPC_URL / ETH_RPC_URLS 获取
RPC_URL=https://eth.llamarpc.com ./evm_rpc_query.sh 0xdAC17F958D2ee523a2206206994597C13D831ec7 ./workdir/evm/ --chain ethereum

# 4. EVM RPC 查询，显式传入单个 RPC
./evm_rpc_query.sh 0xdAC17F958D2ee523a2206206994597C13D831ec7 https://ethereum-rpc.publicnode.com ./workdir/evm/ --chain ethereum

# 5. Solana RPC 查询
SOLANA_RPC_URLS=https://bad.example,https://api.mainnet-beta.solana.com ./solana_rpc_query.sh So11111111111111111111111111111111111111112 ./workdir/solana/

# 6. Sui RPC 查询
./sui_rpc_query.sh 0x2::sui::SUI ./workdir/sui/

# 7. Solidity 模式扫描
python3 pattern_scanner.py --source ./workdir/evm/code/ --output ./workdir/evm/pattern-scan.json

# 8. Sui Move 扫描
python3 sui_scanner.py --package-dir ./workdir/sui/ --package 0x123... --output ./workdir/sui/sui-scan.json

# 9. 业务安全评分
python3 scoring_system.py --goplus ./workdir/evm/goplus-token-security.json --mint "不可增发" --owner "已放弃" --top10 0.45 --dex --open-source
```

## 与 SOP 的对应关系

- Phase 0.5 环境准备: 安装本目录依赖
- Phase 2 数据采集: `goplus_query.py` / `*_rpc_query.py`
- Phase 3 L1 快速扫描: `pattern_scanner.py` / `sui_scanner.py`
- Phase 6 评分: `scoring_system.py`
