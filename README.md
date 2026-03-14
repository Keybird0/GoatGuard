# GoatGuard — GOAT Network AI Security Audit Agent

> **Security-as-a-Service**: An AI security audit agent with on-chain identity. Clients submit a GitHub repo or on-chain address via Web UI, pay 0.000001 BTC through MetaMask (GOAT Testnet3 x402), and receive a professional audit report in ~5 minutes — delivered to Feishu docs and email.

## Architecture

```
Client (Browser)
        │
        │  Web UI: submit GitHub URL / contract address + email
        │  MetaMask: connect wallet + pay 0.000001 BTC
        ▼
┌─────────────────────────────────────────────┐
│         GoatGuard Agent Server (Express)     │
│                                             │
│  ┌────────────┐  ┌────────────────────────┐ │
│  │ Interface   │  │ OpenClaw Agent         │ │
│  │ · Web UI    │  │ · contract-security-   │ │
│  │ · REST API  │  │   audit-skill          │ │
│  │ · x402 Auth │  │ · autonomous analysis  │ │
│  └────────────┘  └────────────────────────┘ │
│                                             │
│  ┌────────────────────────────────────────┐  │
│  │ Audit Orchestration Engine              │  │
│  │ · Input classification                  │  │
│  │   (GitHub / address / browser link)     │  │
│  │ · Auto scan strategy selection          │  │
│  │ · cast source / git clone / GoPlus API  │  │
│  │ · AI code audit + structured reporting  │  │
│  └────────────────────────────────────────┘  │
└─────┬──────────┬──────────┬──────────┬──────┘
      │          │          │          │
      ▼          ▼          ▼          ▼
┌──────────┐ ┌────────┐ ┌────────┐ ┌──────────┐
│  x402    │ │ERC-8004│ │ Feishu │ │  Email   │
│ Payment  │ │Identity│ │(Team)  │ │(Client)  │
│          │ │        │ │        │ │          │
│ BTC tx   │ │Auditor │ │Monitor │ │Completed │
│ on-chain │ │identity│ │· start │ │→ report  │
│ verified │ │ & rep  │ │· done  │ │  attached│
└────┬─────┘ └───┬────┘ └────────┘ └──────────┘
     │           │
     ▼           ▼
┌────────────────────────────────────┐
│      GOAT Network Testnet3         │
│  · AgentRegistry contract          │
│  · Payment records on-chain        │
│  · 0.000001 BTC per audit          │
└────────────────────────────────────┘
```

## Features

**Smart Input Parsing** — Accepts GitHub repos, on-chain addresses (`0x...`), or Etherscan links. The agent autonomously determines how to retrieve contract source code.

**x402 Pay-per-Audit** — No payment, no audit. Clients connect MetaMask, transfer 0.000001 BTC on GOAT Testnet3, and the tx hash is verified on-chain before the audit begins.

**AI Audit Engine (~5 min)** — Follows a professional Token Security Audit SOP:
- Structured static analysis (SWC Registry + Solodit Checklist)
- Token economics audit (supply, tax, blacklist, transfer restrictions)
- Governance & permission analysis (owner privileges, timelock, multisig)
- GOAT Network compatibility check (L2 gas model, cross-chain bridge)
- Outputs three-tier report: Risk Summary, Full Assessment, Audit Checklist

**Dual-Channel Delivery** — Client receives an email with attached report files. Team monitors via Feishu: webhook alerts, auto-generated docs, audit records in Bitable.

**On-Chain Identity (ERC-8004)** — Registered as "Security Audit Agent" with cumulative audit count and reputation score.

## Project Structure

```
GoatGuard/
├── contracts/                  Solidity smart contracts
│   ├── AgentRegistry.sol         ERC-8004 agent identity registry
│   └── demo/
│       └── VulnerableVault.sol   Demo target with planted vulnerabilities
├── script/
│   └── Deploy.s.sol              Foundry deployment script
├── agent-server/               GoatGuard audit API (TypeScript)
│   ├── server.ts                 Express server with x402 payment
│   ├── audit-engine.ts           AI audit orchestration + prompts
│   ├── feishu-integration.ts     Feishu docs, bitable, webhook
│   ├── openclaw-client.ts        OpenClaw agent client
│   └── public/
│       └── index.html            Web UI (submit + pay + progress)
├── scan-scripts/               Token security scanning toolkit (Python)
│   ├── goplus_query.py           GoPlus API integration
│   ├── evm_rpc_query.py          EVM on-chain data collection
│   ├── solana_rpc_query.py       Solana chain queries
│   ├── sui_rpc_query.py          Sui chain queries
│   ├── pattern_scanner.py        Code pattern matching
│   ├── scoring_system.py         Risk scoring logic
│   ├── detect_chain.py           Auto chain detection
│   └── tests/                    Unit tests
├── docs/
│   └── audit-sop.md              Token security audit SOP
├── sample-reports/             Example audit outputs
│   ├── goat-network/             GOAT Network contract assessment
│   ├── goat-coin/                GOAT Coin token assessment
│   └── delegation/               Delegation contract assessment
├── package.json                Node dependencies
├── tsconfig.json               TypeScript config
├── foundry.toml                Foundry build config (GOAT Testnet3)
├── remappings.txt              Solidity import mappings
├── .gitignore
└── .gitmodules                 Foundry lib submodules
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent Framework | OpenClaw |
| Payment | x402 protocol (BTC on GOAT Testnet3) |
| On-chain Identity | ERC-8004 (AgentRegistry.sol) |
| Smart Contracts | Solidity + Foundry |
| Server | TypeScript + Express |
| Scanning | Python (GoPlus API, RPC queries, pattern analysis) |
| Delivery | Feishu (docs + bitable + webhook) + Email (nodemailer) |
| Network | GOAT Network Testnet3 (Bitcoin L2) |

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- [Foundry](https://getfoundry.sh/)
- MetaMask with GOAT Testnet3 configured

### Install Dependencies

```bash
# Node dependencies
npm install

# Foundry submodules
forge install
```

### Environment Variables

Create a `.env` file with the required keys (refer to the server source for variable names):

- Wallet private key (GOAT Testnet3)
- OpenClaw API credentials
- Feishu app credentials (App ID, App Secret, webhook URL)
- Email SMTP config
- Feishu Bitable app token and table ID

### Deploy Contracts

```bash
forge script script/Deploy.s.sol --rpc-url <GOAT_TESTNET3_RPC> --broadcast
```

### Run Server

```bash
npx tsx agent-server/server.ts
```

Open `http://localhost:3000` to access the Web UI.

## Client Flow

1. Open Web UI, enter audit target (GitHub URL or contract address) + email
2. Connect MetaMask wallet
3. Pay 0.000001 BTC on GOAT Testnet3
4. Agent autonomously analyzes the contract (~5 min)
5. Receive audit report via email; team monitors via Feishu

## Sample Reports

The `sample-reports/` directory contains real audit outputs demonstrating GoatGuard's capabilities:

- **goat-network/** — GOAT Network core contract security assessment
- **goat-coin/** — GOAT Coin token audit (scored 92/100, S-tier)
- **delegation/** — Delegation contract security evaluation

## License

MIT
