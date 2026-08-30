# Skylark Drones — AI Business Intelligence Agent

An AI-powered conversational Business Intelligence agent for Skylark Drones that lets founders and business leaders ask natural-language questions about the company's **sales pipeline, deals, work orders, billing, collections, and operational execution**.

The agent connects an LLM to live data from two monday.com boards and uses structured tools to retrieve, filter, aggregate, and validate business data before generating a concise, founder-friendly response.

---

## 1. Overview

Business teams often have valuable operational data inside project-management systems such as monday.com, but extracting insights still requires manually navigating boards, applying filters, calculating metrics, and reconciling information across different workflows.

This project explores a more natural interface:

> **Ask a business question in plain English and get a data-backed answer.**

For example:

- "What's our current sales pipeline?"
- "How much pipeline do we have in Renewables?"
- "Which deals are expected to close this quarter?"
- "How much have we billed versus collected?"
- "Which work orders are still ongoing?"
- "Which deals converted into completed projects?"
- "How much receivable is outstanding?"
- "What does the current data quality look like?"

The system translates these questions into structured tool calls rather than allowing the LLM to directly manipulate or hallucinate business data.

The current implementation uses **OpenAI's tool/function calling**, a lightweight Python orchestration layer, the **monday.com GraphQL API**, and **Streamlit** for the user interface.

---

# 2. Goals

The primary goals were:

1. Provide a conversational interface to business data.
2. Avoid requiring users to know SQL or monday.com board structures.
3. Keep numerical answers grounded in actual source data.
4. Make missing or incomplete data visible instead of silently ignoring it.
5. Establish explicit definitions for business concepts such as "pipeline."
6. Handle the lack of a reliable shared identifier between Deals and Work Orders.
7. Keep the architecture simple enough to understand, deploy, and iterate quickly.
8. Give executives concise answers rather than exposing raw JSON or implementation details.

---

# 3. High-Level Architecture

```text
                         ┌─────────────────────────┐
                         │        User             │
                         │ Natural-language query  │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │       Streamlit UI      │
                         │       app.py             │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │     Agent Orchestrator  │
                         │       agent.py          │
                         │                         │
                         │ OpenAI model + prompts  │
                         │ + tool definitions      │
                         └────────────┬────────────┘
                                      │
                    ┌─────────────────┼─────────────────┐
                    │                 │                 │
                    ▼                 ▼                 ▼
             ┌────────────┐   ┌────────────┐   ┌──────────────┐
             │ Deal Tools │   │ Work Order │   │ Data Quality │
             │            │   │   Tools    │   │    Tools     │
             └─────┬──────┘   └─────┬──────┘   └──────┬───────┘
                   │                │                 │
                   └────────────────┼─────────────────┘
                                    ▼
                         ┌─────────────────────────┐
                         │   query_functions.py   │
                         │ Filtering / aggregation │
                         │ matching / validation   │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │      monday_data.py     │
                         │                         │
                         │ monday.com GraphQL API  │
                         │ Pagination + cleaning   │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │       monday.com        │
                         │                         │
                         │  Deals Board            │
                         │  Work Orders Board      │
                         └─────────────────────────┘
```

The repository contains the main application, agent orchestration, monday.com integration, query/analytics functions, data snapshots, and configuration files.

---

# 4. Repository Structure

```text
skylark-bi-agent/
│
├── agent.py
│   └── LLM orchestration, system prompt, tool definitions,
│       tool execution, conversation loop
│
├── app.py
│   └── Streamlit chat interface
│
├── monday_data.py
│   └── monday.com GraphQL integration, pagination,
│       column mapping, data cleaning and normalization
│
├── query_functions.py
│   └── Filtering, aggregation, data-quality checks,
│       and cross-board matching
│
├── fetch_columns.py
│   └── Utility for inspecting/fetching monday.com columns
│
├── fetch_raw.py
│   └── Utility for fetching raw monday.com data
│
├── deal_columns.json
│   └── Deal-board column metadata
│
├── wo_columns.json
│   └── Work-order column metadata
│
├── raw_deals.json
│   └── Local/raw deal data snapshot
│
├── raw_work_orders.json
│   └── Local/raw work-order data snapshot
│
├── test_connection.py
│   └── Connectivity/testing utility
│
├── requirements.txt
│   └── Python dependencies
│
└── .gitignore
```

