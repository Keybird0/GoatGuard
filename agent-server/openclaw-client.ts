/**
 * OpenClaw Agent Client
 *
 * 通过 `openclaw agent` CLI 将审计任务交给 OpenClaw Agent 执行。
 * Agent 利用 contract-security-audit-skill 和内置飞书工具链完成:
 *   1. build_audit_bundle.py 数据收集 + Scan_Script 扫描
 *   2. AI 代码审计 + 误报分析
 *   3. 生成三份报告 (Risk-Summary / Assessment / Checklist)
 *   4. Assessment 报告写入飞书文档并返回链接
 *   5. 记录写入飞书多维表格
 *   6. 通知推送飞书群 Webhook
 *   7. 回调 Express server 更新任务状态
 */

import { spawn } from "child_process";
import { randomBytes } from "crypto";
import type { AuditTask } from "./audit-engine";

function env(key: string, fallback = ""): string {
  return process.env[key] || fallback;
}

const SKILL_PATH = "~/.openclaw/skills/contract-security-audit-skill";

export function buildAuditInstruction(task: AuditTask): string {
  const inputsList = task.inputs.map((s, i) => `  ${i + 1}. ${s}`).join("\n");
  const port = env("AGENT_SERVER_PORT", "3000");
  const feishuWebhook = env("FEISHU_WEBHOOK_URL");
  const bitableApp = env("FEISHU_BITABLE_APP_TOKEN");
  const bitableTable = env("FEISHU_AUDIT_TABLE_ID");
  const workdir = env("AUDIT_WORKDIR", "/Users/k/Workon/Hackon/0314-Goat/workdir");
  const callbackUrl = `http://localhost:${port}/api/audit/${task.taskId}/complete`;

  return `使用 contract-security-audit-skill 对以下目标进行合约安全审计:

${inputsList}

## 执行要求

请严格按照 ${SKILL_PATH}/SKILL.md 中的审计流程执行。
参考 ${SKILL_PATH}/references/workflow.md 了解完整工作流。
工作目录: ${workdir}/${task.taskId}/

### SOP 关键步骤

**Step 1: 规范化输入 + 数据收集**
- 分析输入类型 (地址/GitHub/Etherscan链接/自由文本)
- 如果是 Etherscan 链接，提取合约地址
- 从地址格式推断链类型 (EVM: 0x 开头 / Solana: Base58)
- 运行 build_audit_bundle.py 进行自动化数据收集:
  \`python3 ${SKILL_PATH}/scripts/build_audit_bundle.py --project-name "<ProjectName>" --token-address <address> --output-root ${workdir}/${task.taskId}\`
  - 该脚本会自动执行: GoPlus 检测、RPC 链上数据读取、源码获取、Pattern Scanner 扫描
  - Scan_Script 工具集位于 ${SKILL_PATH}/Scan_Script/

**Step 2: AI 代码安全审计**
- 读取 scanner 输出 (Slither/Aderyn/4naly3er/Pattern Scanner)
- 读取合约源码 (code/ 目录)
- 对每个 High/Medium 发现进行误报分析 (真阳性/误报/待确认)
- 交叉验证 scanner 发现与 GoPlus 数据和 RPC 结果

**Step 3: 生成三份报告** (AI 直接撰写，参考 ${SKILL_PATH}/references/report-templates.md)
报告输出到 ${workdir}/${task.taskId}/security-review/ 目录:
1. \`Risk-Summary.md\` — 执行摘要 (合约安全概览、持仓分析、流动性分析、Owner权限)
2. \`<ProjectName>-Token-Security-Assessment.md\` — 13 节完整评估报告 ← **此文件上传飞书**
3. \`<ProjectName>-Audit-Checklist-Evaluation.md\` — 分类 Checklist 评估

## 审计完成后的输出动作

### 动作 1: Assessment 报告写入飞书文档
使用 feishu_create_doc 工具将 \`<ProjectName>-Token-Security-Assessment.md\` 的完整内容 (Markdown) 写入飞书云文档。
记录返回的飞书文档链接 (后续动作都需要此链接)。

### 动作 2: 记录写入飞书多维表格
使用 feishu_bitable_app_table_record 工具添加审计记录:
- app_token: ${bitableApp}
- table_id: ${bitableTable}
- 字段:
  - 合约名称: (审计目标名称)
  - 风险评级: (Critical/High/Medium/Low/Safe)
  - Critical: (Critical 数量)
  - High: (High 数量)
  - Medium: (Medium 数量)
  - Low: (Low 数量)
  - 审计时间: (当前时间戳)
  - 状态: 已完成
  - 详细报告地址: (飞书文档链接)

### 动作 3: 推送飞书群通知
通过 HTTP POST 将扫描完成消息推送到飞书群 Webhook:
URL: ${feishuWebhook}
请求体:
\`\`\`json
{
  "msg_type": "interactive",
  "card": {
    "header": {
      "title": { "tag": "plain_text", "content": "📋 GoatGuard 扫描完成" },
      "template": "green"
    },
    "elements": [{
      "tag": "markdown",
      "content": "**合约**: (名称)\\n**风险等级**: (等级) | **评分**: (分数)\\n**发现**: xC / xH / xM / xL\\n📄 **完整报告**: [点击查看](飞书文档链接)"
    }]
  }
}
\`\`\`

### 动作 4: 回调通知 Express Server
通过 HTTP POST 通知审计服务任务完成:
URL: ${callbackUrl}
请求体:
\`\`\`json
{
  "status": "completed",
  "contractName": "(合约名称)",
  "riskLevel": "(风险等级)",
  "riskScore": (评分数字),
  "riskGrade": "(S/A/B/C/D)",
  "reportUrl": "(飞书文档链接，即 Assessment 报告的飞书链接)",
  "findings": [
    { "severity": "Critical/High/Medium/Low/Info", "title": "...", "swcId": "SWC-xxx" }
  ]
}
\`\`\`

请按顺序执行以上所有步骤。`;
}

