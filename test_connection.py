import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_URL = "https://api.monday.com/v2"
API_TOKEN = os.getenv("MONDAY_API_TOKEN")

headers = {
    "Authorization": API_TOKEN,
    "Content-Type": "application/json"
}

query = """
query {
  boards(limit: 10) {
    id
    name
  }
}
"""

response = requests.post(API_URL, json={"query": query}, headers=headers)
print(response.status_code)
print(response.json())