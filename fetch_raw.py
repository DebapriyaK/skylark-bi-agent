import os
import requests
from dotenv import load_dotenv
import json

load_dotenv()

API_URL = "https://api.monday.com/v2"
API_TOKEN = os.getenv("MONDAY_API_TOKEN")

headers = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}

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
                  items {
                    id
                    name
                    column_values {
                      id
                      text
                      value
                    }
                  }
                }
              }
            }
            """
            variables = {"boardId": [board_id]}
        else:
            query = """
            query ($cursor: String!) {
              next_items_page(cursor: $cursor, limit: 50) {
                cursor
                items {
                  id
                  name
                  column_values {
                    id
                    text
                    value
                  }
                }
              }
            }
            """
            variables = {"cursor": cursor}

        response = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers)
        data = response.json()

        if "errors" in data:
            print("ERROR:", data["errors"])
            break

        if cursor is None:
            page = data["data"]["boards"][0]["items_page"]
        else:
            page = data["data"]["next_items_page"]

        items.extend(page["items"])
        cursor = page["cursor"]

        if cursor is None:
            break

    return items

if __name__ == "__main__":
    WORK_ORDERS_BOARD_ID = "5030965244"
    DEALS_BOARD_ID = "5030965668"

    print("Fetching Work Orders...")
    work_orders = fetch_all_items(WORK_ORDERS_BOARD_ID)
    print(f"Got {len(work_orders)} work orders")

    print("Fetching Deals...")
    deals = fetch_all_items(DEALS_BOARD_ID)
    print(f"Got {len(deals)} deals")

    # Save raw output so we can inspect column IDs
    with open("raw_work_orders.json", "w") as f:
        json.dump(work_orders, f, indent=2)

    with open("raw_deals.json", "w") as f:
        json.dump(deals, f, indent=2)

    print("Saved raw_work_orders.json and raw_deals.json")

    # print one sample item from each so we can see the structure
    print("\n--- Sample Work Order item ---")
    print(json.dumps(work_orders[0], indent=2))