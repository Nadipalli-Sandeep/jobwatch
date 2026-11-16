# JobWatch: automatic fresher job alerts

JobWatch checks for new jobs **every 15 minutes, all day**, and messages you when a
new job fits you:

- **Company**: one of the companies in [data/companies.txt](data/companies.txt)
- **Place**: India
- **Role**: IT, software, SDE, data, AI/ML, analytics, cloud, QA, security
- **Level**: internship, fresher, new grad, or 0-1 years of experience.
  Jobs that ask for 2+ years, or say senior / lead / manager / II / III, are skipped.

It runs on GitHub Actions (free), so your laptop can stay off.

## Where it looks

1. **LinkedIn job search** (public, no login): all India jobs posted in the last 2 hours,
   filtered to your companies. Almost every company posts here.
2. **Company career sites directly**: Workday, Greenhouse, Lever, Ashby,
   SmartRecruiters, Eightfold, Oracle and Amazon. The list is in
   [data/sources.json](data/sources.json). It is found automatically by
   `python -m jobwatch.discover` and refreshed on the 1st of each month.

Each job is sent **only once**. If the same job shows up on LinkedIn and on the
careers page, you get it once.

## What an alert looks like

```
*JobWatch: 2 new jobs* (16 Nov, 10:22 AM)

1. *NVIDIA* - Software Engineer, New College Grad 2027
   Bengaluru, India | FRESHER | Posted Today
   https://nvidia.wd5.myworkdayjobs.com/...

2. *Goldman Sachs* - Summer Analyst 2027 - Engineering
   Bengaluru, Karnataka, India | INTERNSHIP | 12 minutes ago
   https://www.linkedin.com/jobs/view/.../
```

Tags: `INTERNSHIP`, `FRESHER`, `0-1 YRS`, `ENTRY LEVEL` (LinkedIn says entry level),
`EXP NOT STATED` (the job text gives no years. Open it and check).

You also get **one status message every morning at 9 AM**. If it stops coming,
something is broken.

## One-time setup

All private values (phone, email, keys) go into **GitHub Secrets**, never into the code.
Repo: Settings -> Secrets and variables -> Actions -> New repository secret.

### A. Email (works today, free)
1. Turn on 2-Step Verification for your Google account.
2. Go to https://myaccount.google.com/apppasswords and create an app password named "JobWatch".
3. Add secrets: `GMAIL_USER` = your Gmail, `GMAIL_APP_PASSWORD` = the 16 letters,
   `ALERT_EMAIL` = where to send (can be the same Gmail).

### B. Telegram (works today, free, instant phone notification)
1. In Telegram, open **@BotFather** -> `/newbot` -> pick any name. Copy the token.
2. Open your new bot and press **Start**.
3. Open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser and copy the `"chat":{"id": ...}` number.
4. Add secrets: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

### C. WhatsApp (pick ONE)
Add secret `WHATSAPP_PHONE` = `+91XXXXXXXXXX`, then one of:

| Route | Cost | Notes | Secrets |
|---|---|---|---|
| **CallMeBot** (used now) | Free | Save the bot number shown on https://www.callmebot.com/blog/free-api-whatsapp-messages/ (it was +34 644 20 47 56 on 16 Nov 2026) in your contacts. From your WhatsApp send it `I allow callmebot to send me messages`. It replies with your API key. | `CALLMEBOT_APIKEY` |
| **Meta WhatsApp Cloud API** | A few paise per alert | Official. Needs a Meta developer app, a permanent token, and one approved template named `job_alert` (category Utility) with body `New job alert: {{1}} - {{2}} ({{3}}). Apply here: {{4}} - sent by JobWatch`. One message per job. | `META_WA_TOKEN`, `META_WA_PHONE_ID` |
| **Green-API** | Free dev plan | Links a WhatsApp account by QR code (like WhatsApp Web). Use a **second** number as the sender, because messages from your own number to yourself do not ring. | `GREENAPI_ID`, `GREENAPI_TOKEN`, (`GREENAPI_URL` if your console shows a different API URL) |

If WhatsApp fails in a run, email and Telegram still deliver, and failed alerts are retried in the next run.

### D. Start it
Actions tab -> **JobWatch** -> **Run workflow**. The first run only *remembers* the
jobs that already exist (no flood of old jobs) and sends "JobWatch is ON".
After that, only new jobs are sent.

## Test on your laptop

```
py -3.12 -m pip install -r requirements.txt
set DRY_RUN=1
py -3.12 -m jobwatch.run      # first time: remembers jobs only
py -3.12 -m jobwatch.run      # next time: prints new matching jobs
```

## Change things

- Add or remove companies: edit `data/companies.txt`, then run `py -3.12 -m jobwatch.discover`
  (or the "Refresh career sites" workflow).
- Change roles or experience rules: [jobwatch/filters.py](jobwatch/filters.py).
- LinkedIn writes some company names differently (for example "Citi"). Add extra
  names in `EXTRA_ALIASES` in [jobwatch/companies.py](jobwatch/companies.py).

## Honest limits

- Naukri blocks robots with a captcha, so it is not used.
- Workday career sites (NVIDIA, Intel, Dell, Citi, Pfizer and about 70 more) answer GitHub's
  servers with "429 too many requests", so the GitHub run skips them (`SKIP_WORKDAY=1`).
  Those companies are still covered through LinkedIn. On a home computer Workday works.
- Google, Apple, Meta, TCS, Infosys, Wipro, Flipkart and a few others have custom
  career sites with no open data feed. For them JobWatch relies on their LinkedIn posts.
- LinkedIn may slow down or block heavy automatic use. JobWatch makes few, slow requests,
  but if LinkedIn blocks GitHub's servers, the career-site part still works.
- GitHub may start a scheduled run a few minutes late at busy times.
- GitHub pauses schedules in a repo with no activity for 60 days. JobWatch saves its
  memory to the `state` branch on every run, which counts as activity.
