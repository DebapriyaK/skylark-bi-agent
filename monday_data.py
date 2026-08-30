import os
import requests
from dotenv import load_dotenv
import re

load_dotenv()

API_URL = "https://api.monday.com/v2"
API_TOKEN = os.getenv("MONDAY_API_TOKEN")
headers = {"Authorization": API_TOKEN, "Content-Type": "application/json"}

WORK_ORDERS_BOARD_ID = "5030965244"
DEALS_BOARD_ID = "5030965668"

WO_COLUMN_MAP = {
    "text_mm6qrxz1": "customer_name_code",
    "text_mm6qa33v": "serial_number",
    "dropdown_mm6qh0w": "nature_of_work",
    "text_mm6qeyzn": "last_executed_month_recurring",
    "color_mm6qgkne": "execution_status",
    "date_mm6qwn0h": "data_delivery_date",
    "date_mm6qxyk7": "date_of_po_loi",
    "dropdown_mm6q5znw": "document_type",
    "date_mm6q7gbz": "probable_start_date",
    "date_mm6q131x": "probable_end_date",
    "text_mm6q67mq": "bd_kam_personnel_code",
    "dropdown_mm6qajnp": "sector",
    "text_mm6qp5en": "type_of_work",
    "dropdown_mm6q3ww6": "skylark_platform_involved",
    "date_mm6q5w4q": "last_invoice_date",
    "text_mm6qgcv5": "latest_invoice_no",
    "numeric_mm6qmdg3": "amount_excl_gst",
    "numeric_mm6qn5y3": "amount_incl_gst",
    "numeric_mm6qhphn": "billed_value_excl_gst",
    "numeric_mm6q9mfd": "billed_value_incl_gst",
    "numeric_mm6qsg66": "collected_amount_incl_gst",
    "numeric_mm6q2b71": "amount_to_be_billed_excl_gst",
    "numeric_mm6qehza": "amount_to_be_billed_incl_gst",
    "numeric_mm6qe2jf": "amount_receivable",
    "color_mm6qktzd": "ar_priority_account",
    "numeric_mm6qpb87": "quantity_by_ops",
    "text_mm6q74tq": "quantities_as_per_po_raw",
    "numeric_mm6q32fe": "quantity_billed_till_date",
    "numeric_mm6qxx5z": "balance_in_quantity",
    "color_mm6q8z2v": "invoice_status",
    "text_mm6q7f4": "expected_billing_month",
    "text_mm6qcv3j": "actual_billing_month",
    "text_mm6q3ygk": "actual_collection_month",
    "color_mm6qxbc5": "wo_status_billed",
    "color_mm6q6ecr": "collection_status",
    "date_mm6qfpc7": "collection_date",
    "color_mm6qpby2": "billing_status",
}

DEAL_COLUMN_MAP = {
    "text_mm6q5yvg": "owner_code",
    "text_mm6qzr7v": "client_code",
    "color_mm6qddzv": "deal_status",
    "date_mm6qdww1": "close_date_actual",
    "color_mm6q4x1e": "closure_probability",
    "numeric_mm6q78be": "masked_deal_value",
    "date_mm6qkwwz": "tentative_close_date",
    "color_mm6q51vg": "deal_stage",
    "text_mm6qekv7": "product_deal",
    "dropdown_mm6qhhpv": "sector_service",
    "date_mm6qqf48": "created_date",
}

WO_NUMERIC_FIELDS = {
    "amount_excl_gst", "amount_incl_gst", "billed_value_excl_gst", "billed_value_incl_gst",
    "collected_amount_incl_gst", "amount_to_be_billed_excl_gst", "amount_to_be_billed_incl_gst",
    "amount_receivable", "quantity_by_ops", "quantity_billed_till_date", "balance_in_quantity"
}
DEAL_NUMERIC_FIELDS = {"masked_deal_value"}


def fetch_all_items(board_id):
    items = []
    cursor = None
    while True:
        if cursor is None:
            query = """
            query ($boardId: [ID!]) {
              boards(ids: $boardId) {
                items_page(limit: 50) {
                  cursor
                  items { id name column_values { id text value } }
                }
              }
            }"""
            variables = {"boardId": [board_id]}
        else:
            query = """
            query ($cursor: String!) {
              next_items_page(cursor: $cursor, limit: 50) {
                cursor
                items { id name column_values { id text value } }
              }
            }"""
            variables = {"cursor": cursor}

        response = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()
        if "errors" in data:
            print("ERROR:", data["errors"])
            break

        page = data["data"]["boards"][0]["items_page"] if cursor is None else data["data"]["next_items_page"]
        items.extend(page["items"])
        cursor = page["cursor"]
        if cursor is None:
            break
    return items


def parse_number(text):
    if text is None or text.strip() == "":
        return None
    cleaned = text.strip()
    if cleaned.upper() in ("#VALUE!", "#N/A", "N/A", "NA", "-"):
        return None
    try:
        return float(cleaned.replace(",", ""))
    except ValueError:
        return None


def parse_quantity_with_unit(text):
    if text is None or text.strip() == "":
        return None, None
    match = re.match(r'^([\d,\.]+)\s*([A-Za-z]+)?$', text.strip())
    if not match:
        return None, None
    num_part, unit_part = match.groups()
    try:
        return float(num_part.replace(",", "")), unit_part
    except ValueError:
        return None, unit_part


def clean_item(raw_item, column_map, numeric_fields, quantity_field=None):
    cv_by_id = {cv["id"]: cv["text"] for cv in raw_item["column_values"]}
    clean = {"item_id": raw_item["id"], "name": raw_item["name"]}

    for col_id, field_name in column_map.items():
        raw_text = cv_by_id.get(col_id)
        if quantity_field and field_name == quantity_field:
            qty_val, qty_unit = parse_quantity_with_unit(raw_text)
            clean["quantities_as_per_po_value"] = qty_val
            clean["quantities_as_per_po_unit"] = qty_unit
            continue
        if field_name in numeric_fields:
            clean[field_name] = parse_number(raw_text)
        else:
            clean[field_name] = raw_text if raw_text not in (None, "") else None

    return clean


def load_live_data():
    """Fetches and cleans fresh data directly from monday.com. Call this any time current data is needed."""
    raw_wo = fetch_all_items(WORK_ORDERS_BOARD_ID)
    clean_wo = [clean_item(i, WO_COLUMN_MAP, WO_NUMERIC_FIELDS, quantity_field="quantities_as_per_po_raw") for i in raw_wo]

    raw_deals = fetch_all_items(DEALS_BOARD_ID)
    clean_deals = [clean_item(i, DEAL_COLUMN_MAP, DEAL_NUMERIC_FIELDS) for i in raw_deals]

    return clean_wo, clean_deals