The current dependency set is intentionally small: `streamlit`, `openai`, `python-dotenv`, and `requests`.

---

# 5. Core Design Approach

The central design decision was:

> **The LLM should reason about which business operation is required, but deterministic Python functions should perform the actual data retrieval and calculations.**

This separates two responsibilities:

### LLM responsibilities

The model is responsible for:

- Understanding natural-language questions.
- Identifying whether the question concerns deals, work orders, pipeline, or both.
- Selecting the appropriate tool.
- Supplying filters such as sector, status, and date range.
- Understanding when a special tool is required.
- Explaining the returned data in business-friendly language.
- Highlighting relevant caveats.

### Python responsibilities

The Python layer is responsible for:

- Fetching monday.com data.
- Cleaning and normalizing fields.
- Filtering records.
- Calculating aggregates.
- Assessing data completeness.
- Matching Deals to Work Orders.
- Refreshing live data.
- Enforcing the available tool surface.

This reduces the risk of asking the LLM to perform arithmetic or database-like operations directly.

---

# 6. Data Architecture

The system currently works with two monday.com boards:

## Deals

The Deals board represents the sales pipeline.

Important fields include:

- Owner
- Client
- Deal status
- Actual close date
- Closure probability
- Deal value
- Tentative close date
- Deal stage
- Product/deal type
- Sector/service
- Created date

These fields are mapped from monday.com column IDs into normalized Python field names.

## Work Orders

The Work Orders board represents project execution.

Important fields include:

- Customer
- Serial number
- Nature of work
- Execution status
- PO/LOI date
- Probable start/end dates
- Sector
- Amount
- Billed value
- Collected amount
- Receivables
- Invoice status
- Billing status
- Collection status

The integration explicitly maps monday.com column IDs into business-friendly names before the data reaches the analytics layer.

---

# 7. Live Data Retrieval

The monday.com integration uses the GraphQL API:

```text
https://api.monday.com/v2
```

Data is fetched using board IDs and `items_page`, with cursor-based pagination through `next_items_page`.

The implementation therefore does not assume that a single API response contains the complete board.

The flow is:

```text
monday.com
    │
    ▼
GraphQL API
    │
    ▼
Paginated raw items
    │
    ▼
Column ID → business field mapping
    │
    ▼
Type normalization
    │
    ▼
Clean Python dictionaries
```

Numeric fields are parsed into numbers, while invalid numeric values such as `#VALUE!`, `#N/A`, `N/A`, and `-` are treated as missing values. Quantity fields are separately parsed to preserve their units.

---

# 8. Agent and Tool Architecture

The agent exposes a deliberately constrained set of tools.

## 8.1 `get_deals`

Retrieves deals with optional filters:

- Sector
- Deal status
- Deal stage
- Close-after date
- Close-before date

This is intended for general deal-level questions where a specific time-period data-quality caveat is not required.

---

## 8.2 `get_deals_with_date_exclusion_note`

This is one of the most important design choices in the system.

A naive implementation might execute:

```text
tentative_close_date >= start
AND
tentative_close_date <= end
```

and return zero records.

But zero records can mean two very different things:

1. There genuinely are no deals in the period.
2. Deals exist, but their tentative close date is missing.

The specialized tool distinguishes these cases.

It reports:

- Number of matching deals.
- Total matching value.
- Number of records before date filtering.
- Number excluded because the close date is missing.

This prevents the agent from incorrectly saying:

> "There is no pipeline this quarter."

when the actual data says:

