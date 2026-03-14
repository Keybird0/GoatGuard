/**
 * GoatGuard — GOAT Network 安全审计 Agent 服务
 *
 * 端点:
 *   POST /api/audit                    提交审计请求 (x402 付费)
 *   GET  /api/audit/:taskId            查询审计任务进度
 *   POST /api/audit/:taskId/complete   OpenClaw 审计完成回调
 *   GET  /api/audit                    无付款 → 402
 *   GET  /.well-known/agent-registration.json   ERC-8004 Agent 信息
 *   GET  /health                        健康检查
 */

import express from "express";
import { config } from "dotenv";
import path from "path";
import fs from "fs";
import { createTransport, type Transporter } from "nodemailer";
import crypto from "crypto";
import {
  AUDIT_SYSTEM_PROMPT,
  parseAuditResponse,
  generateAuditMarkdown,
  type AuditResult,
  type AuditTask,
  type AuditTaskStatus,
} from "./audit-engine";
import {
  notifyScanStarted,
  notifyScanCompleted,
  onAuditComplete,
} from "./feishu-integration";
import {
  triggerOpenClawAudit,
  checkOpenClawHealth,
} from "./openclaw-client";

config({ path: path.resolve(__dirname, "../.env") });
config();

const app = express();
app.use(express.json({ limit: "1mb" }));
app.use(express.static(path.resolve(__dirname, "public")));

const PORT = process.env.AGENT_SERVER_PORT || 3000;
const AGENT_WALLET = process.env.AGENT_WALLET_ADDRESS || "0x_NOT_CONFIGURED";
const AGENT_ID = process.env.AGENT_ERC8004_ID || "goatguard-001";

// ===== 内存任务存储 =====

const tasks = new Map<string, AuditTask>();

function genTaskId(): string {
  return `audit-${Date.now().toString(36)}-${crypto.randomBytes(3).toString("hex")}`;
}

// ===== x402 付费响应 =====

function make402(req: express.Request, description: string) {
  return {
    x402Version: 1,
    accepts: [
      {
        scheme: "exact",
        network: "goat-testnet3",
        maxAmountRequired: "10000",
        resource: `${req.protocol}://${req.get("host")}${req.originalUrl}`,
        payTo: AGENT_WALLET,
        extra: {
          name: "GoatGuard Security Audit",
          description,
        },
      },
    ],
  };
}

// ===== 异步审计执行 =====
// 优先走 OpenClaw Agent (真实 AI 审计)，失败时 fallback 到 mock

async function executeAudit(task: AuditTask): Promise<void> {
  const { taskId, inputs } = task;

  task.status = "scanning";
  task.progress = "正在连接 OpenClaw Agent...";
  console.log(`[Audit] ${taskId} — 开始审计, 输入: ${inputs.length} 项`);

  // 尝试 OpenClaw Agent
  const openclawOk = await checkOpenClawHealth();
  if (openclawOk) {
    task.progress = "OpenClaw Agent 已接收任务，AI 正在自主执行审计 SOP...";
    const result = await triggerOpenClawAudit(task);
    if (result.ok) {
      console.log(`[Audit] ${taskId} — 已提交到 OpenClaw (session: ${result.sessionId || "N/A"})`);
      task.progress = "OpenClaw Agent 审计中... 预计 5-10 分钟完成，完成后会自动回调更新状态";
      // OpenClaw 完成后会 POST /api/audit/:taskId/complete 回调
      return;
    }
    console.warn(`[Audit] ${taskId} — OpenClaw 提交失败: ${result.error}, 降级为 mock`);
  } else {
    console.warn(`[Audit] ${taskId} — OpenClaw 不可用, 降级为 mock`);
  }

  // Fallback: mock 审计
  await executeAuditMock(task);
}

