# main.py
#to run  uvicorn main:app --host 0.0.0.0 --port 8000 --reload
import os
import json
import base64
import asyncio
import logging
import io
import wave
from datetime import datetime, timezone
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from websockets.client import connect
import redis  # Import Redis
from pydub import AudioSegment  # For audio processing
from websockets.client import connect
from starlette.websockets import WebSocketState

load_dotenv()

app = FastAPI()

# CORS settings
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Adjust according to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenAI API key
OPENAI_API_KEY = 'sk-xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'
# OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    logging.error("OpenAI API Key not found. Please set the OPENAI_API_KEY environment variable.")
    raise ValueError("OpenAI API Key not found.")

# WebSocket URL and headers for OpenAI Realtime API
OPENAI_WS_URL = "wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview-2024-10-01"
OPENAI_WS_HEADERS = {
    "Authorization": f"Bearer {OPENAI_API_KEY}",
    "OpenAI-Beta": "realtime=v1",
}

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Load configurations from JSON
with open('config.json', 'r') as f:
    config_data = json.load(f)

# Initialize Redis client
def get_redis():
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
    redis_password = os.getenv('REDIS_PASSWORD', None)
    if redis_password:
        scheme, rest = redis_url.split("://", 1)
        redis_url = f"{scheme}://:{redis_password}@{rest}"
    try:
        client = redis.from_url(redis_url)
        if client.ping():
            logging.info("Successfully connected to Redis.")
            return client
        else:
            raise ConnectionError("Failed to ping Redis.")
    except redis.RedisError as e:
        logging.error(f"Redis connection error: {e}")
        raise

# Initialize the Redis client
r = get_redis()

# Define function for dummy implementation
def get_current_weather(location, unit="fahrenheit"):
    # The Dummy implementation requested;but later, i will it replace with real API call when needed
    weather_data = {
        "location": location,
        "temperature": "72",
        "unit": unit,
        "forecast": ["sunny", "windy"]
    }
    return weather_data


