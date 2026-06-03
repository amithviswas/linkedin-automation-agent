# 🤖 LinkedIn Automation Agent

> Fully autonomous AI LinkedIn Content Engine — researches, writes, and publishes daily posts using Gemini 2.0 Flash + GitHub Actions + Google Sheets + Make.com. **Total cost: ₹0/month.**

---

## 🏗️ Architecture

```
GitHub Actions (8 AM IST, Mon–Fri)
         │
         ▼
 Research Agent ──────────────────── Gemini 2.0 Flash + Google Search
 Fetches 15-20 tech/AI news items    (HackerNews, TechCrunch, AI blogs...)
         │
         ▼
 Filtering Agent ─────────────────── Gemini 2.0 Flash
 Scores & selects top 5 stories      (viral potential × relevance × India fit)
         │
         ▼
 Content Agent ───────────────────── Gemini 2.0 Flash (temp: 0.85)
 Generates 3 formats per story:      ① Text Post  ② Carousel Script  ③ Short Take
         │
         ▼
 Google Sheets (PostQueue tab) ────── gspread + Service Account
 All 5 posts stored with schedule
         │
         ▼
 Make.com Webhook ─────────────────── httpx POST
 Today's #1 post auto-published       LinkedIn auto-posting scenario
         │
         ▼
 LinkedIn Profile 🚀
```

---

## 📁 Project Structure

```
linkedin-agent/
├── main.py                          # Orchestrator — run this
├── requirements.txt
├── .env.example                     # Copy to .env and fill in secrets
│
├── agents/
│   ├── research_agent.py            # Fetches news via Gemini + Google Search
│   ├── filtering_agent.py           # Scores & ranks stories
│   └── content_agent.py             # Generates LinkedIn content
│
├── integrations/
│   ├── sheets.py                    # Google Sheets post queue
│   └── make_webhook.py              # Make.com LinkedIn posting trigger
│
├── prompts/
│   ├── research_prompt.txt          # Research agent system prompt
│   ├── filter_prompt.txt            # Filtering agent system prompt
│   └── content_prompt.txt           # Content generation system prompt
│
├── config/
│   └── settings.py                  # Env var loader
│
├── utils/
│   ├── logger.py                    # Rich-powered logger
│   └── helpers.py                   # Shared utilities
│
└── .github/
    └── workflows/
        └── daily_post.yml           # GitHub Actions schedule
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/linkedin-automation-agent.git
cd linkedin-automation-agent
pip install -r requirements.txt
```

### 2. Set Up Secrets

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required secrets:

| Secret | How to Get |
|--------|-----------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) → Get API key |
| `GOOGLE_SHEETS_CREDS` | Google Cloud Console → Service Account → JSON key |
| `GOOGLE_SHEET_ID` | From your Google Sheet URL |
| `MAKE_WEBHOOK_URL` | Make.com → Webhooks → Custom webhook |

### 3. Test Locally (Dry Run)

```bash
# Test the full pipeline without writing to Sheets or posting
python main.py --dry-run

# Test with fewer stories
python main.py --dry-run --story-count 2
```

### 4. Full Run

```bash
python main.py
```

---

## 🔧 Google Sheets Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or use existing)
3. Enable **Google Sheets API** and **Google Drive API**
4. Create a **Service Account** → Download JSON key
5. Create a Google Sheet and **share it** with the service account email
6. Copy the Sheet ID from the URL into your `.env`

The agent will **auto-create** the `PostQueue` tab with proper column headers on first run.

### Sheet Columns

| Column | Content |
|--------|---------|
| A | Date |
| B | Rank |
| C | Story Title |
| D | Source |
| E | Category |
| F | Composite Score |
| G | Content Type |
| H | Post Content |
| I | Hashtags |
| J | Carousel Slides JSON |
| K | Short Take |
| L | Status (PENDING/POSTED/SKIPPED) |
| M | Scheduled Time |
| N | Posted At |
| O | Source URL |
| P | Notes |

---

## 🔌 Make.com Setup

1. Go to [Make.com](https://make.com/) → Create a new Scenario
2. **Trigger**: Webhooks → Custom Webhook → Copy the URL
3. **Action 1**: LinkedIn → Create a Share / Text Post
   - Use `{{1.post_content}}` as the post body
4. **Action 2** (optional): Google Sheets → Update Row
   - Set Status = `POSTED`, Posted At = `{{now}}`
5. Paste the webhook URL as `MAKE_WEBHOOK_URL` in your `.env`

> **Note:** Make.com free tier gives 1,000 operations/month — plenty for 1 post/day.

---

## 🚀 GitHub Actions Setup

1. Push this repo to GitHub
2. Go to **Settings → Secrets and Variables → Actions**
3. Add these repository secrets:

```
GEMINI_API_KEY
GOOGLE_SHEETS_CREDS    ← paste the full JSON as a single line
GOOGLE_SHEET_ID
MAKE_WEBHOOK_URL
```

4. The workflow runs automatically **Mon–Fri at 8:00 AM IST**
5. To run manually: **Actions → LinkedIn Daily Content Automation → Run workflow**

---

## 📅 Daily Posting Schedule

| Day | Content Type |
|-----|-------------|
| Monday | Carousel — Weekly AI roundup |
| Tuesday | Text post — Hot take / opinion |
| Wednesday | Short take — Quick insight |
| Thursday | Carousel — Tool spotlight |
| Friday | Text post — What I learned this week |

---

## 📝 Generated Content Formats

### Format 1: LinkedIn Text Post
- Scroll-stopping hook → Punchy insights → Personal opinion → Engagement CTA → Hashtags
- Optimised for 1,200–1,800 characters (LinkedIn sweet spot)

### Format 2: Carousel Script (6 Slides)
- Hook → What happened → Why it matters → How to use it → My take → CTA
- With design notes for each slide

### Format 3: Short Take
- 2-line punch — high reach, great for quick engagement

---

## 🛠️ CLI Options

```bash
python main.py [OPTIONS]

Options:
  --dry-run           Skip external API writes (Sheets + Make.com)
  --story-count N     Generate content for N top stories (default: 5)
  -h, --help
```

---

## 💰 Cost Breakdown

| Service | Free Tier | Monthly Usage |
|---------|-----------|--------------|
| GitHub Actions | 2,000 min/month | ~30 min/month |
| Gemini API | 1M tokens/day | ~50K tokens/day |
| Google Sheets | Unlimited | Minimal |
| Make.com | 1,000 ops/month | ~30 ops/month |
| **Total** | **Free** | **₹0** |

---

## 🤝 Contributing

This is a personal brand automation tool. Customise the prompts in `prompts/` to match your voice and niche.

---

*Built with ❤️ using Google Gemini 2.0 Flash*
