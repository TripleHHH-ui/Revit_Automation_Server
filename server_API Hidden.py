from fastapi import FastAPI
import subprocess
import json
import os
import time
import requests

app = FastAPI()

JSON_PATH = "export_levels.json"
BAT_PATH = "run_dynamo_export.bat"

@app.get("/")
def home():
    return {"status": "Revit Automation Server running"}

@app.get("/run-export")
def run_export():
    # Run Dynamo export
    try:
        subprocess.run(BAT_PATH, shell=True, check=True)
    except Exception as e:
        return {"status": "error", "message": str(e)}

    # Wait for JSON to update
    time.sleep(2)

    if not os.path.exists(JSON_PATH):
        return {"status": "error", "message": "levels.json not found"}

    with open(JSON_PATH, "r") as f:
        levels = json.load(f)

    # Fix Dynamo double-list (Dynamo outputs [[...]])
    if isinstance(levels, list) and len(levels) == 1 and isinstance(levels[0], list):
        levels = levels[0]

    return {"status": "success", "levels": levels}


# ---------- Notion API Setup ----------
NOTION_API_KEY = "ntn_XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
NOTION_DATABASE_ID = "XXXXXXXXXXXXXXXX"  # Replace with your Notion database ID

@app.post("/send-to-notion")
def send_to_notion(data: dict):
    headers = {
        "Authorization": f"Bearer {NOTION_API_KEY}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json"
    }

    results = []

    for lvl in data["levels"]:
        payload = {
            "parent": {"database_id": NOTION_DATABASE_ID},
            "properties": {
                "Level Name": {
                    "title": [{"text": {"content": lvl["name"]}}]
                },
                "Elevation (mm)": {
                    "number": lvl["elevation"]
                },
                "Revit ID": {
                    "number": lvl["id"]
                }
            }
        }

        res = requests.post(
            "https://api.notion.com/v1/pages",
            headers=headers,
            json=payload
        )

        results.append({
            "name": lvl["name"],
            "status": res.status_code,
            "response": res.text
        })

    return {"status": "completed", "results": results}
