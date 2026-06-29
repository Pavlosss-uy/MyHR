"""
Centralised email dispatch for MyHR.

send_in_background() is a plain synchronous function designed to be passed
directly to FastAPI's BackgroundTasks.  Starlette automatically runs sync
background tasks in a thread-pool executor, so it never blocks the event loop
and HTTP responses are returned immediately.

Transport priority:
  1. Gmail SMTP  — set SMTP_USER + SMTP_PASS (16-char Google App Password)
  2. Resend API  — set RESEND_API_KEY (requires verified domain to send to others)

Generate a Gmail App Password at: https://myaccount.google.com/apppasswords
"""

import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import resend

logger = logging.getLogger(__name__)

_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASS = os.getenv("SMTP_PASS", "")
_FROM_SMTP = os.getenv("EMAIL_FROM", f"MyHR <{_SMTP_USER}>") if _SMTP_USER else "MyHR"

resend.api_key = os.getenv("RESEND_API_KEY", "")
_FROM_RESEND = os.getenv("EMAIL_FROM", "MyHR <onboarding@resend.dev>")

MYHR_BASE_URL = os.getenv("MYHR_BASE_URL", "http://localhost:5173")


# ── Dispatcher ────────────────────────────────────────────────────────────────

def send_in_background(to: str, subject: str, html_body: str) -> None:
    """
    Synchronous email dispatch — tries Gmail SMTP first, then Resend.
    Always pass this to FastAPI BackgroundTasks; never call directly from async code.
    """
    if _SMTP_USER and _SMTP_PASS:
        _send_smtp(to, subject, html_body)
    elif resend.api_key:
        _send_resend(to, subject, html_body)
    else:
        logger.warning("No email transport configured (set SMTP_USER+SMTP_PASS or RESEND_API_KEY) — skipping: %s", to)


def _send_smtp(to: str, subject: str, html_body: str) -> None:
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = _FROM_SMTP
        msg["To"] = to
        msg.attach(MIMEText(html_body, "html", "utf-8"))
        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(_SMTP_USER, _SMTP_PASS)
            smtp.sendmail(_SMTP_USER, [to], msg.as_string())
        logger.info("sent (smtp) → %s | %s", to, subject)
    except smtplib.SMTPAuthenticationError:
        logger.error("SMTP auth failed — use a Google App Password, not your Gmail password")
    except Exception as exc:
        logger.error("SMTP failed → %s | %s", to, exc)


def _send_resend(to: str, subject: str, html_body: str) -> None:
    try:
        resend.Emails.send({"from": _FROM_RESEND, "to": [to], "subject": subject, "html": html_body})
        logger.info("sent (resend) → %s | %s", to, subject)
    except Exception as exc:
        # Resend free plan only delivers to verified domains / the account owner's email.
        # If you see this error, add SMTP_USER + SMTP_PASS to .env instead.
        logger.error("Resend failed → %s | %s | hint: use SMTP_USER+SMTP_PASS for unrestricted delivery", to, exc)


# ── Shared layout shell ───────────────────────────────────────────────────────

