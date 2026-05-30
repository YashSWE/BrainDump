# BrainDump — Product Requirements Document
**Version:** 0.3  
**Product:** User Information Management System (UIMS)  
**Status:** Active

---

## 1. Vision

BrainDump is a **User Information Management System** — a persistent, structured layer of knowledge about a person that any AI assistant can read from and write to via MCP.

The core bet: AI assistants are already running in every conversation. BrainDump turns those conversations into a continuously improving model of the user — their goals, events, finances, relationships, skills, and emotional state — rather than letting that knowledge evaporate after each chat.

**One sentence:** BrainDump is the long-term memory and life-tracking layer that makes any AI assistant feel like it's known you for years.

### Long-term Direction (out of scope now, directionally important)

The end state is not just an MCP backend. BrainDump becomes a **user identity platform** — the Google account equivalent for AI-native apps:

- **Own assistant:** A BrainDump-native chat interface that briefs your day each morning, checks in on your mood, nudges stale goals, and asks follow-up questions. Built by us, owning the full stack (frontend + backend), not just the MCP layer.
- **Third-party integrations:** Apps and services connect to BrainDump. A shopping site doesn't get raw data — it sends a product and BrainDump returns a relevance score based on the user's full context. Privacy is preserved; only derived signals leave BrainDump.
- **Daily briefing contents** (when built): Today's events and deadlines · Pending follow-up questions · Stale goal nudges · Mood/energy check-in · Any offloaded/delegated tasks awaiting update.

---

## 2. Users

**Phase 1 (MVP):** Single-user, local-first. Dogfooding by builder.  
**Phase 2:** Multi-user SaaS — accounts, auth, hosted backend, per-user data isolation.

Build Phase 1 with multi-user in mind. Every query scoped to `user_id` from day one.

---

## 3. The Core Problem BrainDump Solves

| What AI does today | What BrainDump enables |
|---|---|
| Forgets everything after the conversation | Persistent structured user context across all sessions |
| Treats every conversation as a cold start — may miss relevant context that exists but isn't retrieved | Knows the user's full context before the first message |
| Stores raw text if it stores anything at all — leads to repetition and noise | Typed, structured facts: goals, events, finances, skills, relationships |
| Never notices stale or outdated information | Detects past events and stale facts, triggers follow-ups |
| Requires the user to re-explain themselves constantly | One tool call returns a complete, structured user model |

---

## 4. Architecture Overview

### 4.1 The Smart MCP Client Principle

**Key design decision:** The MCP client (the AI assistant) does all the structuring and parsing work. The backend is a clean data store, not an extraction engine.

Instead of:
```
remember("I invested ₹50K in gold last week")
→ backend tries to extract structure from text (expensive, error-prone)
```

We do:
```
# AI parses intent and calls the right structured tool:
add_financial_fact(type="investment", asset="gold", amount=50000, currency="INR", date="2026-05-23")
```

This means:
- MCP tools are **typed and structured** — they reject vague blobs
- The AI assistant (already an LLM) bears the cost of interpretation for free
- The backend receives clean, validated, indexed data with zero extra inference cost
- The `remember` tool still exists for genuinely unstructured notes, but typed tools are always preferred

### 4.2 System Layers

```
┌─────────────────────────────────────────────────────┐
│           AI Assistants (Claude, Gemini, GPT)        │
│              MCP Client / Plugin / Action            │
└─────────────────────┬───────────────────────────────┘
                      │ MCP Protocol (stdio / HTTP+SSE)
┌─────────────────────▼───────────────────────────────┐
│              BrainDump MCP Server                    │
│   Typed tools: add_event, track_goal, remember, …   │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│              BrainDump Backend API (FastAPI)         │
│   Auth · CRUD · Synthesis · Follow-up Engine        │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
    ┌──────▼──────┐           ┌───────▼──────┐
    │  PostgreSQL  │           │   ChromaDB   │
    │  (entities) │           │  (semantic   │
    │             │           │   search)    │
    └─────────────┘           └──────────────┘
```

