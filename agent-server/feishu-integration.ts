/**
 * GoatGuard 飞书集成模块
 *
 * 功能:
 * 1. 审计报告 → 飞书文档 (docx_builtin_import via MCP)
 * 2. 审计记录 → 飞书多维表格 (bitable via MCP)
 * 3. 高危告警 → 飞书群 Webhook (无需 token，最稳定)
 */

import type { AuditResult, Finding } from "./audit-engine";

// ===== 配置 =====

interface FeishuConfig {
  bitableAppToken: string;
  auditTableId: string;
  alertChatId: string;
  webhookUrl: string;
}

function getConfig(): FeishuConfig {
  return {
    bitableAppToken: process.env.FEISHU_BITABLE_APP_TOKEN || "",
    auditTableId: process.env.FEISHU_AUDIT_TABLE_ID || "",
    alertChatId: process.env.FEISHU_ALERT_CHAT_ID || "",
    webhookUrl: process.env.FEISHU_WEBHOOK_URL || "",
  };
}

const config = new Proxy({} as FeishuConfig, {
  get(_target, prop: string) {
    return getConfig()[prop as keyof FeishuConfig];
  },
});

// ===== 飞书 MCP 调用封装 =====

type FeishuMCPCaller = (toolName: string, args: Record<string, unknown>) => Promise<unknown>;

let mcpCaller: FeishuMCPCaller;

export function initFeishu(caller: FeishuMCPCaller) {
  mcpCaller = caller;
}

// ===== 1. 审计报告 → 飞书文档 =====

export async function exportReportToFeishu(
  markdown: string,
  contractName: string
): Promise<void> {
  const fileName = `GoatGuard-${contractName}`.slice(0, 27);

  await mcpCaller("docx_builtin_import", {
    data: {
      markdown,
      file_name: fileName,
    },
  });

  console.log(`[Feishu] Report exported: ${fileName}`);
}

// ===== 2. 审计记录 → 飞书多维表格 =====

export async function logAuditRecord(result: AuditResult): Promise<void> {
  if (!config.bitableAppToken || !config.auditTableId) {
    console.warn("[Feishu] Bitable not configured, skipping record log");
    return;
  }

  await mcpCaller("bitable_v1_appTableRecord_create", {
    path: {
      app_token: config.bitableAppToken,
      table_id: config.auditTableId,
    },
    data: {
      fields: {
        "合约名称": result.contractName,
        "风险评级": result.riskLevel,
        "Critical": result.critical,
        "High": result.high,
        "Medium": result.medium,
        "Low": result.low,
        "审计时间": Date.now(),
        "支付交易": result.paymentTx,
        "Agent ID": result.agentId,
        "状态": "已完成",
      },
    },
  });

  console.log(`[Feishu] Audit record logged for: ${result.contractName}`);
}

// ===== 3. 高危告警 → 飞书群 Webhook =====

export async function sendCriticalAlert(
  result: AuditResult,
  criticalFindings: Finding[]
): Promise<void> {
  if (!config.webhookUrl && !config.alertChatId) {
    console.warn("[Feishu] No webhook or chat configured, skipping alert");
    return;
  }

  const findingsList = criticalFindings
    .map((f) => `  - ${f.severity}: ${f.title} @ ${f.location}`)
    .join("\n");

  const alertText =
    `🚨 GoatGuard 安全告警\n\n` +
    `合约: ${result.contractName}\n` +
    `风险评级: ${result.riskLevel}\n` +
    `高危发现 ${criticalFindings.length} 项:\n` +
    `${findingsList}\n\n` +
    `审计 Agent: ${result.agentId}\n` +
    `时间: ${result.timestamp}`;

  // 优先使用 Webhook（无需 token，更稳定）
  if (config.webhookUrl) {
    await sendWebhook(alertText);
  } else if (config.alertChatId && mcpCaller) {
    await mcpCaller("im_v1_message_create", {
      params: { receive_id_type: "chat_id" },
      data: {
        receive_id: config.alertChatId,
        msg_type: "text",
        content: JSON.stringify({ text: alertText }),
      },
    });
  }

  console.log(`[Feishu] Critical alert sent for: ${result.contractName}`);
}

// ===== Webhook 发送 =====

