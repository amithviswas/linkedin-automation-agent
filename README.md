# 🤖 LinkedIn Automation Agent

> A fully autonomous AI-powered LinkedIn content engine that researches **150+ global tech & AI news stories** from **65+ sources**, picks the best ones, writes viral LinkedIn posts, and publishes them automatically — **twice daily on weekdays and 3x on weekends**. Total cost: **₹0/month**.

![GitHub Actions](https://img.shields.io/github/actions/workflow/status/amithviswas/linkedin-automation-agent/daily_post.yml?label=Auto%20Post&logo=github)
![Model](https://img.shields.io/badge/AI-Gemini%202.5%20Flash-blue?logo=google)
![Made with Python](https://img.shields.io/badge/Made%20with-Python%203.11-yellow?logo=python)

---

## 🚀 What It Does

Every day, this agent:

1. 🔍 **Researches** 150+ real news stories from 65 global sources (TechCrunch, The Verge, Hacker News, OpenAI Blog, Reddit, and more)
2. 🏆 **Filters** them down to the top 5 most viral, engaging stories using AI scoring
3. ✍️ **Writes** a full LinkedIn post with a scroll-stopping hook, insights, opinion, CTA, and a **📖 Read more** link to the original source
4. 📤 **Posts** directly to your LinkedIn profile via Make.com — fully hands-free

---

## 📅 Automatic Posting Schedule

| Day | Post Times (IST) | Posts Per Day |
|-----|-----------------|--------------|
| Monday – Friday | **8:00 AM** and **6:00 PM** | 2 |
| Saturday – Sunday | **8:00 AM**, **12:00 PM**, and **6:00 PM** | 3 |

**Total: 16 posts per week — all fully automated, zero manual effort.**

---

## 🏗️ How It Works

```
GitHub Actions / Windows Task Scheduler
              │
              ▼
    ┌─────────────────────┐
    │   Research Agent    │  ← Gemini 2.5 Flash + Google Search Grounding
    │  150+ stories from  │    Searches 65 global sources: TechCrunch,
    │   65 global sources │    The Verge, HackerNews, OpenAI Blog, Reddit...
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │   Filtering Agent   │  ← Gemini 2.5 Flash
    │  Picks Top 5 Stories│    Scores by: viral potential, relevance,
    │  from 150+ found    │    engagement, recency, uniqueness
    └─────────┬───────────┘
              │
              ▼
    ┌─────────────────────┐
    │   Content Agent     │  ← Gemini 2.5 Flash (Batch Mode — 1 API call)
    │  Generates post for │    Hook → Insights → Opinion → CTA
    │  the #1 story       │    + 📖 Read more: <source URL>
    └─────────┬───────────┘
              │
         ┌────┴─────┐
         │          │
         ▼          ▼
   Local Storage  Make.com Webhook
   posts_output/  → LinkedIn Profile 🚀
```

---

## 📁 Project Structure

```
linkedin-automation-agent/
├── main.py                        # Orchestrator — run this to trigger everything
├── run_agent.bat                  # Windows Task Scheduler wrapper
├── resend_webhook.py              # Re-fire today's post without re-running agent
├── requirements.txt
├── .env.example                   # Copy to .env and fill in your secrets
│
├── agents/
│   ├── research_agent.py          # Fetches 150+ stories via Gemini + Google Search
│   ├── filtering_agent.py         # Scores & selects the top 5 stories
│   └── content_agent.py           # Generates LinkedIn post (batch mode, 1 API call)
│
├── integrations/
│   ├── make_webhook.py            # Sends the top post to Make.com → LinkedIn
│   └── local_storage.py           # Saves all generated posts locally
│
├── prompts/
│   ├── research_prompt.txt        # Instructs Gemini to research 150+ stories from 65 sources
│   ├── filter_prompt.txt          # Scoring criteria for picking the best stories
│   ├── content_prompt_batch.txt   # Batch post generation prompt (all 5 stories, 1 API call)
│   └── content_prompt.txt         # Fallback single-story prompt
│
├── config/
│   └── settings.py                # Environment variable loader
│
├── utils/
│   ├── logger.py                  # Rich-powered terminal logger
│   └── helpers.py                 # Shared utilities (JSON extractor, date helpers)
│
├── posts_output/                  # Generated posts saved here by date
│   └── YYYY-MM-DD/
│       ├── post_1_text.txt        # Ready-to-post LinkedIn text
│       └── summary.md             # Daily overview of all 5 stories
│
└── .github/
    └── workflows/
        └── daily_post.yml         # GitHub Actions — runs on the full weekly schedule
```

---

## ⚡ Quick Start

### 1. Clone & Install

```bash
git clone https://github.com/amithviswas/linkedin-automation-agent.git
cd linkedin-automation-agent
pip install -r requirements.txt
```

### 2. Set Up Secrets

```bash
cp .env.example .env
# Edit .env and fill in your API keys
```

Required environment variables:

| Variable | How to Get |
|----------|-----------|
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/) → Get API key |
| `MAKE_WEBHOOK_URL` | Make.com → Webhooks → Custom Webhook → Copy URL |
| `GEMINI_MODEL` | Set to `gemini-2.5-flash` |
| `USE_LOCAL_STORAGE` | Set to `true` |

### 3. Test Locally

```bash
# Dry run — no API calls, no posting
python main.py --dry-run

# Full run — researches news and posts to LinkedIn
python main.py

# Generate for fewer stories (faster test)
python main.py --story-count 2
```

### 4. Resend Today's Post (Without Re-Running)

```bash
python resend_webhook.py
```

---

## 🔌 Make.com Setup

1. Go to [Make.com](https://make.com/) → **Create a new Scenario**
2. **Trigger**: Webhooks → Custom Webhook → Copy the URL → paste as `MAKE_WEBHOOK_URL` in `.env`
3. **Action**: LinkedIn → **Create User Text Post**
   - In the text field, use the variable picker to select **`post_content`** (purple bubble)
4. Click **Save** → Toggle the scenario **ON** (blue toggle at bottom left)

> ⚠️ **Important:** The scenario toggle MUST be ON (blue) for posts to go through. If it's off, webhooks queue up but nothing posts.

---

## ☁️ GitHub Actions Setup

1. Push this repo to GitHub
2. Go to **Settings → Secrets and Variables → Actions**
3. Add these repository secrets:

```
GEMINI_API_KEY
MAKE_WEBHOOK_URL
GEMINI_MODEL        ← set value to: gemini-2.5-flash
USE_LOCAL_STORAGE   ← set value to: true
```

4. The workflow runs automatically on the full weekly schedule (Mon–Fri 2x, Sat–Sun 3x)
5. To trigger manually: **Actions → LinkedIn Daily Content Automation → Run workflow**

---

## 🪟 Windows Task Scheduler (Local Fallback)

If GitHub Actions doesn't fire reliably, you can use Windows Task Scheduler as a local fallback:

- **Task 1**: Run `d:\Linkdin\run_agent.bat` — Mon–Fri at **8:00 AM** and **6:00 PM**
- **Task 2**: Run `d:\Linkdin\run_agent.bat` — Sat–Sun at **8:00 AM**, **12:00 PM**, **6:00 PM**

> Note: Tasks run in "Interactive only" mode — the PC must be logged in and unlocked.

---

## 📝 Generated Post Format

Every post follows this proven LinkedIn structure:

```
🔥 [Scroll-stopping hook — surprising stat or bold claim]

[5-6 short, punchy insight sentences — each line = one idea]

[Personal opinion or contrarian take]

[Engagement CTA — a question to spark comments]

Save this post if you found it useful 🔖

📖 Read more: https://source-article-url.com

#AITools #GenAI #FutureOfWork #Technology #Innovation
```

---

## 🌍 Research Coverage — 65 Global Sources

The agent searches **65 sources across 7 categories**:

| Category | Sources |
|----------|---------|
| **Major Tech News** | TechCrunch, The Verge, Wired, Ars Technica, CNET, Engadget, Gizmodo + more |
| **Business & Finance** | CNBC, Bloomberg, Reuters, Forbes, WSJ, Financial Times + more |
| **AI-Specific** | VentureBeat AI, MIT Tech Review, The Batch, The Decoder, Synced Review + more |
| **Official Blogs** | OpenAI, Google DeepMind, Anthropic, Meta AI, Microsoft, Hugging Face, NVIDIA + more |
| **Developer & OSS** | Hacker News top 50, GitHub Trending, Dev.to, Stack Overflow, ProductHunt + more |
| **Reddit** | r/artificial, r/MachineLearning, r/OpenAI, r/LocalLLaMA, r/singularity + more |
| **Newsletters** | TLDR AI, The Rundown AI, Ben's Bites, Stratechery, SemiAnalysis + more |

---

## 💰 Cost Breakdown

| Service | Plan | Monthly Usage | Cost |
|---------|------|--------------|------|
| GitHub Actions | Free | ~150 mins/month | ₹0 |
| Gemini API | Free / Pro | 3 API calls per run | ₹0 |
| Make.com | Free | ~50 ops/month | ₹0 |
| **Total** | | | **₹0/month** |

---

## 🛠️ Efficiency — Batch API Mode

The content agent generates posts for **all 5 stories in a single Gemini API call**:

| Mode | API Calls Per Run |
|------|------------------|
| Old (per-story) | 7 calls (1 research + 1 filter + 5 content) |
| **New (batch)** | **3 calls (1 research + 1 filter + 1 batch content)** |

This means you can run the agent **6x per day** on the free Gemini tier before hitting limits — or virtually unlimited times with a Pro account.

---

## 🤝 Customisation

All prompts are fully customisable in the `prompts/` folder:
- Change **writing style** → edit `content_prompt_batch.txt`
- Change **topics** → edit `research_prompt.txt`
- Change **scoring criteria** → edit `filter_prompt.txt`

---

*Built with ❤️ using Google Gemini 2.5 Flash · Make.com · GitHub Actions*