export interface OpenClawResponse {
  ok: boolean;
  error?: string;
  sessionId?: string;
  pid?: number;
}

/**
 * 通过 `openclaw agent` CLI 触发审计任务
 * 在后台 spawn 进程，不阻塞主线程
 */
export async function triggerOpenClawAudit(task: AuditTask): Promise<OpenClawResponse> {
  const message = buildAuditInstruction(task);

  return new Promise((resolve) => {
    try {
      const sessionId = `${task.taskId}-${randomBytes(4).toString("hex")}`;
      console.log(`[OpenClaw] New session: ${sessionId}`);

      const child = spawn("openclaw", [
        "agent",
        "--agent", "goatguard",
        "--session-id", sessionId,
        "--message", message,
        "--json",
        "--timeout", "600",
      ], {
        stdio: ["ignore", "pipe", "pipe"],
        detached: false,
        env: { ...process.env, PATH: process.env.PATH },
      });

      let stdout = "";
      let stderr = "";

      child.stdout.on("data", (data) => {
        stdout += data.toString();
      });

      child.stderr.on("data", (data) => {
        stderr += data.toString();
        const line = data.toString().trim();
        if (line) console.log(`[OpenClaw:${task.taskId}] ${line}`);
      });

      child.on("error", (err) => {
        console.error(`[OpenClaw] spawn failed:`, err.message);
        resolve({ ok: false, error: `spawn failed: ${err.message}` });
      });

      child.on("close", (code) => {
        if (code === 0) {
          console.log(`[OpenClaw] Task ${task.taskId} agent turn completed`);
          tryParseAndCallback(task.taskId, stdout);
        } else {
          console.error(`[OpenClaw] Task ${task.taskId} exited with code ${code}`);
          if (stderr) console.error(`[OpenClaw] stderr: ${stderr.slice(-500)}`);
        }
      });

      // 不等待完成，立即返回
      // openclaw agent 可能运行 5-10 分钟
      setTimeout(() => {
        if (child.pid) {
          console.log(`[OpenClaw] Task ${task.taskId} running as PID ${child.pid}`);
          resolve({ ok: true, sessionId, pid: child.pid });
        } else {
          resolve({ ok: false, error: "Failed to spawn openclaw process" });
        }
      }, 500);

    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      console.error(`[OpenClaw] Failed to trigger audit:`, msg);
      resolve({ ok: false, error: msg });
    }
  });
}

/**
 * openclaw agent --json 输出结果后，如果 Agent 没有主动 POST 回调，
 * 这里做一次兜底解析，把结果 POST 到 callback
 */
async function tryParseAndCallback(taskId: string, stdout: string): Promise<void> {
  const port = env("AGENT_SERVER_PORT", "3000");
  const callbackUrl = `http://localhost:${port}/api/audit/${taskId}/complete`;

  try {
    const jsonMatch = stdout.match(/\{[\s\S]*\}/);
    if (!jsonMatch) return;

    const data = JSON.parse(jsonMatch[0]);

    // Agent 可能已经主动 POST 了回调，检查一下任务状态
    const statusResp = await fetch(`http://localhost:${port}/api/audit/${taskId}`);
    const status = await statusResp.json() as { status?: string };
    if (status.status === "completed") {
      console.log(`[OpenClaw] Task ${taskId} already completed via agent callback`);
      return;
    }

    // 兜底回调
    await fetch(callbackUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        status: "completed",
        contractName: data.contractName || `Audit-${taskId}`,
        riskLevel: data.riskLevel || "Unknown",
        riskScore: data.riskScore,
        riskGrade: data.riskGrade,
        reportUrl: data.reportUrl,
        findings: data.findings || [],
      }),
    });
    console.log(`[OpenClaw] Fallback callback sent for task ${taskId}`);
  } catch (err) {
    console.warn(`[OpenClaw] Fallback callback failed for ${taskId}:`, err);
  }
}

export async function checkOpenClawHealth(): Promise<boolean> {
  const url = env("OPENCLAW_GATEWAY_URL", "http://127.0.0.1:18790");
  try {
    const resp = await fetch(`${url}/health`, { signal: AbortSignal.timeout(3000) });
    const data = await resp.json() as { ok?: boolean };
    return data.ok === true;
  } catch {
    return false;
  }
}
