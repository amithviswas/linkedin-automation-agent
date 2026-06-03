# LinkedIn Automation Agent
> Build a fully autonomous AI LinkedIn Content Automation System using Google Antigravity 2.0 + Gemini API + GitHub Actions + Make.com

---

## MAIN OBJECTIVE

Create a complete AI-powered LinkedIn automation workflow that functions like a professional personal brand media engine.

The system should:
- Research tech & AI news automatically every day
- Filter the top 5 most valuable and viral updates
- Write premium LinkedIn posts in your personal voice
- Generate carousel slide scripts
- Schedule and automatically publish posts daily
- Track analytics and improve over time

---

## AUTOMATION SCHEDULE

### Daily Workflow

**8:00 AM**
- GitHub Actions triggers the agent
- Start tech & AI news research
- Gather latest updates from all sources
- Analyze viral potential and relevance
- Select top 5 news topics

**8:15 AM**
- Generate LinkedIn post content for all 5 topics
- Write text posts in personal voice
- Write carousel slide scripts
- Generate captions and hashtags

**8:45 AM**
- Save all 5 posts to Google Sheets queue
- Make.com picks up posts from sheet
- Final formatting and prep

**9:00 AM**
- Automatically publish 1 post to LinkedIn
- Remaining 4 posts drip-scheduled across the week
- No manual intervention required

---

## AI RESEARCH AGENT

### Monitor Latest Updates From

**AI Companies**
- OpenAI / ChatGPT
- Google Gemini
- Claude / Anthropic
- DeepSeek
- Meta AI
- Microsoft Copilot
- Perplexity
- Midjourney
- Runway
- ElevenLabs
- Stability AI

**Tech Industry**
- Startups & Funding
- Big Tech (Apple, Google, Microsoft, Amazon, Meta)
- Developer Tools
- SaaS Products
- Indian Tech Ecosystem
- Global Market Trends

**Research Topics**
- AI Agents & Automation
- AI Tools for Productivity
- AI for Business & Startups
- AI Video / Image / Voice Generation
- AI Coding Tools
- Tech Layoffs & Hiring Trends
- Startup Launches
- Developer News
- Indie Hacker Stories
- Future of Work

**Research Sources**
- Official company blogs
- Hacker News
- Product Hunt
- TechCrunch / The Verge / Wired
- X/Twitter AI trends
- Reddit (r/artificial, r/technology, r/MachineLearning)
- AI newsletters (TLDR, The Rundown AI)
- LinkedIn trending posts
- GitHub Trending
- YouTube tech channels

---

## NEWS FILTERING SYSTEM

The AI should filter and select ONLY the top 5 most important updates daily based on:

- Viral potential on LinkedIn
- Usefulness to tech professionals
- Engagement potential (comments, shares, saves)
- Innovation level
- Trending discussions
- Real-world business impact
- Relevance to Indian tech audience
- Creator and developer relevance

### Selected Updates Should Be
- Highly engaging for professionals
- Useful for developers, founders, and creators
- Easy to understand for non-technical audience
- Relevant to career growth and business

---

## LINKEDIN POST GENERATION

For each update, generate **3 content formats**:

### Format 1: Text Post (Primary)
```
Line 1:  Powerful hook headline (curiosity or shock)
Line 2:  Empty line
Lines 3-8: Core insight — short punchy sentences
Line 9:  Empty line
Line 10: Personal opinion angle ("Here's what this means for you...")
Line 11: Empty line
Line 12: Engagement CTA
Line 13: Hashtags
```

### Format 2: Carousel Script (5–7 Slides)

**Slide 1 — Hook**
- Bold headline
- Curiosity-driven subtitle
- Minimal futuristic design

**Slide 2 — What happened?**
- Clear simple explanation
- No jargon

**Slide 3 — Why does it matter?**
- Real-world impact
- Stats or comparisons if available

**Slide 4 — How can YOU benefit?**
- Actionable use cases
- Creator / developer / business angle

**Slide 5 — Your Take**
- Personal opinion
- Contrarian or forward-looking angle

**Slide 6 — CTA**
- Follow prompt
- Save / share prompt
- Comment prompt

### Format 3: Short Take (2-liner)
```
One punchy observation.
One strong opinion or question.
```

---

## DESIGN REQUIREMENTS

### Carousel Visual Style
- Ultra minimal, not over-designed
- Futuristic but clean — think Apple meets Notion
- Dark background with glowing accents OR pure white minimal
- Bold modern typography (Inter, Space Grotesk, or Satoshi)
- High contrast layouts
- Single accent color per post series
- No clutter — every element must earn its place

