# GTM Founder-Led Loop

Full Python implementation of the founder-led GTM loop: content signals → ICP scoring → tier routing → warm outbound → content mining → loop compounds.

Based on the framework by Christian Plascencia (Pipeline.tech).

```
Publish content
      ↓
Capture signal (who engaged, how, ICP fit)
      ↓
Score + route into tiers (Hot / Warm / Nurture)
      ↓
Run warm outbound (email referencing their engagement + DM)
      ↓
Book conversations
      ↓
Mine conversations for content
      ↓
Publish content → loop restarts
```

## Why this works

Content isn't separate from outbound. It's the signal source. When someone comments on your post, you know:
- They're aware of you (no cold start)
- They care about the topic
- Their engagement type tells you how much

That's higher-quality intent than any third-party intent data. The loop builds on itself — conversations generate content ideas, content generates signals, signals generate conversations.

## The tiers

| Tier | Score | Label | Play |
|------|-------|-------|------|
| 1 | 80+ | Hot | Founder sends personally within 24h |
| 2 | 50-79 | Warm | Email sequence + LinkedIn DM |
| 3 | <50 | Nurture | Content retarget only — no cold outreach |

## Setup

```bash
pip install -r requirements.txt
export MINIMAX_API_KEY=your_key
export APOLLO_API_KEY=your_key   # optional, for enrichment
```

## Usage

### Full pipeline (recommended)

```bash
python loop/pipeline.py \
  --input example_data/sample_engagers.csv \
  --post-topic "Why most B2B teams hire SDRs before fixing the system" \
  --sender "Rasul" \
  --sender-title "GTM Engineer"
```

Outputs:
- `enriched_engagers.csv` — enriched with Apollo (if key set)
- `scored_engagers.csv` — scored 0-100, tiered
- `outbound_sequences.csv` — warm email + DM per Tier 1/2 engager

### Phase by phase

```bash
# Phase 01: Ingest + enrich engagers
python loop/01_signal_capture.py \
  --input raw_engagers.csv \
  --post-topic "GTM infrastructure" \
  --output enriched.csv

# Phase 02: Score + route into tiers
python loop/02_score_and_route.py \
  --input enriched.csv \
  --output scored.csv

# Phase 03: Generate warm outbound (MiniMax)
python loop/03_outbound.py \
  --input scored.csv \
  --sender "Rasul" \
  --output outbound.csv

# Phase 04: Mine call notes for content
python loop/04_content_miner.py \
  --input example_data/sample_call_notes.txt
```

## Input format

Phase 01 accepts CSV exports from:
- **PhantomBuster** "LinkedIn Post Likers / Commenters" phantom
- **HeyReach** engager export
- **Manual** CSV with: `full_name, company, title, linkedin_url, engagement_type, post_url`

Supported `engagement_type` values: `like`, `comment`, `share`, `repost`, `dm`, `profile_view`, `connection_request`

## Scoring breakdown

| Signal | Max points |
|--------|-----------|
| Engagement type (comment > share > like) | 30 |
| Job title ICP fit (CRO/VP Sales = max) | 25 |
| Industry fit | 20 |
| Company size fit | 15 |
| Geography | 10 |
| **Total** | **100** |

## Customizing ICP criteria

Edit the constants at the top of `loop/02_score_and_route.py`:

```python
ICP_INDUSTRIES = ["saas", "software", "fintech", ...]
ICP_TITLES = ["vp", "cro", "founder", ...]
ICP_EMPLOYEE_RANGE = (20, 2000)
```

## After conversations: close the loop

```bash
# Mine your call notes for content ideas
python loop/04_content_miner.py \
  --input call_notes.txt \
  --output content_ideas.txt

# Review content_ideas.txt, pick the best post
# Publish → new engagers → restart Phase 01
```

## Stack

- Python (no framework dependencies beyond `requests`)
- MiniMax-Text-01 for email + DM generation
- Apollo API for enrichment (optional)
- Output: CSVs importable into Smartlead, Instantly, HubSpot
