"""
Email notifications via SMTP.

Set these environment variables (or add to a .env file):
  SMTP_HOST  — default smtp.gmail.com
  SMTP_PORT  — default 587
  SMTP_USER  — your Gmail address
  SMTP_PASS  — your Gmail App Password  (not your login password)
               https://myaccount.google.com/apppasswords

If SMTP_USER is not set, all email calls are silently skipped
so bidding still works without email configuration.
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")


def _send(to: str, subject: str, html: str) -> None:
    """Low-level send. Swallows exceptions so callers never crash."""
    if not SMTP_USER or not to:
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = f"BidVault 🔨 <{SMTP_USER}>"
        msg["To"]      = to
        msg.attach(MIMEText(html, "html"))
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
            s.starttls()
            s.login(SMTP_USER, SMTP_PASS)
            s.sendmail(SMTP_USER, to, msg.as_string())
    except Exception as exc:
        print(f"[email] Failed to send to {to}: {exc}")


def _base(body: str) -> str:
    return f"""
    <div style="font-family:'Segoe UI',sans-serif;max-width:520px;margin:0 auto;
                background:#0d0d0d;color:#f0ece3;padding:36px;border-radius:14px;">
      <h2 style="color:#c9a84c;margin:0 0 24px;">🔨 BidVault</h2>
      {body}
      <p style="color:#7a7570;font-size:0.8rem;margin-top:32px;">
        You received this because you placed a bid on BidVault.
      </p>
    </div>"""


def send_bid_confirmation(to: str, bidder: str, item_title: str, amount: float) -> None:
    """Sent to the person who just placed a bid."""
    html = _base(f"""
      <p>Hi <strong>{bidder}</strong>,</p>
      <p>Your bid on <strong>{item_title}</strong> has been placed!</p>
      <div style="background:#1f1f1f;border-radius:10px;padding:16px;margin:20px 0;">
        <p style="margin:0;font-size:0.85rem;color:#7a7570;">YOUR BID</p>
        <p style="margin:4px 0 0;font-size:1.8rem;font-weight:700;color:#c9a84c;">
          ${amount:,.2f}
        </p>
      </div>
      <p>We'll notify you if someone places a higher bid. Good luck!</p>""")
    _send(to, f" Bid confirmed — {item_title}", html)


def send_outbid_notice(to: str, bidder: str, item_title: str, new_amount: float) -> None:
    """Sent to the previous highest bidder when they are outbid."""
    html = _base(f"""
      <p>Hi <strong>{bidder}</strong>,</p>
      <p>You've been outbid on <strong>{item_title}</strong>.</p>
      <div style="background:#1f1f1f;border-radius:10px;padding:16px;margin:20px 0;">
        <p style="margin:0;font-size:0.85rem;color:#7a7570;">NEW HIGHEST BID</p>
        <p style="margin:4px 0 0;font-size:1.8rem;font-weight:700;color:#e05252;">
          ${new_amount:,.2f}
        </p>
      </div>
      <p>Head back to BidVault to reclaim the top spot!</p>""")
    _send(to, f" You've been outbid — {item_title}", html)