> "No dated deals fall in the quarter, but several deals have no close date, so their timing is unknown."

The implementation explicitly calculates and returns this missing-date population.

---

# 9. Pipeline Definition

The agent explicitly defines:

> **Pipeline = Open deals.**

This is important because "pipeline" could otherwise be interpreted as all historical deals.

When `pipeline_view=true`, the analytics layer filters the working set to deals whose status is `Open` and reports how many closed deals were excluded.

This definition is also encoded into the system prompt so that the LLM consistently applies the same business interpretation.

---

# 10. Work Order Analytics

`get_work_orders` supports filtering by:

- Sector
- Execution status
- Start date range

The work-order summary tool calculates:

- Total work orders
- Total billed value including GST
- Total receivable
- Total collected value
- Execution-status breakdown

These calculations are deterministic Python operations rather than LLM-generated calculations.

---

# 11. Data Quality as a First-Class Concept

One of the biggest challenges with real-world business data is that missing values are normal.

Instead of hiding that problem, the agent explicitly models it.

The `assess_data_quality` function calculates field-level completeness:

```text
completeness =
    non-null records / total records × 100
```

For each requested field it returns:

- Total records
- Non-null count
- Null count
- Completeness percentage

The system prompt instructs the model to perform this check alongside aggregate answers and surface important completeness issues.

This is particularly important for:

- Deal values
- Close dates
- Closure probabilities
- Billing amounts
- Collection amounts
- Execution statuses

---

# 12. Cross-Board Matching

A more difficult analytical problem is answering questions that span both boards.

For example:

> "Which deals actually turned into completed projects?"

Ideally, Deals and Work Orders would share a stable client/deal/project ID.

The current data does not provide a reliable shared ID.

Therefore, the system does **not** pretend that a join is exact.

Instead, it uses a confidence-based matching strategy.

### Matching sequence

1. Match Work Order name to Deal name.
2. Prefer candidates with the same sector.
3. If multiple candidates remain, compare:
   - Work Order PO/LOI date
   - Deal actual close date, or tentative close date
4. Use date proximity to disambiguate.
5. Return a confidence level.

Possible outcomes include:

```text
high
medium
low
ambiguous
no_match
```

The matching implementation deliberately returns ambiguity instead of forcing a false positive.

This is an important principle:

> **When source-system identity is uncertain, uncertainty should be part of the answer.**

---

# 13. Why Confidence Matters

Consider two Deals with the same name:

```text
Deal A
Client X
Sector: Mining
Close: January 10

Deal B
Client X
Sector: Mining
Close: September 20
```

and a Work Order:

```text
Client X
Sector: Mining
PO date: January 18
```

The January deal is a stronger candidate.

However, it is still not equivalent to having a shared database ID.

Therefore the system can say:

> "Likely matched to Deal A with medium confidence."

rather than:

> "This Work Order definitely originated from Deal A."

That distinction makes the resulting BI system considerably safer.

---

# 14. LLM Tool Calling Loop

The core agent loop in `agent.py` follows this pattern:

```text
User question
     │
     ▼
OpenAI model
     │
     ├── No tool required
     │       │
     │       ▼
     │    Final answer
     │
     └── Tool required
             │
             ▼
       Structured tool call
             │
             ▼
       Python execution
             │
             ▼
        Tool result
             │
             ▼
       Back to LLM
             │
             ▼
        Final answer
```

The model can call one or more of the registered tools, and the resulting tool messages are appended to the conversation history before the model is called again.

This creates a lightweight agentic loop without requiring a heavyweight agent framework.

---

# 15. Available Tools

The current tool surface is:

| Tool | Purpose |
|---|---|
| `get_deals` | Query individual deals |
| `get_deals_with_date_exclusion_note` | Time-bounded deal queries with missing-date awareness |
| `get_work_orders` | Query work orders |
| `get_deal_summary_stats` | Deal/pipeline aggregation |
| `get_work_order_summary_stats` | Billing, collection, and execution aggregation |
| `assess_data_quality` | Field-level completeness |
| `get_cross_board_summary` | Deal ↔ Work Order matching |
| `refresh_data` | Re-fetch live monday.com data |