export async function sendWebhook(text: string): Promise<void> {
  if (!config.webhookUrl) return;

  const resp = await fetch(config.webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      msg_type: "text",
      content: { text },
    }),
  });

  if (!resp.ok) {
    console.error(`[Feishu Webhook] HTTP ${resp.status}`);
  }
}

export async function sendWebhookRichAlert(result: AuditResult, findings: Finding[]): Promise<void> {
  if (!config.webhookUrl) return;

  const elements = [
    {
      tag: "markdown",
      content: `**合约**: ${result.contractName}\n**风险评级**: ${result.riskLevel}\n**审计时间**: ${result.timestamp}`,
    },
    {
      tag: "markdown",
      content: findings
        .map((f) => `• **${f.severity}** — ${f.title} @ \`${f.location}\``)
        .join("\n"),
    },
  ];

  await fetch(config.webhookUrl, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      msg_type: "interactive",
      card: {
        header: {
          title: { tag: "plain_text", content: "🚨 GoatGuard 安全审计告警" },
          template: "red",
        },
        elements,
      },
    }),
  });
}

// ===== 4. 扫描开始通知 =====

export async function notifyScanStarted(
  taskId: string,
  inputs: string[],
  extra?: { email?: string; paymentTx?: string },
): Promise<void> {
  const inputPreview = inputs.map((s) => s.length > 60 ? s.slice(0, 57) + "..." : s).join("\n  · ");
  let text =
    `✅ **收到审计请求**\n` +
    `任务 ID: \`${taskId}\`\n` +
    `输入:\n  · ${inputPreview}\n` +
    `预计完成: ~5 分钟`;
  if (extra?.email) text += `\n📧 客户邮箱: ${extra.email}`;
  if (extra?.paymentTx) text += `\n💰 付款交易: \`${extra.paymentTx}\``;

  if (config.webhookUrl) {
    await fetch(config.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        msg_type: "interactive",
        card: {
          header: {
            title: { tag: "plain_text", content: "✅ GoatGuard 收到审计请求" },
            template: "green",
          },
          elements: [{ tag: "markdown", content: text }],
        },
      }),
    });
    console.log(`[Feishu] Scan started notification sent: ${taskId}`);
  }
}

// ===== 5. 扫描完成通知 (带报告链接) =====

export async function notifyScanCompleted(
  result: AuditResult,
  reportUrl?: string,
  extra?: { email?: string },
): Promise<void> {
  const stats = `${result.critical}C / ${result.high}H / ${result.medium}M / ${result.low}L`;
  let text =
    `**合约**: ${result.contractName}\n` +
    `**风险等级**: ${result.riskLevel}\n` +
    `**发现**: ${stats}\n` +
    `**审计时间**: ${result.timestamp}`;
  if (reportUrl) {
    text += `\n📄 **完整报告**: [点击查看](${reportUrl})`;
  }
  if (extra?.email) {
    text += `\n📧 **客户邮箱**: ${extra.email}`;
  }

  if (config.webhookUrl) {
    await fetch(config.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        msg_type: "interactive",
        card: {
          header: {
            title: { tag: "plain_text", content: "📋 GoatGuard 扫描完成" },
            template: result.critical > 0 ? "red" : result.high > 0 ? "orange" : "green",
          },
          elements: [{ tag: "markdown", content: text }],
        },
      }),
    });
    console.log(`[Feishu] Scan completed notification sent: ${result.contractName}`);
  }
}

// ===== 完整流程: 审计完成后的飞书输出 =====

export async function onAuditComplete(
  result: AuditResult,
  reportMarkdown: string
): Promise<{ reportUrl?: string }> {
  let reportUrl: string | undefined;

  try {
    await exportReportToFeishu(reportMarkdown, result.contractName);
  } catch (e) {
    console.warn("[Feishu] Report export failed, continuing:", e);
  }

  try {
    await logAuditRecord(result);
  } catch (e) {
    console.warn("[Feishu] Bitable record failed, continuing:", e);
  }

  const criticalFindings = result.findings.filter(
    (f) => f.severity === "Critical" || f.severity === "High"
  );
  if (criticalFindings.length > 0) {
    try {
      await sendCriticalAlert(result, criticalFindings);
    } catch (e) {
      console.warn("[Feishu] Critical alert failed, continuing:", e);
    }
  }

  await notifyScanCompleted(result, reportUrl);

  return { reportUrl };
}