---

## 5. Data Model

### 5.1 Life Categories

8 fixed domains. Every entity is tagged to one.  
*(Extensible via a custom MCP tool — future, not Phase 1.)*

| # | Category | Examples |
|---|---|---|
| 1 | Career & Professional Growth | Job roles, skills, reputation, impact |
| 2 | Financial | Income, savings, investments, targets |
| 3 | Health & Fitness | Fitness goals, nutrition, sleep, energy |
| 4 | Creative & Side Projects | YouTube, apps, anything built outside work |
| 5 | Learning & Intellect | DSA, ML depth, books, courses |
| 6 | Relationships & Social | Friends, family, romantic life, community |
| 7 | Lifestyle & Experiences | Travel, hobbies, quality of life |
| 8 | Mental & Emotional Wellbeing | Stress, self-awareness, peace of mind |

### 5.2 Entity Types

#### Memory (raw, free-text — the fallback)
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| content | text | The raw information |
| category | enum | One of 8 life categories |
| mood | enum | happy / neutral / stressed / anxious / excited / sad |
| emotion_tags | string[] | ["proud", "worried", "motivated"] |
| importance | int 1–10 | |
| source | string | "claude-desktop", "gemini", "chatgpt", etc. |
| tags | string[] | |
| created_at | timestamp | |

#### Goal
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| title | string | "Run a consistent 5K" |
| category | enum | Life category |
| progress | int 0–100 | Percentage complete |
| milestones | jsonb | [{label, target_date, done}] |
| deadline | date | Optional |
| status | enum | active / paused / completed / abandoned |
| notes | text | |
| created_at | timestamp | |
| updated_at | timestamp | |

#### Event
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| title | string | "Sister's wedding" |
| category | enum | Life category |
| event_date | date | |
| people_involved | string[] | ["sister", "family"] |
| outcome | text | Filled after the event passes |
| follow_up_sent | bool | Has the system asked about this yet? |
| notes | text | |
| created_at | timestamp | |

#### Financial Fact
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| type | enum | investment / expense / income / debt / saving |
| asset | string | "gold", "mutual fund", "salary" |
| amount | decimal | |
| currency | string | Default "INR" |
| transaction_date | date | |
| status | enum | active / sold / settled / pending |
| notes | text | |
| follow_up_sent | bool | |
| created_at | timestamp | |

#### Skill
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| name | string | "PyTorch", "System Design" |
| domain | string | "ML", "Software Engineering" |
| proficiency | enum | beginner / intermediate / advanced / expert |
| actively_using | bool | |
| notes | text | |
| updated_at | timestamp | |

#### Relationship
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| name | string | Person or org name |
| relationship_type | string | "friend", "manager", "sister", "mentor" |
| notes | text | Key facts about this person |
| last_mentioned | timestamp | |
| created_at | timestamp | |

#### Delegated Task (Offloaded Work)

The user's cognitive offloading layer. When a user tells an AI "track whether I post to YouTube every week" or "remind me to check on my gold in 3 months" — that intention is a delegated task. It lives in BrainDump across sessions so it never falls through the cracks.

| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| description | text | "Track whether I post to YouTube every week" |
| category | enum | Life category |
| source | string | Which AI assistant created it |
| status | enum | active / completed / cancelled |
| check_in_date | date | When to surface it back to the user |
| outcome | text | What happened — filled when resolved |
| created_at | timestamp | |
| updated_at | timestamp | |

**Flow:**
1. User tells Claude: *"Keep track of whether I post to YouTube every week"*
2. Claude calls `offload_task(description, category, check_in_date)`
3. BrainDump stores it as a delegated task
4. On `check_in_date`, the follow-up engine surfaces: *"You asked me to track your YouTube posting — it's been 10 days, any update?"*
5. User answers → task resolved or check-in date pushed forward

This is one of BrainDump's core differentiators: **cross-session task delegation**. The user offloads cognitive burden to BrainDump and trusts it will resurface at the right time.

