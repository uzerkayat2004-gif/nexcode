import asyncio
import builtins
import traceback
from nexcode.app import NexCodeApp

# Mock input to always auto-approve "a"
builtins.input = lambda prompt: "a"

async def main():
    app = NexCodeApp()
    app._tool_registry.permission_manager.mode = "yolo"
    
    print("Testing NexCode agent loop...")
    try:
        result = await app.process_input("Search the web for 'duckduckgo-search Python package' and save its short description to duck_info.txt")
        print("\n--- FINAL RESULT ---")
        print(result)
    except Exception as e:
        print("\n--- ERROR DURING AGENT LOOP ---")
        traceback.print_exc()
    
    print("\n--- TOOL HISTORY ---")
    for msg in app.history.get_api_messages():
        print(f"[{msg['role']}]")
        if msg.get("content"):
            print(msg.get("content"))
        if msg.get("tool_calls"):
            print(msg.get("tool_calls"))

if __name__ == "__main__":
    asyncio.run(main())
