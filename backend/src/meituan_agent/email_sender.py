"""
邮件发送 — 执行完成后将行程发送至用户邮箱
"""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_itinerary_email(
    *,
    to_email: str,
    subject: str,
    html_body: str,
    smtp_host: str = "smtp.qq.com",
    smtp_port: int = 587,
    sender_email: str | None = None,
    sender_password: str | None = None,
) -> bool:
    """发送行程邮件。

    使用 QQ 邮箱 SMTP。sender_email / sender_password 从环境变量读取：
      MEITUAN_AGENT_EMAIL_SENDER
      MEITUAN_AGENT_EMAIL_PASSWORD（QQ 邮箱授权码，非登录密码）

    若未配置凭据，仅 log 预览，返回 False。
    """
    import os

    sender = sender_email or os.getenv("MEITUAN_AGENT_EMAIL_SENDER")
    password = sender_password or os.getenv("MEITUAN_AGENT_EMAIL_PASSWORD")

    if not sender or not password:
        logger.warning("邮件凭据未配置，跳过发送。预览:\n%s", html_body[:500])
        return False

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = to_email
        msg.attach(MIMEText(html_body, "html", "utf-8"))

        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(sender, password)
            server.sendmail(sender, [to_email], msg.as_string())

        logger.info("行程邮件已发送至 %s", to_email)
        return True

    except Exception as e:
        logger.error("邮件发送失败: %s", e)
        return False


def build_itinerary_html(plan_title: str, plan_rationale: str, items: list[dict]) -> str:
    """构建行程 HTML 邮件"""
    rows = ""
    for i, item in enumerate(items, 1):
        leg = item.get("leg", "")
        leg_str = f"<br><small style='color:#888;'>{leg}</small>" if leg else ""
        rows += f"""
        <tr>
          <td style="padding:10px 14px;border-bottom:1px solid #eee;">
            <strong>{i}.</strong> {item['poi']}
            <small style="color:#666;">[{item.get('category', '')}]</small>
            {leg_str}
            <br><span style="color:#f0b400;font-size:13px;">{item.get('status', '')}</span>
          </td>
        </tr>"""
    return f"""
    <div style="max-width:600px;margin:0 auto;font-family:Arial,sans-serif;background:#f9f9f9;padding:24px;border-radius:12px;">
      <h2 style="color:#333;border-bottom:2px solid #f0b400;padding-bottom:10px;">🍜 {plan_title}</h2>
      <p style="color:#666;font-style:italic;">{plan_rationale}</p>
      <table style="width:100%;border-collapse:collapse;background:#fff;border-radius:8px;">
        {rows}
      </table>
      <p style="color:#999;font-size:13px;margin-top:20px;text-align:center;">
        由「私人规划执行助理」自动生成
      </p>
    </div>"""