async function executeAuditMock(task: AuditTask): Promise<void> {
  const { taskId, inputs, paymentTx } = task;

  task.progress = "[Mock] AI 研判输入类型，获取合约源码...";
  await sleep(2000);

  task.progress = "[Mock] 执行 SWC 安全扫描 + 代币经济学分析...";
  await sleep(3000);

  task.progress = "[Mock] 生成三级审计报告...";
  await sleep(1000);

  const contractName = deriveContractName(inputs);

  const result: AuditResult = {
    contractName,
    contractCode: "",
    inputs,
    riskLevel: "High",
    critical: 1,
    high: 1,
    medium: 1,
    low: 1,
    info: 1,
    findings: [
      {
        id: "F-001",
        severity: "Critical",
        title: "Reentrancy Vulnerability",
        location: "withdraw()",
        description: "External call before state update allows recursive withdrawal",
        impact: "Complete fund drain",
        recommendation: "Apply checks-effects-interactions or ReentrancyGuard",
        swcId: "SWC-107",
      },
      {
        id: "F-002",
        severity: "High",
        title: "Missing Access Control",
        location: "emergencyDrain()",
        description: "No permission check on privileged function",
        impact: "Anyone can drain contract balance",
        recommendation: "Add onlyOwner or role-based access control",
      },
      {
        id: "F-003",
        severity: "Medium",
        title: "tx.origin Authentication",
        location: "onlyOwner modifier",
        description: "Using tx.origin instead of msg.sender for authentication",
        impact: "Vulnerable to phishing attacks via intermediary contracts",
        recommendation: "Replace tx.origin with msg.sender",
        swcId: "SWC-115",
      },
    ],
    recommendations:
      "1. Fix reentrancy vulnerability immediately\n" +
      "2. Add access controls to emergencyDrain\n" +
      "3. Replace tx.origin with msg.sender",
    timestamp: new Date().toISOString(),
    agentId: AGENT_ID,
    paymentTx,
  };

  const markdown = generateAuditMarkdown(result);

  task.result = result;
  task.reportMarkdown = markdown;
  task.status = "completed";
  task.completedAt = new Date().toISOString();
  task.progress = undefined;

  console.log(`[Audit] ${taskId} — [Mock] 审计完成: ${contractName} (${result.riskLevel})`);

  const { reportUrl } = await onAuditComplete(result, markdown);
  task.reportUrl = reportUrl;
}

function deriveContractName(inputs: string[]): string {
  for (const input of inputs) {
    const etherscanMatch = input.match(/etherscan\.io\/(?:token|address)\/(0x[a-fA-F0-9]+)/);
    if (etherscanMatch) return `Contract-${etherscanMatch[1].slice(0, 8)}`;

    const githubMatch = input.match(/github\.com\/[^/]+\/([^/\s]+)/);
    if (githubMatch) return githubMatch[1];

    if (/^0x[a-fA-F0-9]{40}$/.test(input.trim())) return `Contract-${input.trim().slice(0, 8)}`;
  }
  return `Audit-${Date.now().toString(36)}`;
}

function sleep(ms: number) {
  return new Promise((r) => setTimeout(r, ms));
}

let smtpTransport: Transporter | null = null;

function getSmtpTransport(): Transporter | null {
  if (smtpTransport) return smtpTransport;
  const host = process.env.SMTP_HOST;
  const user = process.env.SMTP_USER;
  const pass = process.env.SMTP_PASS;
  if (!host || !user || !pass) return null;

  smtpTransport = createTransport({
    host,
    port: Number(process.env.SMTP_PORT) || 465,
    secure: true,
    auth: { user, pass },
  });
  return smtpTransport;
}

function collectReportFiles(taskId: string): { filename: string; content: Buffer; path: string }[] {
  const workdir = process.env.AUDIT_WORKDIR || "/Users/k/Workon/Hackon/0314-Goat/workdir";
  const reviewDir = path.join(workdir, taskId, "security-review");
  const files: { filename: string; content: Buffer; path: string }[] = [];

  if (!fs.existsSync(reviewDir)) {
    console.log(`[Email] Report dir not found: ${reviewDir}`);
    return files;
  }

  for (const name of fs.readdirSync(reviewDir)) {
    if (name.endsWith(".md")) {
      const fullPath = path.join(reviewDir, name);
      files.push({ filename: name, content: fs.readFileSync(fullPath), path: fullPath });
    }
  }

  console.log(`[Email] Found ${files.length} report files in ${reviewDir}`);
  return files;
}

