import os
import json
from openai import OpenAI, BadRequestError
from dotenv import load_dotenv
from monday_data import load_live_data
import query_functions
from query_functions import (
    get_deals, get_work_orders, get_deals_with_date_exclusion_note,
    get_deal_summary_stats, get_work_order_summary_stats,
    assess_data_quality, match_work_order_to_deal
)

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

MODEL = "gpt-4o-mini"  # switch to "gpt-4o" for stronger reasoning if needed

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_deals",
            "description": "Fetch deals from the sales pipeline, optionally filtered by sector, status, stage, or close date range. Use this whenever the question involves sales, pipeline, deals, or revenue prospects, and time period is NOT a concern.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": ["string", "null"], "description": "e.g. Mining, Renewables, Railways, Powerline, Construction, Others"},
                    "deal_status": {"type": ["string", "null"], "description": "e.g. Open, Won, Dead, On Hold"},
                    "deal_stage": {"type": ["string", "null"], "description": "partial match on deal stage name, e.g. 'Negotiations'"},
                    "close_after": {"type": ["string", "null"], "description": "YYYY-MM-DD, filters tentative_close_date >= this"},
                    "close_before": {"type": ["string", "null"], "description": "YYYY-MM-DD, filters tentative_close_date <= this"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deals_with_date_exclusion_note",
            "description": "Use this INSTEAD of get_deals/get_deal_summary_stats whenever the user asks about a specific time period (e.g. 'this quarter', 'this month', 'this year'). It reports how many deals were excluded from the date-filtered result purely because they have no tentative_close_date set — this prevents falsely reporting 'no pipeline' when the real issue is missing date data rather than deals genuinely falling outside the period.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": ["string", "null"]},
                    "deal_status": {"type": ["string", "null"]},
                    "close_after": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "close_before": {"type": ["string", "null"], "description": "YYYY-MM-DD"}
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
                    "sector": {"type": ["string", "null"]},
                    "execution_status": {"type": ["string", "null"], "description": "e.g. Completed, Ongoing, Not Started, Pause / struck"},
                    "start_after": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "start_before": {"type": ["string", "null"], "description": "YYYY-MM-DD"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_deal_summary_stats",
            "description": "Aggregate stats over deals matching the given filters: total value, status/stage/probability breakdowns. IMPORTANT: set pipeline_view=true whenever the user asks about 'pipeline' specifically (Open deals only). Do NOT use this when the user asks about a specific time period AND the result could be zero/low — use get_deals_with_date_exclusion_note instead in that case.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": ["string", "null"], "description": "filter by sector, optional"},
                    "deal_status": {"type": ["string", "null"], "description": "filter by status, optional"},
                    "pipeline_view": {"type": "boolean", "description": "true = Open deals only (pipeline convention), false = all statuses"},
                    "close_after": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                    "close_before": {"type": ["string", "null"], "description": "YYYY-MM-DD"}
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
                    "sector": {"type": ["string", "null"]},
                    "execution_status": {"type": ["string", "null"]}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assess_data_quality",
            "description": "ALWAYS call this alongside any aggregate/summary answer, scoped with the SAME filters (including status) as the answer you're giving — otherwise the completeness stats won't match the population you're actually describing. Valid field names for dataset='deals': masked_deal_value, closure_probability, close_date_actual, tentative_close_date, deal_stage, deal_status. Valid field names for dataset='work_orders': amount_excl_gst, amount_incl_gst, amount_receivable, billed_value_incl_gst, collected_amount_incl_gst, execution_status. Do NOT use any field name outside these lists — they will not exist and will falsely show as 0% complete.",
            "parameters": {
                "type": "object",
                "properties": {
                    "dataset": {"type": "string", "enum": ["deals", "work_orders"]},
                    "sector": {"type": ["string", "null"]},
                    "deal_status": {"type": ["string", "null"], "description": "only used when dataset='deals' — match this to the status you filtered on in your actual answer, e.g. 'Open'"},
                    "execution_status": {"type": ["string", "null"], "description": "only used when dataset='work_orders'"},
                    "fields": {"type": "array", "items": {"type": "string"}, "description": "Must be exact field names from the valid list in the description above."}
                },
                "required": ["dataset", "fields"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_cross_board_summary",
            "description": "Use this ONLY when the question genuinely requires connecting a deal to its resulting work order(s) (e.g. 'which deals actually turned into completed projects'). Returns match confidence for every link — always mention confidence/ambiguity in your answer, never state a cross-board link as fact if confidence is low.",
            "parameters": {
                "type": "object",
                "properties": {
                    "sector": {"type": ["string", "null"], "description": "optional sector filter on work orders to match"}
                }
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "refresh_data",
            "description": "Re-fetches the latest data live from monday.com. Use this if the user asks for 'latest', 'current', 'up to date', or 'refresh' data, or mentions they just made a change on monday.com.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
]

VALID_TOOL_NAMES = {t["function"]["name"] for t in TOOLS}


def execute_tool(name, tool_input):
    tool_input = {k: v for k, v in tool_input.items() if v is not None}

    if name == "get_deals":
        results = get_deals(**tool_input)
        return {"count": len(results), "deals": results}

    elif name == "get_deals_with_date_exclusion_note":
        return get_deals_with_date_exclusion_note(**tool_input)

    elif name == "get_work_orders":
        results = get_work_orders(**tool_input)
        return {"count": len(results), "work_orders": results}

    elif name == "get_deal_summary_stats":
        filtered = get_deals(
            sector=tool_input.get("sector"),
            deal_status=tool_input.get("deal_status"),
            close_after=tool_input.get("close_after"),
            close_before=tool_input.get("close_before")
        )
        return get_deal_summary_stats(filtered, pipeline_view=tool_input.get("pipeline_view", False))

    elif name == "get_work_order_summary_stats":
        filtered = get_work_orders(sector=tool_input.get("sector"), execution_status=tool_input.get("execution_status"))
        return get_work_order_summary_stats(filtered)

    elif name == "assess_data_quality":
        dataset = tool_input["dataset"]
        fields = tool_input["fields"]
        sector = tool_input.get("sector")
        if dataset == "deals":
            records = get_deals(sector=sector, deal_status=tool_input.get("deal_status"))
        else:
            records = get_work_orders(sector=sector, execution_status=tool_input.get("execution_status"))
        return assess_data_quality(records, fields)

    elif name == "get_cross_board_summary":
        sector = tool_input.get("sector")
        wos = get_work_orders(sector=sector) if sector else query_functions.WORK_ORDERS
        matches = [match_work_order_to_deal(w) for w in wos if w["name"] in set(d["name"] for d in query_functions.DEALS)]
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

    elif name == "refresh_data":
        query_functions.WORK_ORDERS, query_functions.DEALS = load_live_data()
        return {
            "status": "refreshed",
            "work_orders_count": len(query_functions.WORK_ORDERS),
            "deals_count": len(query_functions.DEALS)
        }

    else:
        return {"error": f"Unknown tool '{name}'. Valid tools are: {sorted(VALID_TOOL_NAMES)}"}


SYSTEM_PROMPT = """You are a business intelligence assistant for Skylark Drones' founders/executives. 
You answer questions by querying two monday.com boards: Deals (sales pipeline) and Work Orders (project execution).
Data is fetched live from monday.com — it is not hardcoded or cached from a file.

Rules you must follow:
1. This data is real-world messy: many fields are missing/null. NEVER silently ignore this. When giving any aggregate number (totals, averages, counts), also call assess_data_quality using ONLY the exact valid field names listed in that tool's description, and mention the completeness of the key fields involved if it's below ~80%.
2. "Pipeline" specifically means Open deals only (standard sales convention) — use pipeline_view=true for get_deal_summary_stats when asked about pipeline. If asked about deal history/performance broadly, use pipeline_view=false and say so.
3. There is NO reliable shared ID between the Deals and Work Orders boards. If a question requires connecting the two, use get_cross_board_summary and clearly state the match confidence breakdown — never assert a cross-board fact as certain.
4. If a question is ambiguous (e.g. unclear time period, unclear sector name that doesn't exist in the data), ask a clarifying question rather than guessing.
5. Give context and insight, not just raw numbers — but keep answers concise and founder-friendly, not walls of JSON.
6. If a sector/status the user names doesn't exist in the data, say so and suggest the closest real values rather than silently returning empty results.
7. If asked for the latest/current/refreshed data, call refresh_data first before answering.
8. All monetary values in this data are in Indian Rupees (₹), NOT dollars. Always use ₹ and never $ when reporting amounts.
9. When the user asks about a specific time period (e.g. "this quarter", "this month"), use get_deals_with_date_exclusion_note instead of get_deal_summary_stats. If the result is zero or very low, explicitly tell the user how many deals were excluded because their close date is simply unknown, versus genuinely confirmed outside the period. Never present "0 results" from a date filter as equivalent to "no pipeline" without this distinction.
10. If you're not sure of exact quarter/period date boundaries, state the date range you used in your answer so the user can verify it's what they meant.
11. When calling assess_data_quality, always match its filters (sector, deal_status/execution_status) to the exact same population you are reporting numbers for. A data quality caveat about a broader or different group than the one in your answer is misleading — if get_deals_with_date_exclusion_note or another tool already told you the exact completeness of the relevant subset, trust and use that instead of a mismatched assess_data_quality call.
12. The only available tools are: get_deals, get_deals_with_date_exclusion_note, get_work_orders, get_deal_summary_stats, get_work_order_summary_stats, assess_data_quality, get_cross_board_summary, refresh_data. Do not invent or guess tool names outside this exact list.
13. For calculations, prefer readable plain text such as "Win rate = 165 / 346 x 100 = 47.7%". If you use display math, use valid LaTeX that can be rendered by Streamlit.
"""


def chat(user_message, conversation_history=None):
    if conversation_history is None:
        conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]

    conversation_history.append({"role": "user", "content": user_message})

    max_retries = 2
    retries = 0

    while True:
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=conversation_history,
                tools=TOOLS,
                max_tokens=2000
            )
        except BadRequestError as e:
            retries += 1
            if retries > max_retries:
                fallback = "I ran into a repeated tool error trying to answer that. Could you rephrase your question?"
                conversation_history.append({"role": "assistant", "content": fallback})
                return fallback, conversation_history

            conversation_history.append({
                "role": "user",
                "content": f"(System note: your previous tool call used an invalid tool name. The only valid tools are: {sorted(VALID_TOOL_NAMES)}. Please retry using one of these exact names.)"
            })
            continue

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
    print("Skylark BI Agent (OpenAI gpt-4o-mini) — live monday.com data — type 'quit' to exit\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() == "quit":
            break
        answer, history = chat(user_input, history)
        print(f"\nAgent: {answer}\n")
