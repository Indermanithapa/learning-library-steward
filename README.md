# The Learning Library

**A living atlas of learning.**

🔗 **Live:** [https://the-learning-library.ai.studio/](https://the-learning-library.ai.studio/)

---

## What This Is

The Learning Library is a curated, research-grounded platform for understanding how humans learn, teach, design, assess, coach, and develop.

It combines three things:

- **An interactive 3D map** of 61 concepts connected by 62 semantic relationships
- **A verified library** of research papers, academic textbooks, and frameworks
- **Practical tools** grounded in cognitive science and instructional design

Every resource in the library passes a six-criterion quality standard. Nothing enters without human review. Wikipedia is not a primary source.

---

## The Vision

The learning field produces thousands of papers, frameworks, and tools every year. No single curator can track it all. But quality matters more than quantity — a library is only as good as what it *excludes*.

This project exists to answer one question:

> *"I don't just want to know what something is. I want to understand why it exists, how it works, where it came from, how it affects people, how it is applied, what experts have learned, and how I can use that knowledge."*

**The goal is not a bigger library. The goal is a better one.**

---

## Architecture

```mermaid
flowchart TB
    subgraph Frontend["🖥️ Frontend — React + Vite + TypeScript"]
        direction TB
        Map["/  ·  Learning Map<br/>3D interactive cosmos"]
        Explore["/explore  ·  Concept Catalog<br/>61 concepts, 5 disciplines"]
        Concept["/c/:slug  ·  Concept Deep-Dive<br/>definition · mechanism · resources"]
        Library["/library  ·  Resource Library<br/>30+ verified resources"]
        Tools["/tools  ·  Toolsuite<br/>Synthesizer · Auditor · Matrix · Directory"]
        About["/about  ·  About Page"]
        Archive["/archive  ·  Retired Resources"]
    end

    subgraph Backend["🗄️ Backend — Supabase"]
        direction TB
        ConceptsDB[("concepts<br/>61 rows")]
        EdgesDB[("concept_edges<br/>62 relationships")]
        ResourcesDB[("resources<br/>30+ approved")]
        ToolsDB[("tools<br/>58 directory entries")]
        ReviewDB[("review_queue<br/>pending candidates")]
    end

    subgraph Agent["🤖 AI Discovery Agent — GitHub Actions"]
        direction TB
        Steward["steward.py<br/>Weekly sweep"]
        TelegramSender["send_to_telegram.py<br/>Notification sender"]
    end

    subgraph External["🌐 External APIs"]
        Exa["Exa API<br/>Research discovery"]
        Gemini["Gemini API<br/>Evaluation & scoring"]
    end

    subgraph Human["📱 Human Review — Telegram"]
        Bot["telegram-steward<br/>Edge Function"]
        Phone["Your Phone<br/>Approve / Reject / Defer"]
    end

    Frontend --> Backend

    Steward --> Exa
    Steward --> Gemini
    Steward --> ReviewDB

    TelegramSender --> ReviewDB
    TelegramSender --> Phone

    Phone --> Bot
    Bot --> ResourcesDB
    Bot --> ReviewDB

    classDef frontend fill:#4338CA,stroke:#6366F1,color:#fff
    classDef backend fill:#0F766E,stroke:#14B8A6,color:#fff
    classDef agent fill:#B45309,stroke:#F59E0B,color:#fff
    classDef external fill:#7C3AED,stroke:#A78BFA,color:#fff
    classDef human fill:#BE185D,stroke:#EC4899,color:#fff

    class Map,Explore,Concept,Library,Tools,About,Archive frontend
    class ConceptsDB,EdgesDB,ResourcesDB,ToolsDB,ReviewDB backend
    class Steward,TelegramSender agent
    class Exa,Gemini external
    class Bot,Phone human
```

---

## The Weekly Pipeline

Every Monday at 09:00 UTC, the entire pipeline runs automatically:

```mermaid
sequenceDiagram
    participant GH as GitHub Actions
    participant Exa as Exa API
    participant Gemini as Gemini API
    participant DB as Supabase
    participant TG as Telegram
    participant You as You (on phone)

    GH->>Exa: Search for recent peer-reviewed papers
    Exa-->>GH: 8 candidate papers
    loop For each candidate
        GH->>Gemini: Evaluate & score (0-10)
        Gemini-->>GH: Scores + summary + reasoning
    end
    GH->>DB: Insert verified candidates to review_queue
    GH->>TG: Send each candidate with action buttons
    TG->>You: 📱 Telegram notification
    You->>TG: Tap ✅ Approve
    TG->>DB: Insert into resources table
    DB-->>You: Resource now live on the site
```

**The principle:** AI triages. Humans decide.

---

## Data Model

```mermaid
erDiagram
    CONCEPTS {
        uuid id PK
        text slug UK
        text name
        int level
        text category
        text parent_slug FK
        text description
        text example
        text use_case
        text icon
    }

    CONCEPT_EDGES {
        uuid id PK
        text source_slug FK
        text target_slug FK
        text relationship
        numeric weight
        text note
    }

    RESOURCES {
        uuid id PK
        text title
        text url
        text author
        text institution
        text year
        text domain
        text_array context
        text_array audience
        text evidence_level
        text content_type
        text_array tags
        text source_status
        text added_by
        timestamptz approved_at
        timestamptz retired_at
        uuid superseded_by FK
    }

    TOOLS {
        uuid id PK
        text name
        text vendor
        text url
        text category
        text pricing_model
        text_array learning_stage
        boolean commercial_flag
    }

    REVIEW_QUEUE {
        uuid id PK
        text title
        text url
        text author
        int authority_score
        int evidence_score
        int relevance_score
        int currency_score
        int uniqueness_score
        text suggested_action
        text status
        timestamptz reviewed_at
    }

    CONCEPTS ||--o{ CONCEPT_EDGES : "source"
    CONCEPTS ||--o{ CONCEPT_EDGES : "target"
    RESOURCES ||--o{ RESOURCES : "superseded_by"
    REVIEW_QUEUE ||--o| RESOURCES : "on approval"
```

---

## The Quality Standard

Every resource must pass six criteria:

| Criterion | What It Means |
|---|---|
| **Authority** | Published by a recognized source |
| **Evidence** | Appropriate to its claims |
| **Relevance** | Fits the library charter |
| **Currency** | Not superseded |
| **Usefulness** | Helps someone learn or teach |
| **Diversity** | Adds a perspective or fills a gap |

### What Gets Included

- Peer-reviewed research and systematic reviews
- Academic textbooks and university publications
- University open educational resources
- Government and public-sector education research
- Professional association publications and standards
- Institutional reports from recognized research organizations
- Expert practitioner articles from recognized voices

### What Gets Excluded

- Wikipedia as a primary source
- Commercial content without independent credibility
- AI-generated content without human authorship
- SEO-optimized blog spam
- Content outside the meta-domain of learning
- Vendor product pages (these go in the Tools directory instead)

---

## The Five-Stage Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Discovered: Exa finds it
    Discovered --> Suggested: Agent evaluates
    Suggested --> Verified: Passes quality criteria
    Verified --> Approved: Human approves
    Approved --> Retired: Superseded or outdated
    Retired --> [*]

    Verified --> Rejected: Human rejects
    Rejected --> [*]
```

Nothing enters the public library without human approval.

---

## Repository Structure

```
learning-library-steward/
├── steward.py                       # Weekly discovery agent
├── send_to_telegram.py              # Telegram notification sender
├── requirements.txt                 # Python dependencies
├── supabase_migration.sql           # Database schema + seed data
├── README.md                        # This file
├── SETUP.md                         # Setup instructions for forks
├── .github/
│   └── workflows/
│       └── weekly-sweep.yml         # GitHub Actions schedule
└── supabase/
    └── functions/
        └── telegram-steward/
            └── index.ts             # Webhook receiver for button taps
```

---

## The Charter

> Don't just collect knowledge. Discover, verify, evaluate, connect, curate, improve.
>
> The goal is not a bigger library. The goal is a better one.

---

## Contributing

This is currently a one-person project. If you'd like to contribute, reach out.

**Contact:** [indermanithapa1@gmail.com](mailto:indermanithapa1@gmail.com)

---

## Setup

See [SETUP.md](./SETUP.md) for full setup instructions if you're forking this project.

---

## Copyright

© 2026 Indermani Thapa. All rights reserved.

This repository is shared publicly for transparency and reference. The content, code, and data are not licensed for redistribution or commercial use without permission.

---

## Contact

**Maintained by** [Indermani Thapa](https://github.com/Indermanithapa)

📧 [indermanithapa1@gmail.com](mailto:indermanithapa1@gmail.com)
🔗 [https://the-learning-library.ai.studio/](https://the-learning-library.ai.studio/)

---

**Understand the landscape. Find the depth.**
