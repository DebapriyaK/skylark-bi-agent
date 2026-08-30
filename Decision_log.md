# 2. Decision Log

## 1. Key Assumptions

### Pipeline definition
I interpreted **"pipeline" as open deals only**. Including closed deals would make the metric less useful for understanding current sales opportunity. This definition is enforced in the analytics layer rather than relying only on the LLM's interpretation.

### Source of truth
monday.com is treated as the operational source of truth for Deals and Work Orders. The application therefore fetches the live boards and normalizes their fields before analysis.

### Financial interpretation
Deal and Work Order monetary fields are assumed to represent **INR values**. Missing financial values are treated as missing rather than zero.

### Date interpretation
For pipeline-period questions, I use the **tentative close date**. For work-order timing, I use the **probable start date**. This gives the agent a consistent interpretation of time-based questions.

### Cross-board relationships
There is no reliable shared identifier between Deals and Work Orders. I therefore assume that customer/name, sector, and date proximity can provide useful *candidate matches*, but these cannot be treated as guaranteed relationships. The system exposes match confidence rather than hiding this limitation.

### Missing data
I assume missing fields are potentially meaningful. In particular, a missing close date should not cause a deal to silently disappear from a period-based analysis.

---

## 2. Trade-offs Chosen and Why

### Structured tools instead of unrestricted SQL generation

I chose an **LLM + deterministic business tools** architecture rather than asking the LLM to generate arbitrary SQL.

**Why:** The current data source is monday.com, and the required analytics are relatively well-defined. Structured tools provide tighter control over filters, calculations, and business definitions while reducing the chance of hallucinated numbers.

**Trade-off:** The system is less flexible than a general natural-language-to-SQL system. New analytical capabilities may require extending the tool layer.

---

### Live monday.com data instead of introducing a warehouse

The application directly queries monday.com rather than building an ETL pipeline and analytical database.

**Why:** This keeps the prototype small, easy to deploy, and close to the source of truth. It also avoids spending most of the implementation effort on infrastructure rather than the agent itself.

**Trade-off:** API latency, rate limits, and dataset size will become concerns at production scale.

---

### Heuristic matching instead of ignoring cross-board questions

For questions such as *"Which deals converted into work orders?"*, I chose to provide probabilistic matching rather than remove the capability entirely.

**Why:** Cross-board insights are valuable, even with imperfect source data.

**Trade-off:** The result is not equivalent to a relational join. Confidence and ambiguity must be surfaced to avoid false certainty.

---

### Explicit data-quality handling

I deliberately added data-quality checks rather than assuming the underlying data is clean.

For example, a query for pipeline in a specific quarter can return zero dated deals even though many open deals exist without a tentative close date.

**Why:** A technically correct filter can still produce a misleading business conclusion.

The agent therefore distinguishes **"no records found"** from **"records exist but cannot be dated."**

---

### Small, focused tool surface

I exposed a limited set of business operations rather than giving the model broad access to arbitrary Python functionality.

**Why:** Fewer tools make tool selection more predictable and make business logic easier to test and audit.

**Trade-off:** The agent currently supports a defined set of analytical patterns rather than completely open-ended analysis.

---

## 3. What I Would Do Differently With More Time

### 1. Add a proper semantic/metrics layer

I would centralize definitions such as:

- Pipeline
- Forecast pipeline
- Conversion rate
- Receivables
- Collection rate
- Billing rate

This would prevent business definitions from being distributed between prompts and Python functions.

### 2. Introduce a persistent analytical store

For production, I would ingest monday.com data into PostgreSQL, BigQuery, or a similar warehouse.

This would enable:

- Historical analysis
- Faster aggregation
- Reproducible results
- Trend analysis
- More sophisticated querying

The LLM could then operate over a controlled semantic layer rather than directly over the operational API.

### 3. Establish a shared Deal ↔ Work Order ID

This is the highest-value data-model improvement. A stable `deal_id` carried into Work Orders would eliminate heuristic matching and make conversion analysis deterministic.

### 4. Build an evaluation suite

I would create a set of representative leadership questions with expected:

- Tool selection
- Parameters
- Numerical results
- Data-quality caveats

This would allow model/tool changes to be evaluated objectively rather than manually.

### 5. Add visualization and trend analysis

The next version could automatically generate charts for:

- Pipeline by sector
- Pipeline by stage
- Billing vs. collections
- Receivables
- Work-order execution
- Deal-to-project conversion

### 6. Add production controls

Before broader deployment, I would add authentication, role-based access, audit logs, API caching, observability, and explicit data-freshness indicators.

---

## 4. Interpretation of "Leadership Updates"

I interpreted **"leadership updates" as concise, decision-oriented summaries rather than a generic chatbot response or a detailed operational report.**

A leadership update should answer three questions:

1. **What is happening?**
2. **Why does it matter?**
3. **What should leadership be aware of or act on?**

For example, instead of returning:

> "There are 42 open deals with a total value of ₹X."

the intended style is closer to:

> **"Open pipeline is ₹X across 42 deals, with the largest concentration in Renewables. A significant portion of deals are missing tentative close dates, so the quarterly outlook should be treated cautiously."**

The important design principle is that the agent should **lead with the business signal**, while still providing enough supporting numbers and caveats for the answer to be trusted.

I also interpreted leadership updates as requiring **exception awareness**. If data quality, missing dates, unusual concentration, weak collections, or uncertain deal-to-work-order matching materially affects the conclusion, the agent should surface that rather than presenting a falsely precise answer.

In short:

> **Leadership update = current business signal + key metric + material caveat/implication**, expressed concisely and without unnecessary implementation detail.