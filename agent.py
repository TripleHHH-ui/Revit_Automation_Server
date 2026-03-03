import os
import json
import requests
import anthropic

# ---------- CONFIG ----------
AUTOMATION_SERVER = "http://127.0.0.1:8000"
MODEL_NAME = "claude-sonnet-4-20250514"  # Updated to latest model

print("=" * 60)
print("🚀 REVIT ↔ NOTION CLAUDE AGENT - DEBUG MODE")
print("=" * 60)

# Check API key
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set!")
    print("\nSet it with:")
    print("  Windows CMD:        set ANTHROPIC_API_KEY=sk-ant-...")
    print("  Windows PowerShell: $env:ANTHROPIC_API_KEY='sk-ant-...'")
    print("  Mac/Linux:          export ANTHROPIC_API_KEY=sk-ant-...")
    exit(1)
else:
    print(f"✅ API Key found: {api_key[:20]}...{api_key[-4:]}")

# Check server connectivity
print(f"\n🔍 Testing connection to server: {AUTOMATION_SERVER}")
try:
    response = requests.get(f"{AUTOMATION_SERVER}/", timeout=5)
    if response.status_code == 200:
        print(f"✅ Server is running: {response.json()}")
    else:
        print(f"⚠️  Server responded with status {response.status_code}")
except requests.exceptions.ConnectionError:
    print("❌ ERROR: Cannot connect to FastAPI server!")
    print("   Make sure you've started it with: uvicorn server:app --reload")
    exit(1)
except Exception as e:
    print(f"❌ ERROR connecting to server: {e}")
    exit(1)

client = anthropic.Anthropic(api_key=api_key)
print(f"✅ Claude client initialized with model: {MODEL_NAME}")
print("=" * 60)

# ---------- STEP 1: DEFINE THE TOOL SCHEMA ----------

tools = [
    {
        "name": "sync_revit_levels_to_notion",
        "description": (
            "Export Revit levels using the local Revit Automation Server "
            "and push them to the Notion 'Revit Levels' database. "
            "Use this when the user asks to sync or upload Revit levels to Notion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        },
    }
]


# ---------- STEP 2: IMPLEMENT THE TOOL IN PYTHON ----------

def sync_revit_levels_to_notion():
    """
    1) Call /run-export on the local automation server
    2) Call /send-to-notion with the levels data
    3) Return the server's response
    """
    print("\n[🔧 TOOL] Running sync_revit_levels_to_notion...")
    
    # Step 1: run Dynamo export via FastAPI
    print("  → Calling /run-export...")
    export_resp = requests.get(f"{AUTOMATION_SERVER}/run-export")
    export_resp.raise_for_status()
    export_data = export_resp.json()
    print(f"  ✅ Export complete: {len(export_data.get('levels', []))} levels found")

    # Step 2: send levels into Notion
    print("  → Calling /send-to-notion...")
    notion_resp = requests.post(
        f"{AUTOMATION_SERVER}/send-to-notion",
        json=export_data
    )
    notion_resp.raise_for_status()
    notion_data = notion_resp.json()
    print(f"  ✅ Notion sync complete")

    # Combine info
    return {
        "export": export_data,
        "notion": notion_data,
    }


# Map tool name -> implementation
tool_impls = {
    "sync_revit_levels_to_notion": sync_revit_levels_to_notion,
}


# ---------- CHAT LOOP WITH CLAUDE + TOOL USE ----------

def call_claude(messages):
    """Helper to call Claude with tools."""
    print("\n[🤖 CLAUDE] Sending request to API...")
    response = client.messages.create(
        model=MODEL_NAME,
        max_tokens=1024,
        messages=messages,
        tools=tools,
    )
    print(f"[🤖 CLAUDE] Response received (stop_reason: {response.stop_reason})")
    return response


def main():
    print("\n💬 Chat started. Type your message or 'quit' to exit.\n")

    messages = []

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
            
        if user_input.lower() in {"q", "quit", "exit"}:
            print("\n👋 Goodbye!")
            break

        messages.append({"role": "user", "content": user_input})

        # 1) Ask Claude, giving it our tools
        response = call_claude(messages)
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # 2) Check if Claude wants to use a tool
        tool_uses = [b for b in assistant_content if b.type == "tool_use"]

        if not tool_uses:
            # No tool use, just print Claude's reply text
            text_parts = [b.text for b in assistant_content if b.type == "text"]
            print("Claude:", "\n".join(text_parts))
            print()
            continue

        # 3) For each tool Claude wants to use, run it locally
        for tool_block in tool_uses:
            tool_name = tool_block.name
            tool_id = tool_block.id
            tool_input = tool_block.input

            print(f"\n[🛠️  TOOL USE] Claude wants to use: {tool_name}")

            if tool_name not in tool_impls:
                tool_result = {"error": f"Unknown tool {tool_name}"}
            else:
                try:
                    tool_result = tool_impls[tool_name](**tool_input) if tool_input else tool_impls[tool_name]()
                except Exception as e:
                    print(f"  ❌ Tool execution failed: {e}")
                    tool_result = {"error": str(e)}

            # 4) Send the tool result back to Claude
            print("\n[🤖 CLAUDE] Sending tool result back to Claude...")
            tool_result_message = {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_id,
                        "content": json.dumps(tool_result),
                    }
                ],
            }
            messages.append(tool_result_message)

            # 5) Ask Claude again, now that it has the tool result
            followup = call_claude(messages)
            follow_content = followup.content
            messages.append({"role": "assistant", "content": follow_content})

            text_parts = [b.text for b in follow_content if b.type == "text"]
            print("\nClaude:", "\n".join(text_parts))
            print()


if __name__ == "__main__":
    main()