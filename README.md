# Skylark BI Agent

An AI-powered conversational Business Intelligence agent that allows founders and business teams to ask natural-language questions about **sales pipeline, deals, work orders, billing, collections, and execution** using live monday.com data.

Hosted Link: https://skylark-bi-agent-khmfsn8km6mtx4nc2j4xor.streamlit.app/

## Overview

The goal was to build a lightweight BI interface where a user can ask questions such as:

- *What is our current pipeline?*
- *How much open pipeline do we have in Renewables?*
- *How much have we billed and collected?*
- *Which work orders are ongoing?*
- *Which deals converted into projects?*

Instead of asking the LLM to directly calculate business metrics, the system uses the LLM primarily for **intent understanding and tool selection**, while deterministic Python functions handle data retrieval, filtering, aggregation, and validation.

This separation makes numerical answers more reliable and allows business rules and data-quality issues to be handled explicitly.

---

## Architecture

```text
                         User
                          │
                          ▼
                   Streamlit UI
                          │
                          ▼
                OpenAI LLM + Tools
                          │
              ┌───────────┼───────────┐
              ▼           ▼           ▼
          Deal Tools  Work Order   Data Quality
                       Tools          Tools
              │           │           │
              └───────────┼───────────┘
                          ▼
                 Python Analytics
                          │
                          ▼
                 monday.com GraphQL
                    API / Live Data
```

### Main components

- **`app.py`** — Streamlit conversational interface.
- **`agent.py`** — OpenAI model, system prompt, tool definitions, and tool-calling loop.
- **`monday_data.py`** — Fetches and normalizes Deals and Work Orders from monday.com using GraphQL and pagination.
- **`query_functions.py`** — Deterministic filtering, aggregation, data-quality analysis, and cross-board matching.
- **JSON files** — Column metadata and local/raw data snapshots for development and inspection.

The agent exposes a small set of business-oriented tools including deal queries, work-order queries, summary statistics, data-quality checks, cross-board analysis, and data refresh.

---

## Approach

### 1. LLM for reasoning, Python for truth

The LLM determines **what the user is asking** and which structured tool should answer it. Python then performs the actual calculation.

For example:

```text
"What is our pipeline this quarter?"
              ↓
LLM identifies:
Open deals + current quarter
              ↓
Python filters and aggregates
              ↓
Validated result
              ↓
LLM produces concise business explanation
```

This reduces hallucination and arithmetic errors compared with giving the model raw data and asking it to calculate everything itself.

### 2. Explicit business definitions

The system defines **pipeline as open deals** rather than relying on the model to infer the meaning.

Other date and financial fields are also mapped to explicit business concepts, such as tentative close date for pipeline timing and probable start date for work orders.

### 3. Data quality is part of the answer

Missing data can produce misleading BI results. For example, a quarter may appear to have no pipeline simply because deals have no tentative close date.

The agent therefore has a dedicated data-quality function and a date-aware deal query that can distinguish:

> "There are no deals in this period"

from:

> "There are deals, but their close dates are missing."

This is especially important for executive decision-making.

### 4. Cross-board matching

Deals and Work Orders do not have a reliable shared identifier. Rather than pretending there is an exact join, the system uses customer/name, sector, and date proximity to find likely matches and returns a **confidence level**.

This makes uncertainty explicit instead of producing potentially misleading relationships.

---

## Key Assumptions

- **Pipeline = Open deals.**
- Monetary values are treated as **INR**.
- Tentative close date is used for deal timing.
- Probable start date is used for work-order timing.
- Missing values are not automatically interpreted as zero.
- Cross-board Deal ↔ Work Order relationships are heuristic unless a reliable shared identifier exists.
- monday.com is the operational source of truth.

---

## Trade-offs

### Tool calling vs. SQL generation

A traditional conversational BI architecture could translate natural language into SQL. I chose structured tools because the current source is monday.com rather than a relational warehouse, and the required business operations are relatively well-defined.

**Advantages:** stronger control, explicit business rules, easier validation.

**Trade-off:** less flexibility; new analytical capabilities may require additional tools.

### Live API vs. database

The application retrieves live monday.com data rather than introducing a warehouse.

**Advantages:** simple architecture and fresh data.

**Trade-off:** slower queries, API dependency, and limited scalability for larger datasets.

### Heuristic joins vs. ignoring cross-board analysis

Heuristic matching provides useful cross-functional insights despite the lack of a shared ID.

**Trade-off:** matches cannot be treated as authoritative, so confidence and ambiguity must be surfaced.

---

## AI / Technology Used

- **OpenAI** — natural-language reasoning and function/tool calling.
- **monday.com GraphQL API** — live Deals and Work Orders data.
- **Python** — deterministic analytics, normalization, and orchestration.
- **Streamlit** — conversational UI.
- **Requests / python-dotenv** — API access and configuration.

The current implementation uses `gpt-4o-mini` with the option to substitute a stronger model where additional reasoning capability is required.

---

## Challenges

### Messy operational data

monday.com fields can contain empty values or strings such as `N/A`, `#VALUE!`, and `-`. The ingestion layer normalizes these values before analytics are performed.

### Ambiguous business language

Terms such as "pipeline" can have different interpretations. These are encoded as explicit business rules rather than leaving them entirely to the LLM.

### Missing dates

Date filtering can silently exclude undated records. The system specifically reports excluded records with missing dates so that a zero result is not misinterpreted.

### No common identifier

The absence of a reliable Deal/Work Order ID makes joins uncertain. The system therefore uses confidence-based matching instead of claiming exact relationships.

### Reliable executive output

The agent is instructed to return concise, business-friendly insights while still surfacing important caveats and data-quality limitations.

---

## Potential Improvements

For a production version, I would prioritize:

1. **Introduce a semantic metrics layer** so definitions such as pipeline, receivables, and conversion are centrally managed rather than partially encoded in prompts.
2. **Move data into a warehouse** such as PostgreSQL/BigQuery for scalable querying, historical snapshots, and faster analytics.
3. **Add automated evaluation** with benchmark questions and expected results to measure tool-selection and numerical accuracy.
4. **Create a shared Deal/Work Order ID** in the source system to replace heuristic matching.
5. **Add visual analytics** for pipeline by sector/stage, billing vs. collections, execution status, and conversion.
6. **Add authentication, authorization, audit logs, and observability** before exposing sensitive business data to a wider user base.
7. **Add caching and explicit data freshness indicators** to reduce API calls while maintaining transparency.

---

## Summary

The core design principle is:

> **Use the LLM for understanding and orchestration; use deterministic code for business data and calculations.**

This provides a practical middle ground between traditional dashboards and fully autonomous AI agents: users get the flexibility of natural-language BI while important numbers, business rules, missing data, and uncertainty remain grounded in explicit application logic.