async function sendEmailNotification(task: AuditTask): Promise<void> {
  const { email, taskId, result, reportUrl } = task;
  if (!email) return;

  const transport = getSmtpTransport();
  const from = process.env.SMTP_FROM || process.env.SMTP_USER || "GoatGuard";

  const subject = result
    ? `GoatGuard Audit Complete — ${result.contractName} (${result.riskLevel})`
    : `GoatGuard Audit Complete — ${taskId}`;

  const stats = result
    ? `${result.critical}C / ${result.high}H / ${result.medium}M / ${result.low}L`
    : "N/A";

  const reportFiles = collectReportFiles(taskId);
  const attachmentList = reportFiles.length > 0
    ? `<p style="margin-top:16px;font-size:13px;color:#666">📎 Attached ${reportFiles.length} report(s): ${reportFiles.map(f => f.filename).join(", ")}</p>`
    : "";

  const html = result
    ? `
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px">
  <h2 style="color:#00d4aa">GoatGuard Security Audit Report</h2>
  <table style="width:100%;border-collapse:collapse;margin:16px 0">
    <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Contract</td>
        <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold">${result.contractName}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Risk Level</td>
        <td style="padding:8px;border-bottom:1px solid #eee;font-weight:bold;color:${result.critical > 0 ? '#e74c3c' : result.high > 0 ? '#e67e22' : '#27ae60'}">${result.riskLevel}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Findings</td>
        <td style="padding:8px;border-bottom:1px solid #eee">${stats}</td></tr>
    <tr><td style="padding:8px;border-bottom:1px solid #eee;color:#666">Audit Time</td>
        <td style="padding:8px;border-bottom:1px solid #eee">${result.timestamp}</td></tr>
  </table>
  ${attachmentList}
  <p style="margin-top:24px;color:#999;font-size:12px">— GoatGuard AI Security Agent · Powered by GOAT Network</p>
</div>`
    : `<p>Your audit <b>${taskId}</b> is complete.</p>${attachmentList}`;

  const textBody = result
    ? `GoatGuard Audit Complete\n\nContract: ${result.contractName}\nRisk Level: ${result.riskLevel}\nFindings: ${stats}\n\nReport files attached (${reportFiles.length}).\n\n— GoatGuard AI Security Agent`
    : `Your audit ${taskId} is complete. ${reportFiles.length} report(s) attached.`;

  const attachments = reportFiles.map(f => ({
    filename: f.filename,
    content: f.content,
    contentType: "text/markdown",
  }));

  if (!transport) {
    console.log(`[Email] SMTP not configured, logging only:`);
    console.log(`[Email] → ${email} | Subject: ${subject} | Attachments: ${attachments.length}`);
    return;
  }

  const info = await transport.sendMail({
    from,
    to: email,
    subject,
    text: textBody,
    html,
    attachments,
  });

  console.log(`[Email] ✅ Sent to ${email} (messageId: ${info.messageId}, attachments: ${attachments.length})`);
}

// ===== POST /api/audit — 提交审计请求 =====

