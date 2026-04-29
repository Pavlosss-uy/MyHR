"""
Centralised email dispatch for MyHR.

send_in_background() is a plain synchronous function designed to be passed
directly to FastAPI's BackgroundTasks.  Starlette automatically runs sync
background tasks in a thread-pool executor, so it never blocks the event loop
and HTTP responses are returned immediately.

Transport: Gmail SMTP via STARTTLS (smtp.gmail.com:587).
Use a 16-character Google App Password — NOT your normal Gmail password.
Generate one at: https://myaccount.google.com/apppasswords

Required environment variables
  SMTP_USER    Full Gmail address        e.g. myhr2026@gmail.com
  SMTP_PASS    16-char Google App Pass   e.g. xxxx xxxx xxxx xxxx
  EMAIL_FROM   Display name + address    e.g. MyHR <myhr2026@gmail.com>
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587
_SMTP_USER = os.getenv("SMTP_USER", "")
_SMTP_PASS = os.getenv("SMTP_PASS", "")
_FROM      = os.getenv("EMAIL_FROM", f"MyHR <{_SMTP_USER}>")


# ── Dispatcher ────────────────────────────────────────────────────────────────

def send_in_background(to: str, subject: str, html: str) -> None:
    """
    Synchronous Gmail SMTP dispatch over STARTTLS.
    Always pass this to FastAPI BackgroundTasks — never call it directly from
    an async route, because smtplib is blocking and must run in a thread pool.
    """
    if not _SMTP_USER or not _SMTP_PASS:
        print(f"[email] SMTP_USER/SMTP_PASS not configured — skipping: {to} | {subject}")
        return
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"]    = _FROM
        msg["To"]      = to
        msg.attach(MIMEText(html, "html", "utf-8"))

        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT) as smtp:
            smtp.ehlo()
            smtp.starttls()
            smtp.ehlo()
            smtp.login(_SMTP_USER, _SMTP_PASS)
            smtp.sendmail(_SMTP_USER, [to], msg.as_string())

        print(f"[email] ✓ sent → {to} | {subject}")
    except smtplib.SMTPAuthenticationError:
        print(f"[email] ✗ authentication failed — check SMTP_USER and SMTP_PASS (use an App Password, not your Gmail password)")
    except smtplib.SMTPRecipientsRefused:
        print(f"[email] ✗ recipient refused → {to}")
    except Exception as exc:
        print(f"[email] ✗ failed → {to} | {exc}")


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

def hr_invitation_html(
    contact_name: str,
    company_name: str,
    link: str,
    expires_hours: int = 72,
) -> str:
    """Email sent to an HR contact when their access request is approved."""
    body = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;">
  Access approved! 🎉
</h2>
<p style="margin:0 0 24px;font-size:14px;color:#64748b;">Hi {contact_name},</p>

<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#334155;">
  Your enterprise access request for
  <strong style="color:#1e3a8a;">{company_name}</strong> has been approved.
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
  <a href="{link}"
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
    body = f"""
<h2 style="margin:0 0 6px;font-size:22px;font-weight:700;color:#0f172a;">
  Interview invitation
</h2>
<p style="margin:0 0 24px;font-size:14px;color:#64748b;">Hi {candidate_name},</p>

<p style="margin:0 0 16px;font-size:15px;line-height:1.7;color:#334155;">
  You've been shortlisted for the
  <strong style="color:#1e3a8a;">{job_title}</strong> role at
  <strong>{company_name}</strong> and are invited to complete an
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
  <a href="{link}"
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
               border-bottom:1px solid #e2e8f0;">{company_name}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;color:#64748b;font-weight:600;
               border-bottom:1px solid #e2e8f0;">Size</td>
    <td style="padding:10px 14px;color:#0f172a;
               border-bottom:1px solid #e2e8f0;">{company_size}</td>
  </tr>
  <tr style="background:#f8fafc;">
    <td style="padding:10px 14px;color:#64748b;font-weight:600;
               border-bottom:1px solid #e2e8f0;">Contact</td>
    <td style="padding:10px 14px;color:#0f172a;
               border-bottom:1px solid #e2e8f0;">{contact_name}</td>
  </tr>
  <tr>
    <td style="padding:10px 14px;color:#64748b;font-weight:600;">Email</td>
    <td style="padding:10px 14px;color:#0f172a;">{contact_email}</td>
  </tr>
</table>

<div style="text-align:center;margin:24px 0;">
  <a href="{admin_url}"
     style="display:inline-block;
            background:linear-gradient(135deg,#1e3a8a,#3b82f6);
            color:#fff;padding:13px 36px;border-radius:10px;
            text-decoration:none;font-weight:600;font-size:14px;">
    Review in Admin Panel →
  </a>
</div>"""
    return _shell(body)
