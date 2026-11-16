"""Send alerts: WhatsApp, Gmail, and Telegram.

All settings come from environment variables (GitHub Secrets), never from code:
  WHATSAPP_PHONE      e.g. +919xxxxxxxxx  (your number, receives alerts)
  WhatsApp route - set ONE of these groups:
    CALLMEBOT_APIKEY                     free; key that CallMeBot sends you
    META_WA_TOKEN + META_WA_PHONE_ID     official Meta WhatsApp Cloud API
      (META_WA_TEMPLATE default "job_alert", META_WA_LANG default "en")
    GREENAPI_ID + GREENAPI_TOKEN         Green-API (sender = a second WhatsApp number)
      (GREENAPI_URL default https://api.green-api.com)
  GMAIL_USER          your Gmail address (sender)
  GMAIL_APP_PASSWORD  16-letter Google "app password"
  ALERT_EMAIL         where to send (defaults to GMAIL_USER)
  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID   optional extra channel
  DRY_RUN=1           print messages instead of sending
"""
import html
import os
import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from .common import SESSION, now_ist

WA_CHARS = 1400          # keep each WhatsApp message short enough for CallMeBot
WA_MAX_MESSAGES = 6      # per run; the rest goes to email


def _env(k):
    return (os.environ.get(k) or "").strip()


def dry():
    return _env("DRY_RUN") == "1"


def wa_route():
    if not _env("WHATSAPP_PHONE"):
        return ""
    if _env("META_WA_TOKEN") and _env("META_WA_PHONE_ID"):
        return "meta"
    if _env("GREENAPI_ID") and _env("GREENAPI_TOKEN"):
        return "greenapi"
    if _env("CALLMEBOT_APIKEY"):
        return "callmebot"
    return ""


def _digits(phone):
    return "".join(c for c in phone if c.isdigit())


def channels():
    ch = []
    if wa_route():
        ch.append("whatsapp")
    if _env("GMAIL_USER") and _env("GMAIL_APP_PASSWORD"):
        ch.append("email")
    if _env("TELEGRAM_BOT_TOKEN") and _env("TELEGRAM_CHAT_ID"):
        ch.append("telegram")
    return ch


# ------------------------------------------------------------------ formatting
def _job_block(i, j):
    yrs = f" ({j['years']}+ yrs asked)" if j.get("years") else ""
    lines = [f"{i}. *{j['company_short']}* - {j['title']}",
             f"   {j['location'] or 'India'} | {j['tag']}{yrs}" + (f" | {j['posted']}" if j.get("posted") else ""),
             f"   {j['url']}"]
    return "\n".join(lines)


def whatsapp_texts(jobs):
    head = f"*JobWatch: {len(jobs)} new job{'s' if len(jobs) != 1 else ''}* ({now_ist():%d %b, %I:%M %p})"
    msgs, cur = [], head
    for i, j in enumerate(jobs, 1):
        block = _job_block(i, j)
        if len(cur) + len(block) + 2 > WA_CHARS:
            msgs.append(cur)
            cur = block
        else:
            cur += "\n\n" + block
    msgs.append(cur)
    if len(msgs) > WA_MAX_MESSAGES:
        rest = len(jobs) - sum(m.count("\n   http") for m in msgs[:WA_MAX_MESSAGES])
        msgs = msgs[:WA_MAX_MESSAGES]
        msgs[-1] += f"\n\n...and {rest} more. Full list is in your email."
    return msgs


def email_html(jobs, intro=""):
    rows = []
    for j in jobs:
        rows.append(
            "<tr>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'><b>{html.escape(j['company_short'])}</b></td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'><a href='{html.escape(j['url'])}'>{html.escape(j['title'])}</a></td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{html.escape(j['location'] or 'India')}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{html.escape(j['tag'])}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{html.escape(j.get('posted') or '')}</td>"
            f"<td style='padding:6px 8px;border-bottom:1px solid #ddd'>{html.escape(j['source'])}</td>"
            "</tr>")
    return (f"<div style='font-family:Arial,sans-serif;font-size:14px'>{intro}"
            "<table style='border-collapse:collapse'>"
            "<tr style='background:#f0f0f0'><th align=left style='padding:6px 8px'>Company</th>"
            "<th align=left style='padding:6px 8px'>Job</th><th align=left style='padding:6px 8px'>Location</th>"
            "<th align=left style='padding:6px 8px'>Type</th><th align=left style='padding:6px 8px'>Posted</th>"
            "<th align=left style='padding:6px 8px'>Found on</th></tr>"
            + "".join(rows) + "</table></div>")


