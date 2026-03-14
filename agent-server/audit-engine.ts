/**
 * GoatGuard 审计引擎 — 核心安全分析逻辑
 *
 * 策略: 利用 AI 模型 + 结构化 Prompt + 后处理生成标准化审计报告
 * 真正的安全知识体现在 Prompt 和结果解析中
 */

export interface Finding {
  id: string;
  severity: "Critical" | "High" | "Medium" | "Low" | "Info";
  title: string;
  location: string;
  description: string;
  impact: string;
  recommendation: string;
  swcId?: string;
}

export interface AuditResult {
  contractName: string;
  contractCode: string;
  inputs: string[];
  riskLevel: string;
  critical: number;
  high: number;
  medium: number;
  low: number;
  info: number;
  findings: Finding[];
  recommendations: string;
  timestamp: string;
  agentId: string;
  paymentTx: string;
  reportUrl?: string;
}

export type AuditTaskStatus = "pending" | "scanning" | "completed" | "failed";

export interface AuditTask {
  taskId: string;
  inputs: string[];
  email?: string;
  status: AuditTaskStatus;
  progress?: string;
  result?: AuditResult;
  reportUrl?: string;
  reportMarkdown?: string;
  createdAt: string;
  completedAt?: string;
  paymentTx: string;
}

export const AUDIT_SYSTEM_PROMPT = `你是 GoatGuard，一个部署在 GOAT Network 上的专业智能合约安全审计 Agent。

你精通 Solidity 安全审计，熟悉 SWC (Smart Contract Weakness Classification) 分类标准。

## 审计框架

按以下分类逐项检查合约代码:

### Critical / High
- SWC-107: Reentrancy (重入攻击) — 外部调用前未更新状态
- SWC-101: Integer Overflow/Underflow — 未使用 SafeMath 或 Solidity 0.8+
- SWC-106: Unprotected SELFDESTRUCT
- SWC-112: Delegatecall to Untrusted Callee
- Access Control 缺陷 — 关键函数缺少权限检查
- Unchecked Return Values — 未检查低级调用返回值

### Medium
- SWC-115: tx.origin Authentication — 应使用 msg.sender
- SWC-114: Front-running / Transaction Order Dependence
- SWC-108: State Variable Default Visibility
- Centralization Risk — 过度中心化的管理员权限
- Missing Input Validation

### Low / Info
- SWC-103: Floating Pragma
- Missing Events — 关键状态变更缺少事件
- Gas Optimization — 可优化的存储模式
- Code Quality — 命名规范、注释完整性
- Missing Zero-Address Checks

### GOAT Network 特殊考虑
- L2 Gas 模型差异
- 跨链桥交互安全
- BTC 原生资产处理

## 输出格式要求

必须以如下 JSON 格式输出，不要包含其他内容:

{
  "riskLevel": "Critical|High|Medium|Low|Safe",
  "findings": [
    {
      "id": "F-001",
      "severity": "Critical|High|Medium|Low|Info",
      "title": "漏洞标题",
      "location": "函数名或行号范围",
      "description": "漏洞描述",
      "impact": "潜在影响",
      "recommendation": "修复建议",
      "swcId": "SWC-XXX (如适用)"
    }
  ],
  "recommendations": "整体修复建议优先级排序"
}`;

export function parseAuditResponse(raw: string): Partial<AuditResult> {
  const jsonMatch = raw.match(/\{[\s\S]*\}/);
  if (!jsonMatch) {
    throw new Error("Failed to parse audit response as JSON");
  }

  const parsed = JSON.parse(jsonMatch[0]);
  const findings: Finding[] = parsed.findings || [];

  return {
    riskLevel: parsed.riskLevel || "Unknown",
    findings,
    critical: findings.filter((f) => f.severity === "Critical").length,
    high: findings.filter((f) => f.severity === "High").length,
    medium: findings.filter((f) => f.severity === "Medium").length,
    low: findings.filter((f) => f.severity === "Low").length,
    info: findings.filter((f) => f.severity === "Info").length,
    recommendations: parsed.recommendations || "",
  };
}

export function generateAuditMarkdown(result: AuditResult): string {
  const severityEmoji: Record<string, string> = {
    Critical: "\u{1F534}",
    High: "\u{1F7E0}",
    Medium: "\u{1F7E1}",
    Low: "\u{1F535}",
    Info: "\u26AA",
  };

  const findingsSection = result.findings
    .map(
      (f) => `
### ${severityEmoji[f.severity] || ""} ${f.severity} — ${f.title}${f.swcId ? ` (${f.swcId})` : ""}

- **位置**: \`${f.location}\`
- **描述**: ${f.description}
- **影响**: ${f.impact}
- **修复建议**: ${f.recommendation}
`
    )
    .join("\n---\n");

  return `# GoatGuard 安全审计报告

## 基本信息

| 项目 | 详情 |
|------|------|
| 合约 | ${result.contractName} |
| 网络 | GOAT Network Testnet3 |
| 审计时间 | ${result.timestamp} |
| Agent ID | ${result.agentId} |
| 支付交易 | ${result.paymentTx} |

## 风险评级: ${result.riskLevel}

## 发现汇总

| 严重性 | 数量 |
|--------|------|
| ${severityEmoji.Critical} Critical | ${result.critical} |
| ${severityEmoji.High} High | ${result.high} |
| ${severityEmoji.Medium} Medium | ${result.medium} |
| ${severityEmoji.Low} Low | ${result.low} |
| ${severityEmoji.Info} Info | ${result.info} |

## 详细发现

${findingsSection}

## 修复建议优先级

${result.recommendations}

---

*由 GoatGuard AI Security Agent 自动生成*
`;
}