These are the only tools exposed to the model, and the system prompt explicitly instructs the model not to invent other tools.

---

# 16. Refresh Strategy

The application initially loads live monday.com data.

A separate `refresh_data` tool is available when a user asks for:

- Latest data
- Current data
- Refreshed data
- Data after a recent monday.com change

The tool re-fetches both boards and replaces the in-memory datasets.

This is a useful compromise between:

- Always making an external API request for every operation.
- Serving permanently stale cached data.

---

# 17. User Interface

The frontend is intentionally lightweight.

Streamlit provides:

- Chat input
- Conversation history
- Assistant/user message rendering
- Loading state
- Basic Markdown rendering
- LaTeX rendering for calculations

The application maintains both the agent conversation history and display history in `st.session_state`.

The UI intentionally avoids adding a complex dashboard layer because the core problem being solved is **conversational access to business intelligence**, rather than dashboard construction.

---

# 18. AI Tools Used

## OpenAI

The system uses the OpenAI Python client and an OpenAI chat model with function/tool calling.

The current implementation is configured for:

```python
MODEL = "gpt-4o-mini"
```

with the code noting that a stronger model such as `gpt-4o` could be substituted when more reasoning capability is required.

The LLM is primarily used for:

- Intent understanding
- Tool selection
- Parameter generation
- Multi-step reasoning
- Natural-language synthesis

It is **not** treated as the source of truth for the business numbers.

---

## monday.com API

monday.com acts as the operational data source.

The application accesses the boards through the monday.com GraphQL API and performs pagination and normalization before exposing the data to the agent.

---

## Streamlit

Streamlit provides the conversational application layer and keeps deployment relatively simple.

---

# 19. Key Assumptions

The implementation makes several explicit assumptions.

### 19.1 Pipeline semantics

"Pipeline" means **Open deals only**.

### 19.2 Currency

Monetary values are assumed to be in **Indian Rupees (₹)**.

### 19.3 Deal timing

`tentative_close_date` is used for date-based pipeline analysis.

### 19.4 Work-order timing

`probable_start_date` is used for work-order start-date filtering.

### 19.5 Cross-board identity

There is no reliable shared identifier between Deals and Work Orders.

Therefore cross-board relationships are probabilistic rather than authoritative.

### 19.6 Missing values

Missing values are considered meaningful information and should not automatically be interpreted as zero.

### 19.7 User ambiguity

When the question is genuinely ambiguous, the agent should ask for clarification rather than silently choosing an interpretation.

These assumptions are encoded into the agent's system prompt and/or deterministic query functions.

---

# 20. Important Trade-offs

## Simplicity vs. scalability

The architecture is deliberately small:

```text
Streamlit
   +
Python
   +
OpenAI
   +
monday.com
```

This makes the project easy to understand and iterate on.

The trade-off is that it is not yet designed as a horizontally scalable production analytics platform.

---

## Tool calling vs. SQL generation

A common approach to conversational BI is:

```text
Natural language
      ↓
LLM
      ↓
SQL
      ↓
Database
```

This project instead uses:

```text
Natural language
      ↓
LLM
      ↓
Structured business tool
      ↓
Python analytics function
```

### Why?

The data source is monday.com rather than a relational warehouse, and the number of business operations is relatively constrained.

Explicit tools also make business rules easier to encode.

For example:

> "Pipeline means Open deals."

is much easier to guarantee through a dedicated tool than through unrestricted SQL generation.

### Trade-off

The tool approach is safer and easier to control, but it is less flexible.

Adding a new analytical question may require adding a new tool or extending an existing one.

---

# 21. Why Not Give the LLM Raw Data?

Another possible design would be to download all monday.com records and put them directly into the LLM context.