### Design Principles
- Less is more
- White space is power
- Typography does the heavy lifting
- One visual idea per slide
- Consistent brand identity across all posts

---

## CONTENT WRITING STYLE

### Tone
- Modern and direct
- Conversational but credible
- Exciting without being cringe
- Easy to understand for everyone
- Opinionated — not just news, but a point of view
- Feels like a smart friend explaining something important

### Writing Rules
- Start with a hook that stops the scroll
- Use short sentences — max 15 words per sentence
- No corporate jargon
- Add personal opinion to every post
- Write like you're talking to someone 1-on-1
- Use numbers and specifics over vague claims

### Avoid
- Boring "In today's fast-paced world..." intros
- Long paragraphs
- Passive voice
- Generic motivational content

### Use
- Strong opinionated hooks
- Curiosity gaps
- Contrarian takes
- Real examples and use cases
- "You" language

---

## CAPTION & HASHTAG GENERATION

### LinkedIn Caption Structure
```
[Strong hook — 1 line]

[Core insight — 3-5 short lines]

[Personal opinion or angle — 2 lines]

[Engagement CTA]
[Save/share CTA]
[Comment CTA]

[5-10 relevant hashtags]
```

### Example CTAs
- "Would you use this tool? Drop a comment 👇"
- "Save this — you'll need it later 🔖"
- "Tag a founder who needs to see this"
- "Agree or disagree? Tell me below"
- "Which one is most useful for you? 1, 2, or 3?"

### Hashtag Strategy
- 3-5 niche hashtags (e.g. #AITools #PromptEngineering)
- 2-3 broad hashtags (e.g. #Technology #Innovation)
- 1-2 trending hashtags (pulled from LinkedIn trends)

---

## TECH STACK (100% FREE)

| Layer | Tool | Cost |
|---|---|---|
| Scheduler / Runner | GitHub Actions | Free (2000 min/month) |
| AI Content Generation | Gemini API | Free (1M tokens/day) |
| News Research | Gemini API + Web Search | Free |
| Post Queue Storage | Google Sheets | Free |
| LinkedIn Auto-Posting | Make.com | Free (1000 ops/month) |
| Image Generation Prompts | Gemini API | Free |
| Carousel Design | Canva API / Templates | Free tier |

**Total Monthly Cost: ₹0**

---

## SYSTEM ARCHITECTURE

```
GitHub Actions
(Runs daily at 8:00 AM IST)
        │
        ▼
Research Agent
(Gemini API + Web Search)
Fetches top tech/AI news
        │
        ▼
Filtering Agent
(Selects top 5 stories)
Scores by viral potential
        │
        ▼
Content Generation Agent
(Gemini API)
Writes in your personal voice
→ Text post
→ Carousel script
→ Short take
→ Caption + hashtags
        │
        ▼
Google Sheets
(Post Queue)
Stores all generated content
        │
        ▼
Make.com
(Reads from Google Sheets)
Schedules and posts to LinkedIn
        │
        ▼
LinkedIn Profile
(Auto-published daily)
```

---

## ANALYTICS SYSTEM

### Track Per Post
- Impressions
- Likes
- Comments
- Shares
- Profile visits driven
- Follower growth

### Use Analytics To
- Identify which topics perform best
- Identify which post formats get most engagement
- Improve future content selection
- Double down on winning content styles
- Feed performance data back into the filtering agent

---

## DASHBOARD (Optional Phase 2)

Build a simple web dashboard showing:

- Today's top 5 selected news stories
- Generated post previews
- Caption and hashtag previews
- Posting schedule
- LinkedIn upload status
- Automation logs
- Weekly performance analytics

### Dashboard Feel
- Minimal and clean
- Dark mode first
- Futuristic but functional
- Real-time status updates

---

## POSTING STRATEGY

| Day | Content Type |
|---|---|
| Monday | Carousel — Weekly AI roundup |
| Tuesday | Text post — Hot take / opinion |
| Wednesday | Short take — Quick insight |
| Thursday | Carousel — Tool spotlight |
| Friday | Text post — What I learned this week |

> Consistency beats virality. 5 posts/week for 90 days will transform your profile.

---

## FINAL GOAL

Build a fully autonomous LinkedIn content engine that:

1. Researches tech and AI news every day automatically
2. Filters the most relevant and viral stories
3. Writes posts in YOUR voice — not generic AI content
4. Designs minimal futuristic carousel scripts
5. Schedules and publishes everything automatically
6. Requires zero manual effort after initial setup
7. Grows your 8,500+ connection network into an engaged audience
8. Positions you as a top tech voice on LinkedIn

> **Your LinkedIn profile has 8,500+ connections waiting to hear from you. This system activates that audience — automatically, every single day.**
