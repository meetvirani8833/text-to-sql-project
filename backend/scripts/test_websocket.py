import asyncio
import json
import websockets

async def test_ws():
    uri = "ws://localhost:8000/ws/chat/default_project"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as ws:
            print("Connected! Starting tests...\n")
            
            # ---------------------------------------------------------
            # TEST 1: No Entities (Regression)
            # ---------------------------------------------------------
            print("--- TEST 1: 'How many courses are there?' ---")
            await ws.send(json.dumps({
                "type": "question", 
                "content": "How many courses are there?"
            }))
            
            while True:
                msg_str = await ws.recv()
                msg = json.loads(msg_str)
                type_ = msg.get("type")
                
                print(f"[{type_.upper()}] {msg.get('node', '')} {msg.get('content', '')}")
                
                if type_ in ("answer", "error"):
                    print("Test 1 Completed.\n")
                    break
                    
            await asyncio.sleep(2)
            
            # ---------------------------------------------------------
            # TEST 2: Unambiguous Entity (Auto-Resolve)
            # ---------------------------------------------------------
            print("--- TEST 2: 'Show courses offered by Computer Science and Engineering department' ---")
            await ws.send(json.dumps({
                "type": "question", 
                "content": "Show courses offered by Computer Science and Engineering department"
            }))
            
            while True:
                msg_str = await ws.recv()
                msg = json.loads(msg_str)
                type_ = msg.get("type")
                
                if type_ == "status":
                    print(f"[STATUS] {msg.get('node')}")
                elif type_ == "clarification":
                    print(f"[CLARIFICATION] Unexpected clarification needed!")
                    break
                else:
                    print(f"[{type_.upper()}] {msg.get('content', '')}")
                
                if type_ in ("answer", "error"):
                    print("Test 2 Completed.\n")
                    break
                    
            await asyncio.sleep(2)

            # ---------------------------------------------------------
            # TEST 3: Ambiguous Entity (Requires Clarification)
            # ---------------------------------------------------------
            print("--- TEST 3: 'show computer science details for engineering' ---")
            await ws.send(json.dumps({
                "type": "question", 
                "content": "show computer science details for engineering"
            }))
            
            while True:
                msg_str = await ws.recv()
                msg = json.loads(msg_str)
                type_ = msg.get("type")
                
                if type_ == "status":
                    print(f"[STATUS] {msg.get('node')}")
                    
                elif type_ == "clarification":
                    print(f"\n[CLARIFICATION REQUIRED] {msg['message']}")
                    opts = msg.get("options", [])
                    for i, opt in enumerate(opts):
                        print(f"  [{i}] {opt}")
                        
                    # Auto-reply with option 0 for the test
                    print("--> Auto-replying with Option 0...")
                    await ws.send(json.dumps({
                        "type": "clarification_response",
                        "thread_id": msg["thread_id"],
                        "selection": 0
                    }))
                    
                else:
                    print(f"[{type_.upper()}] {msg.get('content', '')}")
                
                if type_ in ("answer", "error"):
                    print("Test 3 Completed.\n")
                    break

    except Exception as e:
        print(f"Connection failed: {e}. Is Uvicorn running?")

if __name__ == "__main__":
    asyncio.run(test_ws())