#### Follow-up
| Field | Type | Notes |
|---|---|---|
| id | UUID | |
| user_id | UUID | |
| question | text | "Did you sell the gold you bought in May?" |
| source_entity_type | string | "financial_fact" / "event" / "delegated_task" / etc. |
| source_entity_id | UUID | |
| status | enum | pending / answered / dismissed |
| answer | text | User's response |
| created_at | timestamp | |
| answered_at | timestamp | |

---

## 6. MCP Tools (AI-facing API)

The AI assistant is responsible for choosing the right tool and populating structured fields. The backend validates and stores — it does not interpret.

### Memory & Context

| Tool | Description |
|---|---|
| `remember(content, category, mood, emotion_tags, importance, tags, source)` | Store a free-text memory with emotional context. Use when no typed tool fits. |
| `get_context(purpose?, categories?)` | Returns a structured summary of the user. `purpose` filters what's included ("financial advice" → financials + goals, skips fitness). |
| `recall(query, n)` | Semantic search across all entity types. |

### Goals

| Tool | Description |
|---|---|
| `track_goal(title, category, deadline?, milestones?, notes?)` | Create a new goal. |
| `update_goal(goal_id, progress, notes?)` | Update progress on an existing goal. |
| `list_goals(category?, status?)` | List goals, optionally filtered. |

### Events

| Tool | Description |
|---|---|
| `add_event(title, event_date, category, people?, notes?)` | Log an upcoming or past event. |
| `update_event(event_id, outcome)` | Record the outcome after the event passes. |

### Financial

| Tool | Description |
|---|---|
| `add_financial_fact(type, asset, amount, currency, date, notes?)` | Log an investment, expense, income, debt, or saving. |
| `update_financial_fact(fact_id, status, notes?)` | Update status — e.g. "sold", "settled". |

### Skills & Relationships

| Tool | Description |
|---|---|
| `add_skill(name, domain, proficiency, actively_using?)` | Log or update a skill. |
| `add_relationship(name, relationship_type, notes?)` | Log a person or organisation. |

### Profile

| Tool | Description |
|---|---|
| `get_user_profile()` | Get structured identity fields. |
| `update_user_profile(updates)` | Update profile fields (name, age, location, etc.). |

### Delegated Tasks

| Tool | Description |
|---|---|
| `offload_task(description, category, check_in_date, notes?)` | Delegate a task or intention to BrainDump for cross-session tracking. |
| `update_delegated_task(task_id, status, outcome?)` | Mark a delegated task complete, cancelled, or push its check-in date. |
| `list_delegated_tasks(status?)` | List active or completed delegated tasks. |

### Follow-ups

| Tool | Description |
|---|---|
| `get_pending_followups()` | Returns all pending questions — from stale events, financials, and delegated tasks. AI weaves these naturally into conversation. |
| `answer_followup(followup_id, answer)` | Record the user's answer to a follow-up. |

---

## 7. Follow-up Engine

Runs as a background job. Generates a follow-up question when:

| Trigger | Example question generated |
|---|---|
| Event date has passed and outcome is empty | "Your sister's wedding was in December — how did it go?" |
| Financial fact is 60+ days old and status is still `active` | "You invested ₹50K in gold in May — still holding?" |
| Goal hasn't been updated in 30 days | "You set a goal to run a 5K — any progress?" |
| Delegated task `check_in_date` has arrived | "You asked me to track your YouTube posting — it's been 10 days, any update?" |
| Memory references a future intention | "You mentioned wanting to travel — did that happen?" |

Follow-ups surface in **two places**:
1. **MCP tool** — `get_pending_followups()` so any AI can weave them naturally into conversation
2. **Dashboard** — a "Pending Questions" panel the user can answer directly in the UI

---

## 8. Context Generation (`get_context`)

The most important tool. Returns a structured, human-readable summary of the user, filtered by purpose.