This was intentionally avoided.

Problems with that approach include:

- Context-window pressure
- Higher token costs
- Slower responses
- More opportunities for arithmetic errors
- Greater exposure of unnecessary data
- Less deterministic filtering
- Harder validation

Instead, the LLM receives structured results from narrowly scoped functions.

---

# 22. Challenges Faced

## Challenge 1 — Messy business data

Real operational data is rarely complete.

Fields can contain:

```text
null
""
"N/A"
"#VALUE!"
"-"
```

The data ingestion layer normalizes these values, while the analytics layer separately measures completeness.

---

## Challenge 2 — Misleading zero results

A date filter can produce zero records simply because dates are missing.

This led to the creation of the dedicated date-aware deal query function.

This is arguably one of the most important reliability improvements in the project.

---

## Challenge 3 — Ambiguous definition of "pipeline"

A business user might expect:

```text
Pipeline = all deals
```

while a sales organization usually means:

```text
Pipeline = open opportunities
```

The implementation makes this definition explicit rather than leaving it to the LLM's interpretation.

---

## Challenge 4 — Joining two boards without a shared ID

The lack of a reliable shared identifier makes cross-board analysis inherently uncertain.

Instead of pretending otherwise, the system returns match confidence and ambiguity information.

This is a conscious trade-off between usefulness and correctness.

---

## Challenge 5 — Keeping LLM output concise

Executive users generally don't want:

```json
{
  "total_deals": 123,
  "stage_breakdown": {...}
}
```

They want something like:

> "Current open pipeline is ₹X across Y deals, concentrated primarily in Renewables and Mining. However, Z% of deals are missing tentative close dates."

The system prompt therefore instructs the model to provide context and insight while remaining concise and founder-friendly.

---

# 23. Error Handling

The OpenAI interaction includes retry handling for malformed tool calls.

If the model repeatedly attempts to use an invalid tool name, the agent adds a corrective system note listing the valid tools and retries.

After repeated failures, it returns a user-friendly fallback instead of exposing a raw exception.

This is a simple but useful guardrail for tool-calling reliability.

---

# 24. Security Considerations

Secrets are loaded from environment variables using `python-dotenv`.

The two required secrets are:

```text
OPENAI_API_KEY
MONDAY_API_TOKEN
```

For Streamlit deployment, the application also checks `st.secrets` as a source for these values.

Secrets should never be committed to the repository.

For production deployment, I would additionally recommend:

- Secret-manager integration
- Token rotation
- Least-privilege monday.com credentials
- Authentication around the Streamlit application
- Audit logging
- PII/access-control policies
- Rate limiting
- Per-user authorization

---

# 25. Running Locally

## 1. Clone the repository

```bash
git clone https://github.com/DebapriyaK/skylark-bi-agent.git
cd skylark-bi-agent
```

## 2. Install dependencies

```bash
pip install -r requirements.txt
```

The project currently requires:

```text
streamlit
openai
python-dotenv
requests
```



## 3. Configure environment variables

Create a `.env` file:

```env
OPENAI_API_KEY=your_openai_api_key
MONDAY_API_TOKEN=your_monday_api_token
```

## 4. Run the application

```bash
streamlit run app.py
```

The application will launch the conversational BI interface.

---

# 26. Example Questions

Once running, users can ask questions such as:

### Sales

```text
What is our current pipeline?
```

```text
How much open pipeline do we have in Renewables?
```

```text
Show me deals in Negotiations.
```

```text
What deals are expected to close this quarter?
```

### Operations

```text
How many work orders are ongoing?
```

```text
How much have we billed?
```

```text
How much is currently receivable?
```

```text
What is the execution status by sector?
```

### Cross-functional

```text
Which deals have turned into work orders?
```

```text
Which sectors have strong pipeline but weak execution?
```

```text
Compare our sales pipeline with current project execution.
```

### Data quality

```text
How complete is our deal data?
```

