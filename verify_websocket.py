
import asyncio
import websockets
import json
import httpx
import time

async def verify_websocket():
    uri = "ws://localhost:8002/ws"
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("WebSocket Connected!")
            
            # Trigger a manual fetch to generate data
            print("Triggering manual news fetch via API...")
            async with httpx.AsyncClient(trust_env=False) as client:
                try:
                    # First check if the endpoint exists
                    resp = await client.get("http://localhost:8002/openapi.json", timeout=5.0)
                    print(f"OpenAPI Check: {resp.status_code}")
                    
                    # Trigger the fetch for 2017 data using proven parameters
                    query = "sourcelang:eng"
                    start_date = "20170101000000"
                    end_date = "20170102000000"
                    
                    params = {
                        "query": query, 
                        "max_records": 10,
                        "start_date": start_date,
                        "end_date": end_date
                    }
                    url = "http://localhost:8002/api/debug/fetch-news"
                    print(f"Triggering fetch with params: {params}")
                    resp = await client.post(url, params=params, timeout=120.0)
                    print(f"Trigger Response: {resp.status_code} - {resp.text}")
                except Exception as e:
                    print(f"API Trigger Failed: {e}")
                    return

            print("Waiting for messages...")
            try:
                # Wait for at least one message with a timeout
                # We expect multiple messages if articles are found
                start_time = time.time()
                while time.time() - start_time < 120:
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                        data = json.loads(message)
                        print(f"Received WebSocket Message: {json.dumps(data, indent=2)}")
                        
                        if data.get("type") in {"news_item", "news_event"}:
                            print("✅ Verification SUCCESS: Received news event via WebSocket.")
                            return
                        else:
                            print(f"⚠️ Received unexpected message type: {data.get('type')}")
                    except asyncio.TimeoutError:
                        print("No message received in last 5 seconds...")
                        continue
                    
                print("❌ Verification FAILED: Timed out waiting for 2017 data.")
                    
            except Exception as e:
                print(f"❌ Error in receive loop: {e}")
                
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(verify_websocket())
