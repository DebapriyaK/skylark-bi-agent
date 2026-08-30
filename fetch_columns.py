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

def fetch_columns(board_id):
    query = """
    query ($boardId: [ID!]) {
      boards(ids: $boardId) {
        columns {
          id
          title
          type
        }
      }
    }
    """
    variables = {"boardId": [board_id]}
    response = requests.post(API_URL, json={"query": query, "variables": variables}, headers=headers)
    data = response.json()
    return data["data"]["boards"][0]["columns"]

if __name__ == "__main__":
    WORK_ORDERS_BOARD_ID = "5030965244"
    DEALS_BOARD_ID = "5030965668"

    print("--- Work Orders columns ---")
    wo_cols = fetch_columns(WORK_ORDERS_BOARD_ID)
    for c in wo_cols:
        print(c)

    print("\n--- Deals columns ---")
    deal_cols = fetch_columns(DEALS_BOARD_ID)
    for c in deal_cols:
        print(c)

    with open("wo_columns.json", "w") as f:
        json.dump(wo_cols, f, indent=2)
    with open("deal_columns.json", "w") as f:
        json.dump(deal_cols, f, indent=2)