def _shell(body: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1.0"/>
</head>
<body style="margin:0;padding:0;background:#f1f5f9;
             font-family:'Segoe UI',Helvetica,Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0"
         style="padding:40px 16px;">
    <tr><td align="center">
      <table cellpadding="0" cellspacing="0"
             style="width:100%;max-width:520px;background:#ffffff;
                    border-radius:16px;overflow:hidden;
                    box-shadow:0 4px 24px rgba(0,0,0,0.07);">

        <!-- ── header ── -->
        <tr>
          <td style="background:linear-gradient(135deg,#1e3a8a 0%,#3b82f6 100%);
                     padding:28px 40px;text-align:center;">
            <span style="font-size:22px;font-weight:700;color:#fff;letter-spacing:-0.5px;">
              My<span style="color:#93c5fd;">HR</span>
            </span><br/>
            <span style="font-size:11px;color:#bfdbfe;letter-spacing:1.5px;
                         text-transform:uppercase;">Enterprise Platform</span>
          </td>
        </tr>

        <!-- ── body ── -->
        <tr><td style="padding:36px 40px;">{body}</td></tr>

        <!-- ── footer ── -->
        <tr>
          <td style="background:#f8fafc;border-top:1px solid #e2e8f0;
                     padding:18px 40px;text-align:center;">
            <p style="margin:0;font-size:12px;color:#94a3b8;">
              © 2026 MyHR · AI-Powered Hiring Platform<br/>
              <span style="color:#cbd5e1;">
                If you didn't expect this email, you can safely ignore it.
              </span>
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


# ── Templates ─────────────────────────────────────────────────────────────────

def _validate_link(link: str) -> str:
    """Ensure the link starts with MYHR_BASE_URL to prevent open redirect."""
    if not link.startswith(MYHR_BASE_URL):
        raise ValueError(
            f"Link must start with {MYHR_BASE_URL!r}, got {link!r}"
        )
    return link


def hr_invitation_html(
    contact_name: str,
    company_name: str,
    link: str,
    expires_hours: int = 72,
) -> str:
    """Email sent to an HR contact when their access request is approved."""
    link = _validate_link(link)
    _name = html.escape(contact_name)
    _company = html.escape(company_name)
    _link = html.escape(link)
    body = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;">
  Access approved! 🎉
</h2>
<p style="margin:0 0 24px;font-size:14px;color:#64748b;">Hi {_name},</p>

<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#334155;">
  Your enterprise access request for
  <strong style="color:#1e3a8a;">{_company}</strong> has been approved.
  Click the button below to complete your account setup and start hiring smarter.
</p>

<div style="background:#eff6ff;border-left:4px solid #3b82f6;
            border-radius:8px;padding:14px 18px;margin:20px 0;">
  <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#1d4ed8;">
    What to do next
  </p>
  <ul style="margin:0;padding-left:18px;font-size:13px;
             color:#334155;line-height:1.9;">
    <li>Create your account using the button below</li>
    <li>Post your first job and upload candidate CVs</li>
    <li>Let AI rank and interview your shortlist automatically</li>
  </ul>
</div>

<div style="text-align:center;margin:28px 0;">
  <a href="{_link}"
     style="display:inline-block;
            background:linear-gradient(135deg,#1e3a8a,#3b82f6);
            color:#fff;padding:14px 40px;border-radius:10px;
            text-decoration:none;font-weight:600;font-size:15px;">
    Create Your Account →
  </a>
</div>

<p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
  ⏰ This invitation expires in <strong>{expires_hours} hours</strong>.
</p>"""
    return _shell(body)


def candidate_interview_html(
    candidate_name: str,
    job_title: str,
    company_name: str,
    link: str,
    expires_days: int = 7,
) -> str:
    """Email sent to a candidate when they are invited to an AI interview."""
    link = _validate_link(link)
    _name = html.escape(candidate_name)
    _title = html.escape(job_title)
    _company = html.escape(company_name)
    _link = html.escape(link)
    body = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;">
  Interview invitation
</h2>
<p style="margin:0 0 24px;font-size:14px;color:#64748b;">Hi {_name},</p>

<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#334155;">
  You've been shortlisted for the
  <strong style="color:#1e3a8a;">{_title}</strong> role at
  <strong>{_company}</strong> and are invited to complete an
  AI-powered interview.
</p>

<div style="background:#f0fdf4;border-left:4px solid #22c55e;
            border-radius:8px;padding:14px 18px;margin:20px 0;">
  <p style="margin:0 0 6px;font-size:13px;font-weight:600;color:#15803d;">
    What to expect
  </p>
  <ul style="margin:0;padding-left:18px;font-size:13px;
             color:#334155;line-height:1.9;">
    <li>5–7 questions tailored to the role · roughly <strong>10–15 minutes</strong></li>
    <li>Type or speak your answers — no extra software needed</li>
    <li>Complete it any time before the link expires</li>
  </ul>
</div>

<div style="text-align:center;margin:28px 0;">
  <a href="{_link}"
     style="display:inline-block;
            background:linear-gradient(135deg,#15803d,#22c55e);
            color:#fff;padding:14px 40px;border-radius:10px;
            text-decoration:none;font-weight:600;font-size:15px;">
    Start Your Interview →
  </a>
</div>

<p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;">
  ⏰ This link expires in <strong>{expires_days} days</strong>. Best of luck!
</p>"""
    return _shell(body)


def admin_new_request_html(
    company_name: str,
    company_size: str,
    contact_name: str,
    contact_email: str,
    admin_url: str,
) -> str:
    """Internal alert sent to the admin when a new access request arrives."""
    _validate_link(admin_url)
    _company = html.escape(company_name)
    _size = html.escape(company_size)
    _name = html.escape(contact_name)
    _email = html.escape(contact_email)
    _url = html.escape(admin_url)
    body = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;">
  New access request
</h2>
<p style="margin:0 0 20px;font-size:14px;color:#64748b;">
  A new enterprise request is waiting for your review.
</p>

<table cellpadding="0" cellspacing="0"
       style="width:100%;border-collapse:collapse;font-size:14px;margin:0 0 24px;">
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;color:#64748b;font-weight:600;
               border-bottom:1px solid #e2e8f0;width:130px;">Company</td>
    <td style="padding:10px 14px;color:#0f172a;
               border-bottom:1px solid #e2e8f0;">{_company}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;color:#64748b;font-weight:600;
               border-bottom:1px solid #e2e8f0;">Size</td>
    <td style="padding:10px 14px;color:#0f172a;
               border-bottom:1px solid #e2e8f0;">{_size}</td>
  </tr>
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;color:#64748b;font-weight:600;
               border-bottom:1px solid #e2e8f0;">Contact</td>
    <td style="padding:10px 14px;color:#0f172a;
               border-bottom:1px solid #e2e8f0;">{_name}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;color:#64748b;font-weight:600;">Email</td>
    <td style="padding:10px 14px;color:#0f172a;">{_email}</td>
  </tr>
</table>

<div style="text-align:center;margin:24px 0;">
  <a href="{_url}"
     style="display:inline-block;
            background:linear-gradient(135deg,#1e3a8a,#3b82f6);
            color:#fff;padding:13px 36px;border-radius:10px;
            text-decoration:none;font-weight:600;font-size:14px;">
    Review in Admin Panel →
  </a>
</div>"""
    return _shell(body)