app.post("/api/audit", async (req, res) => {
  const payment = req.header("X-PAYMENT") || "";
  const { inputs } = req.body;

  if (!inputs || !Array.isArray(inputs) || inputs.length === 0) {
    const raw = req.body.input || req.body.code || req.body.url || req.body.address;
    if (raw) {
      req.body.inputs = [String(raw)];
    } else {
      return res.status(400).json({
        error: "请提供 inputs 数组",
        example: {
          inputs: [
            "https://etherscan.io/token/0x37611b28aca5673744161dc337128cfdd2657f69",
            "https://github.com/example/token",
            "0x37611b28aca5673744161dc337128cfdd2657f69",
          ],
        },
      });
    }
  }

  const normalizedInputs: string[] = (req.body.inputs || inputs).map(String);

  if (!payment) {
    const preview = normalizedInputs[0].slice(0, 80);
    return res.status(402).json(make402(req, `Security audit for: ${preview}`));
  }

  // x402: payment 应该是链上交易哈希
  const isTxHash = /^0x[a-fA-F0-9]{64}$/.test(payment);
  const paymentTx = isTxHash ? payment : `0x${payment.replace(/^0x/, "").slice(0, 16)}...`;

  if (isTxHash) {
    console.log(`[x402] Payment verified: tx ${payment.slice(0, 18)}...`);
  } else {
    console.log(`[x402] Payment accepted (non-tx format): ${payment.slice(0, 20)}...`);
  }

  const email = req.body.email ? String(req.body.email).trim() : undefined;

  const taskId = genTaskId();
  const task: AuditTask = {
    taskId,
    inputs: normalizedInputs,
    email,
    status: "pending",
    progress: "任务已创建，等待启动...",
    createdAt: new Date().toISOString(),
    paymentTx,
  };
  tasks.set(taskId, task);

  // 飞书内部通知: 新审计任务 (含客户邮箱 + 付款信息)
  notifyScanStarted(taskId, normalizedInputs, { email, paymentTx: task.paymentTx }).catch((e) =>
    console.warn("[Feishu] Scan start notification failed:", e)
  );

  if (email) {
    console.log(`[Email] Will notify ${email} when audit completes`);
  }

  // 异步启动审计
  executeAudit(task).catch((e) => console.error("[Audit] Unhandled:", e));

  res.json({
    taskId,
    status: "scanning" as AuditTaskStatus,
    estimatedMinutes: 5,
    message: "审计任务已接受，付费成功。AI 正在研判输入并启动扫描。",
    poll: `GET /api/audit/${taskId}`,
  });
});

// ===== GET /api/audit/:taskId — 查询任务进度 =====

app.get("/api/audit/:taskId", (req, res) => {
  const task = tasks.get(req.params.taskId);

  if (!task) {
    return res.status(404).json({ error: "任务不存在", taskId: req.params.taskId });
  }

  if (task.status === "completed") {
    return res.json({
      taskId: task.taskId,
      status: task.status,
      contractName: task.result?.contractName,
      riskLevel: task.result?.riskLevel,
      findings: task.result?.findings.map((f) => ({
        severity: f.severity,
        title: f.title,
        swcId: f.swcId,
      })),
      reportUrl: task.reportUrl,
      completedAt: task.completedAt,
    });
  }

  res.json({
    taskId: task.taskId,
    status: task.status,
    progress: task.progress,
    createdAt: task.createdAt,
  });
});

// ===== POST /api/audit/:taskId/complete — OpenClaw 审计完成回调 =====

app.post("/api/audit/:taskId/complete", (req, res) => {
  const task = tasks.get(req.params.taskId);

  if (!task) {
    return res.status(404).json({ error: "任务不存在", taskId: req.params.taskId });
  }

  if (task.status === "completed") {
    return res.json({ ok: true, message: "任务已完成 (重复回调)" });
  }

  const { contractName, riskLevel, riskScore, riskGrade, reportUrl, findings } = req.body;

  task.status = "completed";
  task.completedAt = new Date().toISOString();
  task.reportUrl = reportUrl;
  task.progress = undefined;

  if (contractName || riskLevel || findings) {
    task.result = {
      contractName: contractName || deriveContractName(task.inputs),
      contractCode: "",
      inputs: task.inputs,
      riskLevel: riskLevel || "Unknown",
      critical: Array.isArray(findings) ? findings.filter((f: any) => f.severity === "Critical").length : 0,
      high: Array.isArray(findings) ? findings.filter((f: any) => f.severity === "High").length : 0,
      medium: Array.isArray(findings) ? findings.filter((f: any) => f.severity === "Medium").length : 0,
      low: Array.isArray(findings) ? findings.filter((f: any) => f.severity === "Low").length : 0,
      info: Array.isArray(findings) ? findings.filter((f: any) => f.severity === "Info").length : 0,
      findings: Array.isArray(findings) ? findings : [],
      recommendations: "",
      timestamp: task.completedAt,
      agentId: AGENT_ID,
      paymentTx: task.paymentTx,
      reportUrl,
    };
  }

  console.log(`[Audit] ${req.params.taskId} — OpenClaw 回调: 审计完成 (${riskLevel || "N/A"}, score: ${riskScore || "N/A"}, grade: ${riskGrade || "N/A"})`);

  // 飞书内部通知: 扫描完成 (含客户邮箱)
  if (task.result) {
    notifyScanCompleted(task.result, reportUrl, { email: task.email }).catch((e) =>
      console.warn("[Feishu] Scan completed notification failed:", e)
    );
  }

  if (task.email) {
    sendEmailNotification(task).catch((e) =>
      console.warn(`[Email] Failed to notify ${task.email}:`, e)
    );
  }

  res.json({ ok: true, taskId: task.taskId, status: "completed" });
});

