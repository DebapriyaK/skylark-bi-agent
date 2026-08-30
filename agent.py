import os
import json
from groq import Groq
from dotenv import load_dotenv
from query_functions import (
    get_deals, get_work_orders,
    get_deal_summary_stats, get_work_order_summary_stats,
    assess_data_quality, match_work_order_to_deal,
    DEALS, WORK_ORDERS
)

load_dotenv()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

MODEL = "openai/gpt-oss-120b"  # strong open-source model, good tool-calling support

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_deals",
            "description": "Fetch deals from the sales pipeline, optionally filtered by sector, status, stage, or close date range. Use this whenever the question involves sales, pipeline, deals, or revenue prospects.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "e.g. Mining, Renewables, Railways, Powerline, Construction, Others"},
                    "deal_status": {"type": "string", "description": "e.g. Open, Won, Dead, On Hold"},
                    "deal_stage": {"type": "string", "description": "partial match on deal stage name, e.g. 'Negotiations'"},
                    "close_after": {"type": "string", "description": "YYYY-MM-DD, filters tentative_close_date >= this"},
                    "close_before": {"type": "string", "description": "YYYY-MM-DD, filters tentative_close_date <= this"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_orders",
            "description": "Fetch work orders (project execution data), optionally filtered by sector, execution status, or start date range. Use this for operational/execution/billing questions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string"},
                    "execution_status": {"type": "string", "description": "e.g. Completed, Ongoing, Not Started, Pause / struck"},
                    "start_after": {"type": "string", "description": "YYYY-MM-DD"},
                    "start_before": {"type": "string", "description": "YYYY-MM-DD"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deal_summary_stats",
            "description": "Aggregate stats over a set of deals: total value, status/stage/probability breakdowns. IMPORTANT: set pipeline_view=true whenever the user asks about 'pipeline' specifically (this correctly scopes to Open deals only, per standard sales convention) rather than all deal history.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "re-filter by sector before aggregating, optional"},
                    "deal_status": {"type": "string", "description": "re-filter by status before aggregating, optional"},
                    "pipeline_view": {"type": "boolean", "description": "true = Open deals only (pipeline convention), false = all statuses"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_work_order_summary_stats",
            "description": "Aggregate stats over work orders: total billed, receivable, collected, execution status breakdown.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string"},
                    "execution_status": {"type": "string"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assess_data_quality",
            "description": "ALWAYS call this alongside any aggregate/summary answer to check how complete the underlying data is, so you can caveat the answer honestly (e.g. 'only 32% of these deals have a recorded value'). Pass the same filters as the stats call.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "enum": ["deals", "work_orders"]},
                    "sector": {"type": "string"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "field names to check completeness for"}
                },
                "required": ["dataset", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "cross_board_summary",
            "description": "Use this ONLY when the question genuinely requires connecting a deal to its resulting work order(s) (e.g. 'which deals actually turned into completed projects'). Returns match confidence for every link — always mention confidence/ambiguity in your answer, never state a cross-board link as fact if confidence is low.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": "string", "description": "optional sector filter on work orders to match"}
                }
            }
        }
    }
]


def execute_tool(name, tool_input):
    if name == "get_deals":
        results = get_deals(**tool_input)
        return {"count": len(results), "deals": results}

    elif name == "get_work_orders":
        results = get_work_orders(**tool_input)
        return {"count": len(results), "work_orders": results}

    elif name == "get_deal_summary_stats":
        sector = tool_input.get("sector")
        deal_status = tool_input.get("deal_status")
        pipeline_view = tool_input.get("pipeline_view", False)
        filtered = get_deals(sector=sector, deal_status=deal_status)
        return get_deal_summary_stats(filtered, pipeline_view=pipeline_view)

    elif name == "get_work_order_summary_stats":
        filtered = get_work_orders(sector=tool_input.get("sector"), execution_status=tool_input.get("execution_status"))
        return get_work_order_summary_stats(filtered)

    elif name == "assess_data_quality":
        dataset = tool_input["dataset"]
        fields = tool_input["fields"]
        sector = tool_input.get("sector")
        records = get_deals(sector=sector) if dataset == "deals" else get_work_orders(sector=sector)
        return assess_data_quality(records, fields)

    elif name == "cross_board_summary":
        sector = tool_input.get("sector")
        wos = get_work_orders(sector=sector) if sector else WORK_ORDERS
        matches = [match_work_order_to_deal(w) for w in wos if w["name"] in set(d["name"] for d in DEALS)]
        high = sum(1 for m in matches if m.get("confidence") == "high")
        medium = sum(1 for m in matches if m.get("confidence") == "medium")
        low_or_ambiguous = sum(1 for m in matches if m["status"] == "ambiguous" or m.get("confidence") == "low")
        return {
            "total_work_orders_checked": len(matches),
            "high_confidence_matches": high,
            "medium_confidence_matches": medium,
            "low_confidence_or_ambiguous": low_or_ambiguous,
            "note": "Cross-board matching uses deal name + sector + PO-to-close-date proximity, since no shared client ID exists between boards. Confidence reflects how strong the evidence is, not certainty."
        }


SYSTEM_PROMPT = """You are a business intelligence assistant for Skylark Drones' founders/executives. 
You answer questions by querying two monday.com boards: Deals (sales pipeline) and Work Orders (project execution).

Rules you must follow:
1. This data is real-world messy: many fields are missing/null. NEVER silently ignore this. When giving any aggregate number (totals, averages, counts), also call assess_data_quality and mention the completeness of the key fields involved if it's below ~80%.
2. "Pipeline" specifically means Open deals only (standard sales convention) — use pipeline_view=true for get_deal_summary_stats when asked about pipeline. If asked about deal history/performance broadly, use pipeline_view=false and say so.
3. There is NO reliable shared ID between the Deals and Work Orders boards. If a question requires connecting the two, use cross_board_summary and clearly state the match confidence breakdown — never assert a cross-board fact as certain.
4. If a question is ambiguous (e.g. unclear time period, unclear sector name that doesn't exist in the data), ask a clarifying question rather than guessing.
5. Give context and insight, not just raw numbers — but keep answers concise and founder-friendly, not walls of JSON.
6. If a sector/status the user names doesn't exist in the data, say so and suggest the closest real values rather than silently returning empty results.
"""


def chat(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversation_history.append({"role": "user", "content": user_message})

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=conversation_history,
            tools=TOOLS,
            max_tokens=2000
        )

        message = response.choices[0].message

        if message.tool_calls:
            conversation_history.append({
                "role": "assistant",
                "content": message.content,
                "tool_calls": [tc.model_dump() for tc in message.tool_calls]
            })

            for tc in message.tool_calls:
                tool_name = tc.function.name
                tool_args = json.loads(tc.function.arguments)
                print(f"  [calling tool: {tool_name}({tool_args})]")
                result = execute_tool(tool_name, tool_args)

                conversation_history.append({
                    "role": "tool",
                    "tool_call_id": tc.id,
                    "content": json.dumps(result, default=str)
                })
        else:
            conversation_history.append({"role": "assistant", "content": message.content})
            return message.content, conversation_history


if __name__ == "__main__":
    history = None
    print("Skylark BI Agent (Groq/Llama 3.3) — type 'quit' to exit\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break
        answer, history = chat(user_input, history)
        print(f"\nAgent: {answer}\n")