**Example — `get_context(purpose="financial advice")`:**
```
User: Yash Bhandari, 22, AI Engineer at Syngenta (Pune, India)

FINANCIAL SNAPSHOT
- Goal: ₹10Cr before age 30 (deadline: Sept 2033)
- Investments: ₹2.5L stocks/MFs · ₹50K FD · ₹50K gold [active]
- Debt: ₹20K to a friend (0% interest, unsettled)
- Emergency fund: ₹0 of ₹1L target

RELEVANT GOALS
- [Financial] ₹10Cr before 30 — 0% progress
- [Financial] Emergency fund ₹1L — 0% progress
```

Without a `purpose`, all 8 categories are summarised briefly. The output is always plain text — readable by any AI, no parsing required.

---

## 9. Dashboard (Web UI)

Extends the existing FastAPI + HTML frontend.

### Views

| View | What it shows |
|---|---|
| **Overview** | 8 category tiles with item counts and a simple health indicator |
| **Goals** | List view — active / paused / completed, progress bars, deadlines |
| **Events** | Timeline — upcoming and past, with outcome status |
| **Financial** | Table — investments, debts, savings with status badges |
| **Skills** | Grid by domain, proficiency indicators |
| **Relationships** | People and orgs, last mentioned date |
| **Memories** | Existing card grid with mood and emotion badges added |
| **Follow-ups** | Pending questions panel — answer inline |

### Global features
- Semantic search across all entity types
- Category filter across all views
- Add button — manually create any entity type
- Source badge on each item (which AI client wrote it)

---

## 10. Multi-user & Auth (Phase 2)

| Requirement | Detail |
|---|---|
| Auth | Email + password, or Google OAuth. JWT tokens. |
| Data isolation | Every query scoped to `user_id`. Zero cross-user leakage. |
| MCP auth | Each user gets a personal API key. Included in MCP server config. |
| Rate limiting | Per-user write limits to prevent runaway agent loops. |

---

## 11. Tech Stack

| Layer | Choice |
|---|---|
| MCP Server | Python + FastMCP |
| Backend API | FastAPI |
| Database | SQLite → PostgreSQL (Phase 2) + ChromaDB (vectors) |
| Auth (Phase 2) | JWT + bcrypt |
| Embeddings | sentence-transformers all-MiniLM-L6-v2 (local, no API cost) |
| Frontend | Vanilla JS + Tailwind CSS |
| Hosting (Phase 2) | TBD — Railway / Render / VPS |

---

## 12. Build Phases

### Phase 1 — UIMS Core (now)
- [ ] Redesign schema: add `goals`, `events`, `financial_facts`, `skills`, `relationships`, `delegated_tasks`, `followups` tables
- [ ] Redesign MCP server: typed structured tools (add_event, track_goal, add_financial_fact, etc.)
- [ ] `get_context()` with purpose-aware filtering
- [ ] Follow-up engine: background job, detect past events + stale financials
- [ ] Dashboard: Goals view · Events timeline · Financial table · Follow-ups panel
- [ ] Mood and emotion fields on memories

### Phase 2 — Multi-user SaaS
- [ ] PostgreSQL migration
- [ ] Auth: registration, login, JWT, personal API keys
- [ ] MCP server resolves `user_id` from API key
- [ ] Dashboard: login/signup, per-user sessions

### Phase 3 — Intelligence & Integrations
- [ ] Mood/emotion trend visualisation
- [ ] Goal health scoring and stale goal detection
- [ ] Cross-entity insights ("financial stress correlates with job transitions")
- [ ] ChatGPT Actions adapter (OpenAPI spec over same backend)
- [ ] Extensible life categories via MCP tool

### Phase 4 — Platform (long-term)
- [ ] BrainDump-native assistant with daily briefing (own the frontend)
- [ ] Third-party integration API: apps send a product, BrainDump returns a relevance score — raw user data never leaves
- [ ] Mobile app

---

## 13. Open Questions

| Question | Status |
|---|---|
| Hosting provider for Phase 2 | To decide |
| Follow-up question text: LLM-generated or templated? | To discuss |
| Skills: stored data only, or interactive self-assessment in dashboard? | To discuss |
| Mobile app: Phase 4 or never? | To discuss |