# ------------------------------------------------------------------ senders
def send_whatsapp(text):
    """Free-text WhatsApp (CallMeBot / Green-API). Meta needs templates: see send_whatsapp_meta."""
    if dry():
        print("---- WHATSAPP ----\n" + text)
        return True
    route = wa_route()
    try:
        if route == "greenapi":
            base = (_env("GREENAPI_URL") or "https://api.green-api.com").rstrip("/")
            r = SESSION.post(f"{base}/waInstance{_env('GREENAPI_ID')}/sendMessage/{_env('GREENAPI_TOKEN')}",
                             json={"chatId": f"{_digits(_env('WHATSAPP_PHONE'))}@c.us", "message": text},
                             timeout=60)
            ok = r.status_code == 200 and "idMessage" in r.text
        elif route == "callmebot":
            r = SESSION.get("https://api.callmebot.com/whatsapp.php",
                            params={"phone": _env("WHATSAPP_PHONE"), "text": text,
                                    "apikey": _env("CALLMEBOT_APIKEY")}, timeout=60)
            ok = r.status_code == 200 and "error" not in r.text.lower()[:500]
        elif route == "meta":
            return send_whatsapp_meta_text(text)
        else:
            return False
    except Exception as e:
        print(f"whatsapp failed: {e.__class__.__name__}")
        return False
    if not ok:
        print(f"whatsapp ({route}) failed: HTTP {r.status_code} {r.text[:200]!r}")
    return ok


def _meta_send(payload):
    ver = _env("META_API_VERSION") or "v23.0"
    r = SESSION.post(f"https://graph.facebook.com/{ver}/{_env('META_WA_PHONE_ID')}/messages",
                     headers={"Authorization": f"Bearer {_env('META_WA_TOKEN')}"},
                     json={"messaging_product": "whatsapp", "to": _digits(_env("WHATSAPP_PHONE")), **payload},
                     timeout=60)
    if r.status_code != 200:
        print(f"whatsapp (meta) failed: HTTP {r.status_code} {r.text[:300]!r}")
    return r.status_code == 200


def _clean_param(s, n=200):
    # Meta template values may not contain new lines, tabs or 4+ spaces.
    s = " ".join(str(s).split())
    return s[:n] or "-"


def send_whatsapp_meta_job(j):
    """One template message per job. Template body (create it in Meta, category Utility):
    New job: {{1}} - {{2}} | {{3}} | Apply: {{4}}"""
    params = [_clean_param(j["company_short"], 60), _clean_param(j["title"], 120),
              _clean_param(f"{j['location'] or 'India'} | {j['tag']}", 120), _clean_param(j["url"], 500)]
    return _meta_send({"type": "template", "template": {
        "name": _env("META_WA_TEMPLATE") or "job_alert",
        "language": {"code": _env("META_WA_LANG") or "en"},
        "components": [{"type": "body", "parameters": [{"type": "text", "text": p} for p in params]}]}})


def send_whatsapp_meta_text(text):
    """Status notes through the same template (company=JobWatch, title=note)."""
    return send_whatsapp_meta_job({"company_short": "JobWatch", "title": text.replace("*", "")[:120],
                                   "location": "status", "tag": "info", "url": "-"})


def send_email(subject, body_html):
    if dry():
        print(f"---- EMAIL: {subject} ({len(body_html)} chars html)")
        return True
    user = _env("GMAIL_USER")
    to = _env("ALERT_EMAIL") or user
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, f"JobWatch <{user}>", to
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=60) as s:
            s.login(user, _env("GMAIL_APP_PASSWORD").replace(" ", ""))
            s.sendmail(user, [to], msg.as_string())
        return True
    except Exception as e:
        print(f"email failed: {e.__class__.__name__}: {e}")
        return False


def send_telegram(text):
    if dry():
        return True
    try:
        r = SESSION.post(f"https://api.telegram.org/bot{_env('TELEGRAM_BOT_TOKEN')}/sendMessage",
                         data={"chat_id": _env("TELEGRAM_CHAT_ID"), "text": text.replace("*", ""),
                               "disable_web_page_preview": "true"}, timeout=30)
        return r.status_code == 200
    except Exception:
        return False


def send_jobs(jobs):
    """Send one batch. Returns True if at least one channel delivered."""
    if not jobs:
        return True
    ch = channels() if not dry() else ["whatsapp", "email"]
    if not ch:
        print("No alert channel configured (set WHATSAPP_PHONE+CALLMEBOT_APIKEY or GMAIL_*).")
        return False
    delivered = False
    if "whatsapp" in ch:
        ok_all = True
        if wa_route() == "meta" and not dry():
            for j in jobs[:25]:
                ok_all &= send_whatsapp_meta_job(j)
        else:
            for t in whatsapp_texts(jobs):
                ok_all &= send_whatsapp(t)
                time.sleep(4)
        delivered |= ok_all
    if "telegram" in ch:
        for t in whatsapp_texts(jobs):
            delivered |= send_telegram(t)
    if "email" in ch:
        top = jobs[0]
        subj = (f"[JobWatch] {len(jobs)} new: {top['company_short']} - {top['title'][:60]}"
                if len(jobs) > 1 else f"[JobWatch] {top['company_short']} - {top['title'][:80]}")
        delivered |= send_email(subj, email_html(jobs))
    return delivered


def send_note(text):
    """Plain status message (start-up, daily heartbeat)."""
    ch = channels() if not dry() else ["whatsapp", "email"]
    ok = False
    if "whatsapp" in ch:
        ok |= send_whatsapp(text)
    if "telegram" in ch:
        ok |= send_telegram(text)
    if "email" in ch:
        ok |= send_email("[JobWatch] " + text.split("\n")[0].replace("*", "")[:90],
                         "<pre style='font-family:Arial,sans-serif;font-size:14px'>"
                         + html.escape(text.replace("*", "")) + "</pre>")
    return ok
