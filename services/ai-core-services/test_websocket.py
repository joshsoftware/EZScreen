import asyncio
import websockets
import json
import base64

async def test_bot_connection():
    uri = "ws://localhost:8002/attendee-websocket"
    
    print(f"Connecting to {uri}...")
    async with websockets.connect(uri) as websocket:
        print("Connected!")
        
        # 1. Simulate Attendee sending the bot.joined event
        join_payload = {
            "trigger": "bot.joined",
            "data": {
                "bot_id": "test_bot_123"
            }
        }
        await websocket.send(json.dumps(join_payload))
        print("Sent bot.joined event.")
        
        # 2. Listen for the Bot's Greeting (TTS output)
        while True:
            try:
                msg = await asyncio.wait_for(websocket.recv(), timeout=2.0)
                data = json.loads(msg)
                if data.get("trigger") == "realtime_audio.bot_output":
                    print("Received PCM audio chunk from Bot!")
                    # In a real test, you'd decode this base64 and play it
                    # chunk = base64.b64decode(data["data"]["chunk"])
            except asyncio.TimeoutError:
                print("No more audio received. Bot is listening...")
                break
                
        # 3. Simulate Candidate speaking (sending dummy PCM audio)
        print("Simulating candidate speech...")
        dummy_pcm = b'\x00' * 2400
        speech_payload = {
            "trigger": "realtime_audio.mixed",
            "data": {
                "chunk": base64.b64encode(dummy_pcm).decode('utf-8')
            }
        }
        await websocket.send(json.dumps(speech_payload))
        print("Sent mock candidate audio.")

if __name__ == "__main__":
    asyncio.run(test_bot_connection())