@app.websocket("/gpt-api/chat_stream/{organization}/{request_id}")
async def chat_stream(websocket: WebSocket, organization: str, request_id: str):
    await websocket.accept()
    try:
        logging.info(f"Frontend WebSocket connected for organization: {organization}, request_id: {request_id}")

        org_config = config_data.get(organization)
        if not org_config:
            error_message = f"Organization '{organization}' not found in configuration."
            logging.error(error_message)
            await websocket.send_text(json.dumps({"error": error_message}))
            await websocket.close()
            return

        # Build session configuration based on org_config
        session_config = {
            "type": "session.update",
            "session": {
                "voice": org_config.get("voice", "alloy"),
                "instructions": org_config["prompts"]["instructions"],
                "turn_detection": org_config.get("turn_detection"),
                "input_audio_format": org_config.get("input_audio_format", "pcm16"),
                "output_audio_format": org_config.get("output_audio_format", "pcm16"),
                "input_audio_transcription": org_config.get("input_audio_transcription", {"model": "whisper-1"}),
                "temperature": org_config.get("temperature", 0.8),
                "tool_choice": org_config.get("tool_choice", "auto"),
                "tools": org_config.get("tools", []),
                "max_response_output_tokens": org_config.get("max_response_output_tokens", "inf")
           }
        }

    except Exception as e:
        logging.error(f"Error during WebSocket setup: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))
        await websocket.close()
        return

    try:
        async with connect(
            OPENAI_WS_URL,
            extra_headers=OPENAI_WS_HEADERS
        ) as openai_ws:
            logging.info("Connected to OpenAI Realtime API")

            # Send session configuration
            await openai_ws.send(json.dumps(session_config))

            # Start tasks for bidirectional communication
            chat_history = []
            await asyncio.gather(
                handle_frontend_to_openai(websocket, openai_ws, organization, request_id, chat_history),
                handle_openai_to_frontend(websocket, openai_ws, organization, request_id, chat_history),
            )

    except WebSocketDisconnect:
        logging.info("Frontend WebSocket disconnected")
    except Exception as e:
        logging.error(f"Error: {e}")
        await websocket.send_text(json.dumps({"error": str(e)}))

async def handle_frontend_to_openai(frontend_ws: WebSocket, openai_ws, organization, request_id, chat_history):
    while True:
        try:
            message = await frontend_ws.receive()
            message_type = message.get('type')

            if message_type == 'websocket.receive':
                if 'bytes' in message and message['bytes'] is not None:
                    audio_chunk = message['bytes']
                    logging.info(f"Received audio chunk of size {len(audio_chunk)} bytes from frontend")

                    # Process audio to match OpenAI requirements
                    base64_audio = process_audio(audio_chunk)

                    # Send audio data to OpenAI Realtime API
                    await openai_ws.send(json.dumps({
                        "type": "input_audio_buffer.append",
                        "audio": base64_audio
                    }))

                    # Optionally commit and request a response
                    await openai_ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                    await openai_ws.send(json.dumps({"type": "response.create"}))

                elif 'text' in message and message['text'] is not None:
                    text_data = message['text']
                    logging.info(f"Received text message from frontend: {text_data}")

                    # Parse the text_data as JSON to extract the actual text content

                    try:
                        parsed_message = json.loads(text_data)
                        text_content = parsed_message.get('text', text_data)
                    except json.JSONDecodeError:
                        text_content = text_data

                    # Handle special signals as Vladimar sent me on slack
                    if text_content.startswith("DOCUMENT_SENT:"):
                        logging.info("Document received")
                        # TODO: In The future Add processing for the document
                        # For now, send acknowledgment to frontend
                        await frontend_ws.send_text(json.dumps({"info": "Document received"}))
                        continue
                    elif text_content.startswith("IMAGE_SENT:"):
                        logging.info("Image received")
                        # TODO: Add processing for the image
                        # For now, send acknowledgment to frontend
                        await frontend_ws.send_text(json.dumps({"info": "Image received"}))
                        continue

                    elif text_content == "DOWNLOAD_CHAT_HISTORY_BUTTON_CLICKED":
                        logging.info("User requested to download chat history.")
                        # Retrieve chat history from Redis
                        redis_key = f"{organization}:conversation:{request_id}"
                        conversation_data = r.get(redis_key)
                        if conversation_data:
                            # Send the conversation data back to the frontend
                            await frontend_ws.send_text(json.dumps({
                                "chat_history": json.loads(conversation_data)
                            }))
                        else:
                            await frontend_ws.send_text(json.dumps({"error": "Chat history not found."}))
                        continue  # Then i guess i will  Continue to the next iteration of the loop


                    else:
                        # Save user message to chat history
                        chat_history.append({
                            'sender': 'user',
                            'message': text_content,
                            'timestamp':  datetime.now(timezone.utc).isoformat()
                        })

                        # Send text message to OpenAI
                        await openai_ws.send(json.dumps({
                            "type": "conversation.item.create",
                            "item": {
                                "type": "message",
                                "role": "user",
                                "content": [
                                    {
                                        "type": "input_text",
                                        "text": text_content
                                    }
                                ]
                            }
                        }))

                        # Request a response from OpenAI
                        await openai_ws.send(json.dumps({"type": "response.create"}))

                else:
                    logging.warning("Received message with no 'text' or 'bytes' from frontend.")

            elif message_type == 'websocket.disconnect':
                logging.info("Frontend WebSocket disconnected")
                break

        except Exception as e:
            logging.error(f"Error in frontend to OpenAI communication: {e}")
            break

async def handle_openai_to_frontend(frontend_ws: WebSocket, openai_ws, organization, request_id, chat_history):
    audio_chunks = bytearray()  # Accumulator for audio data
    async for message in openai_ws:
        try:
            # Log the raw message and its type
            logging.info(f"Received message from OpenAI of type {type(message)}")

            # Check if message is bytes and decode it
            if isinstance(message, bytes):
                message_text = message.decode('utf-8')
            elif isinstance(message, str):
                message_text = message
            else:
                # Handle unexpected message types
                logging.error(f"Received unexpected message type from OpenAI: {type(message)}")
                continue

            # Parse the JSON message
            event = json.loads(message_text)
            logging.info(f"Received event from OpenAI: {event}")

          

            # Ensure 'type' is in event
            event_type = event.get('type')
            if not event_type:
                logging.error(f"No 'type' field in event: {event}")
                continue

            # Process the event based on its type
            if event_type == 'conversation.item.created':
                item = event.get('item', {})
                item_type = item.get('type')
                role = item.get('role')

                if item_type == 'message' and role == 'assistant':
                    # Extract the AI's message
                    content_list = item.get('content', [])
                    ai_message = ''
                    for content in content_list:
                        content_type = content.get('type')
                        if content_type == 'text':
                            ai_message += content.get('text', '')
                        elif content_type == 'audio':
                            ai_message += content.get('transcript', '')
                    chat_history.append({
                        'sender': 'bot',
                        'message': ai_message,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    # Save chat history to Redis
                    save_conversation(organization, request_id, chat_history)
                    # Optionally, send text_done to frontend
                    if frontend_ws.client_state == WebSocketState.CONNECTED:
                        await frontend_ws.send_text(json.dumps({"text_done": True}))

                # if item_type == 'message' and role == 'assistant':
                #     # Extract the AI's message
                #     ai_message = ''.join([content.get('text', '') for content in item.get('content', [])])
                #     chat_history.append({
                #         'sender': 'bot',
                #         'message': ai_message,
                #         'timestamp':  datetime.now(timezone.utc).isoformat()
                #     })
                #     # Save chat history to Redis
                #     save_conversation(organization, request_id, chat_history)
                #     # Send text_done to frontend
                #     await frontend_ws.send_text(json.dumps({"text_done": True}))

                elif item_type == 'function_call':
                    # Handle function call item
                    function_call = item.get('function_call', {})
                    function_name = function_call.get('name')
                    function_args = json.loads(function_call.get('arguments', '{}'))
                    call_id = item.get('id')

                    logging.info(f"Function call received: {function_name} with args {function_args}")

                    # Execute the function
                    if function_name == 'get_current_weather':
                        result = get_current_weather(**function_args)
                    else:
                        result = {"error": f"Function '{function_name}' not found."}

                    # Send function_call_output to OpenAI
                    await openai_ws.send(json.dumps({
                        "type": "conversation.item.create",
                        "item": {
                            "type": "function_call_output",
                            "call_id": call_id,
                            "output": json.dumps(result)
                        }
                    }))

                    # Request the model to generate the assistant's response using the function call result
                    await openai_ws.send(json.dumps({"type": "response.create"}))

            elif event_type == 'response.text.delta':
                text_delta = event.get('delta', '')
                if frontend_ws.client_state == WebSocketState.CONNECTED:
                    await frontend_ws.send_text(json.dumps({"text": text_delta}))

            elif event_type == 'response.text.done':
                # Handle end of text response if needed
                if frontend_ws.client_state == WebSocketState.CONNECTED:
                    await frontend_ws.send_text(json.dumps({"text_done": True}))

            elif event_type == 'response.audio.delta':
                audio_base64 = event.get('delta', '')
                if audio_base64:
                    try:
                        pcm_data = base64.b64decode(audio_base64)
                        audio_chunks.extend(pcm_data)
                    except Exception as e:
                        logging.error(f"Error processing audio data: {e}")
                else:
                    logging.warning("Received 'response.audio.delta' event without 'delta' data.")

            elif event_type == 'response.audio.done':
                # Convert accumulated PCM data to WAV
                if audio_chunks:
                    wav_data = pcm_to_wav(bytes(audio_chunks))
                    # Send WAV data as bytes to the frontend
                    if frontend_ws.client_state == WebSocketState.CONNECTED:
                        await frontend_ws.send_bytes(wav_data)
                    # Clear the accumulator for future responses
                    audio_chunks.clear()
                if frontend_ws.client_state == WebSocketState.CONNECTED:
                    await frontend_ws.send_text(json.dumps({"audio_done": True}))

            elif event_type == 'error':
                logging.error(f"Error from OpenAI: {event}")
                error_message = event.get('error', {}).get('message', 'Unknown error')
                if frontend_ws.client_state == WebSocketState.CONNECTED:
                    await frontend_ws.send_text(json.dumps({"error": error_message}))


            elif event_type == 'session.created':
                logging.info("Session created event received from OpenAI.")

                continue

            elif event_type == 'response.done':
                logging.info("Response processing completed.")
                # Optionally, you can handle usage statistics or perform cleanup
                response = event.get('response', {})
                # Log usage statistics if needed
                usage = response.get('usage', {})
                logging.info(f"Usage statistics: {usage}")
                # You can also send a message to the frontend if necessary
                continue  # Proceed to the next event
            elif event_type == 'response.output_item.done':
                item = event.get('item', {})
                item_type = item.get('type')
                role = item.get('role')

                if item_type == 'message' and role == 'assistant':
                    # Extract the AI's message
                    content_list = item.get('content', [])
                    ai_message = ''
                    for content in content_list:
                        content_type = content.get('type')
                        if content_type == 'text':
                            ai_message += content.get('text', '')
                        elif content_type == 'audio':
                            ai_message += content.get('transcript', '')
                    chat_history.append({
                        'sender': 'bot',
                        'message': ai_message,
                        'timestamp': datetime.now(timezone.utc).isoformat()
                    })
                    # Save chat history to Redis
                    save_conversation(organization, request_id, chat_history)
                logging.info("Output item processing completed.")

            elif event_type == 'session.updated':
                logging.info(f"Session updated: {event['session']}")
                # Optionally, send session details to frontend
                continue
            else:
                logging.info(f"Unhandled event type: {event_type}")
                # Handle other event types as needed

        except Exception as e:
            logging.error(f"Error in OpenAI to frontend communication: {e}")
            break

def save_conversation(organization, request_id, chat_history, expire_seconds=86400):
    if not chat_history:
        logging.warning("save_conversation called with empty chat_history.")
        return

    logging.info(f"Saving chat_history for {organization}:{request_id}")
    metadata = {
        'created': chat_history[0]['timestamp'],
        'downloaded':  datetime.now(timezone.utc).isoformat(),
        'number_of_requests': sum(1 for msg in chat_history if msg.get('sender') == 'user'),
        'number_of_responses': sum(1 for msg in chat_history if msg.get('sender') == 'bot'),
    }
    redis_key = f"{organization}:conversation:{request_id}"
    conversation_data = {'metadata': metadata, 'messages': chat_history}
    try:
        r.setex(redis_key, expire_seconds, json.dumps(conversation_data))
        logging.info(f"Conversation saved to Redis with key: {redis_key}")
    except redis.RedisError as e:
        logging.error(f"Failed to save conversation to Redis: {e}")

def process_audio(raw_audio):
    # Convert audio to 16-bit PCM, 24kHz, mono, little-endian
    audio = AudioSegment.from_file(io.BytesIO(raw_audio))
    audio = audio.set_frame_rate(24000).set_channels(1).set_sample_width(2)
    pcm_audio = audio.raw_data

    # Encode to base64
    base64_audio = base64.b64encode(pcm_audio).decode('utf-8')
    return base64_audio

def pcm_to_wav(pcm_data):
    # Define WAV file parameters
    num_channels = 1
    sample_width = 2  # 16-bit audio
    frame_rate = 24000  # 24kHz

    # Create a BytesIO object to hold WAV data
    wav_io = io.BytesIO()

    # Initialize WAV writer
    with wave.open(wav_io, 'wb') as wav_file:
        wav_file.setnchannels(num_channels)
        wav_file.setsampwidth(sample_width)
        wav_file.setframerate(frame_rate)
        wav_file.writeframes(pcm_data)

    # Get WAV data from BytesIO object
    wav_data = wav_io.getvalue()
    return wav_data