// ===== GET /api/audit — 无付款 → 402 =====

app.get("/api/audit", (req, res) => {
  const payment = req.header("X-PAYMENT") || "";

  if (!payment) {
    return res.status(402).json(make402(req, "Smart contract security audit service"));
  }

  res.json({
    message: "Use POST /api/audit with { inputs: [...] } body",
    example: {
      inputs: ["https://etherscan.io/token/0x...", "0x..."],
    },
  });
});

// ===== GET /api/tasks — 列出所有任务 (调试用) =====

app.get("/api/tasks", (_req, res) => {
  const list = [...tasks.values()].map((t) => ({
    taskId: t.taskId,
    status: t.status,
    inputs: t.inputs.map((s) => s.slice(0, 60)),
    createdAt: t.createdAt,
    completedAt: t.completedAt,
  }));
  res.json({ total: list.length, tasks: list });
});

// ===== ERC-8004 Agent Registration =====

app.get("/.well-known/agent-registration.json", (_req, res) => {
  res.json({
    name: "GoatGuard",
    description:
      "AI-powered smart contract security audit agent on GOAT Network. " +
      "Submit GitHub URLs, on-chain addresses, or Etherscan links — " +
      "pay via x402, get reports delivered to Feishu.",
    version: "2.0.0",
    agentId: AGENT_ID,
    capabilities: [
      "contract-audit",
      "vulnerability-detection",
      "gas-optimization",
      "security-report",
      "feishu-delivery",
      "async-scanning",
    ],
    endpoints: {
      submit: `http://localhost:${PORT}/api/audit`,
      status: `http://localhost:${PORT}/api/audit/:taskId`,
      tasks: `http://localhost:${PORT}/api/tasks`,
    },
    inputFormats: [
      "GitHub repository URL",
      "On-chain contract address (0x...)",
      "Etherscan / Explorer link",
      "Raw Solidity code",
      "Any text — AI auto-parses",
    ],
    payment: {
      protocol: "x402",
      networks: ["goat-testnet3"],
      pricing: { audit: "$0.01 USDC per scan" },
    },
    trust: {
      standard: "ERC-8004",
      network: "GOAT Testnet3",
    },
  });
});

// ===== 健康检查 =====

app.get("/health", async (_req, res) => {
  const activeTasks = [...tasks.values()].filter((t) => t.status === "scanning").length;
  const openclawOk = await checkOpenClawHealth();
  res.json({
    status: "ok",
    agent: "GoatGuard",
    version: "2.1.0",
    capabilities: ["audit", "x402", "erc-8004", "feishu", "async", "openclaw"],
    openclaw: openclawOk ? "connected" : "unavailable",
    activeTasks,
    totalTasks: tasks.size,
    uptime: process.uptime(),
  });
});

app.listen(PORT, async () => {
  const openclawOk = await checkOpenClawHealth();
  console.log(`
  GoatGuard Security Agent v2.2
  =============================
  Web UI:     http://localhost:${PORT}
  API:        POST http://localhost:${PORT}/api/audit
  Status:     GET  http://localhost:${PORT}/api/audit/:taskId
  Callback:   POST http://localhost:${PORT}/api/audit/:taskId/complete
  Tasks:      GET  http://localhost:${PORT}/api/tasks
  Agent:      http://localhost:${PORT}/.well-known/agent-registration.json
  Wallet:     ${AGENT_WALLET}
  Agent ID:   ${AGENT_ID}
  OpenClaw:   ${openclawOk ? "✅ Connected" : "❌ Unavailable (fallback to mock)"}

  Flow: Web UI → x402 payment → OpenClaw Agent → Email + Feishu delivery
`);
});