```text
How many pipeline deals are missing close dates?
```

---

# 27. Example Agent Reasoning

For:

> "What's our pipeline this quarter?"

The intended flow is approximately:

```text
1. Identify "pipeline"
        ↓
2. Interpret pipeline as Open deals
        ↓
3. Determine quarter date boundaries
        ↓
4. Use date-aware deal tool
        ↓
5. Calculate matching open-deal value
        ↓
6. Identify deals without tentative close dates
        ↓
7. Assess relevant data completeness
        ↓
8. Explain result + caveats
```

The important point is that the model does not simply generate an answer from its own knowledge.

It orchestrates calls into deterministic business logic.

---

# 28. Current Limitations

The current implementation is intentionally a focused prototype, and several limitations remain.

### 28.1 In-memory data

The application loads board data into Python memory.

For larger datasets, a persistent analytical store would be more appropriate.

### 28.2 Limited analytical vocabulary

The available tools cover common BI questions but do not yet provide arbitrary analytical exploration.

### 28.3 No semantic metrics layer

Business metrics are encoded partly in tool descriptions and prompts rather than in a formal metric-definition layer.

### 28.4 Cross-board joins are heuristic

The absence of a stable shared ID limits the reliability of cross-board analysis.

### 28.5 Limited automated evaluation

The repository does not currently contain a comprehensive benchmark suite for measuring:

- Tool-selection accuracy
- Numerical accuracy
- Hallucination rate
- Data-quality disclosure
- Cross-board matching accuracy
- Response latency

### 28.6 Limited access control

The application assumes the configured monday.com token is authorized to access the relevant data.

### 28.7 No persistent conversation storage

Conversation state is maintained by the Streamlit session rather than a dedicated persistence layer.

---

# 29. Potential Improvements

## 29.1 Introduce a semantic metrics layer

Instead of defining concepts such as pipeline only in prompts, introduce a formal metric registry:

```python
METRICS = {
    "pipeline": {
        "filter": {"deal_status": "Open"},
        "value_field": "masked_deal_value"
    },
    "receivables": {
        "dataset": "work_orders",
        "field": "amount_receivable"
    }
}
```

This would make business definitions easier to audit and change.

---

## 29.2 Move data into an analytical warehouse

For larger-scale usage:

```text
monday.com
     ↓
ETL / ELT
     ↓
PostgreSQL / BigQuery / Snowflake
     ↓
Semantic layer
     ↓
BI Agent
```

This would provide:

- Historical snapshots
- Faster aggregation
- Better scalability
- Reproducibility
- SQL-based analytics
- Time-series analysis

---

## 29.3 Add an evaluation framework

Create a benchmark dataset containing questions such as:

```text
Question
Expected tool
Expected filters
Expected result
Expected caveat
```

Then automatically evaluate:

- Tool selection
- Parameter correctness
- Numerical correctness
- Citation/source grounding
- Data-quality disclosure

This would make model upgrades much safer.

---

## 29.4 Improve cross-board identity

The strongest improvement would be introducing a shared identifier:

```text
deal_id
    ↓
work_order.deal_id
```

Then cross-board queries become deterministic:

```sql
SELECT ...
FROM deals
JOIN work_orders
  ON deals.deal_id = work_orders.deal_id
```

This would eliminate much of the uncertainty currently handled through confidence scoring.

---

## 29.5 Add visualization tools

The next version could allow the agent to generate charts when appropriate:

- Pipeline by sector
- Pipeline by stage
- Billing vs collection
- Receivables aging
- Work-order execution status
- Deal conversion funnel

The LLM could decide when a chart adds value, while Python would generate the actual visualization.

---

## 29.6 Add caching with explicit freshness

A production implementation could introduce:

```text
Live monday.com data
        ↓
Short-lived cache
        ↓
Analytics layer
```

with explicit freshness metadata:

```text
Data refreshed: 2 minutes ago
```

This would reduce API calls while maintaining transparency.

---

## 29.7 Add authentication and authorization

A production version should support:

```text
User
 ↓
Authentication
 ↓
Authorization
 ↓
Agent
 ↓
Filtered data access
```

For example, different users could have different visibility into:

- Sales data
- Financial information
- Customer information
- Operational data

---

## 29.8 Add observability

Every request could record:

```text
User question
↓
Tools selected
↓
Tool parameters
↓
Execution time
↓
Data returned
↓
Model response
↓
Errors
```

This would make it easier to diagnose incorrect answers and monitor production performance.

---

## 29.9 Add human feedback

A simple:

```text
👍 Correct
👎 Incorrect
```

mechanism could capture examples for evaluation and prompt/tool improvements.

---

# 30. Why This Architecture

The architecture intentionally sits between a traditional dashboard and a fully autonomous AI agent.

A traditional dashboard provides:

```text
High reliability
+
Low flexibility
```

A fully autonomous LLM agent provides:

```text
High flexibility
+
Higher risk of incorrect reasoning
```

This project aims for:

```text
Natural-language flexibility
          +
Deterministic data operations
          +
Explicit business rules
          +
Visible uncertainty
```

That balance is especially important for executive BI, where a polished but incorrect number can be more harmful than an obviously incomplete answer.

---

# 31. Design Principles

The implementation follows several principles.

### 1. Data before prose

The model should retrieve the data before answering.

### 2. Deterministic calculations

Totals, counts, filters, and completeness calculations belong in Python.

### 3. Explicit definitions

Business concepts such as "pipeline" should have explicit definitions.

### 4. Missing data is information

A missing date should not silently become "outside the period."

### 5. Uncertainty should be visible

A heuristic cross-board match should never be represented as a guaranteed relationship.

### 6. Small tool surface

Expose only the business operations the agent actually needs.

### 7. Executive-oriented output

Return insights and context, not implementation details.

---

# 32. Summary

This project demonstrates a practical pattern for building a conversational BI system over operational SaaS data.

The core idea is simple:

```text
              Natural-language question
                         │
                         ▼
                   LLM reasoning
                         │
                         ▼
                 Structured tool call
                         │
                         ▼
             Deterministic data operation
                         │
                         ▼
                  Validated result
                         │
                         ▼
               Executive-friendly answer
```

The most important architectural decisions are not the choice of UI or model, but the guardrails around the model:

- deterministic tools,
- explicit metric definitions,
- data-quality checks,
- missing-data awareness,
- confidence-based cross-board matching,
- and live data refresh.

This makes the agent more trustworthy than simply placing raw business data into an LLM context and asking it to "analyze the data."

The current implementation is intentionally lightweight, but the architecture provides a strong foundation for evolving toward a production-grade conversational analytics platform with a semantic metric layer, warehouse-backed analytics, automated evaluation, visualization, authentication, observability, and deterministic entity relationships.

---

## Technology Stack

| Layer | Technology |
|---|---|
| UI | Streamlit |
| Agent orchestration | Python |
| LLM | OpenAI |
| LLM interaction | OpenAI tool/function calling |
| Data source | monday.com |
| API | monday.com GraphQL API |
| HTTP client | Requests |
| Configuration | python-dotenv |
| Analytics | Python |
| Deployment target | Streamlit-compatible environment |

The current repository keeps the dependency footprint intentionally small.

---

## Repository

[GitHub — skylark-bi-agent](https://github.com/DebapriyaK/skylark-bi-agent?utm_source=chatgpt.com)

---

## Author's Note

This project is best viewed as a focused prototype demonstrating how an LLM can act as a **reasoning and orchestration layer over structured business tools**, rather than as the database or analytical engine itself.

The strongest production path would be to preserve the current philosophy—**LLM for intent and orchestration, deterministic systems for data and calculations**—while adding a semantic layer, persistent analytical storage, evaluation infrastructure, authentication, and stronger entity relationships.