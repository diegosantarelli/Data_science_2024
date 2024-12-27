from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv
import os
import logging
import requests
import time
from slack_sdk import WebClient

load_dotenv()
SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
client = WebClient(token=SLACK_BOT_TOKEN)

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, 'static')

# Debug del percorso
logger.debug(f"BASE_DIR: {BASE_DIR}")
logger.debug(f"STATIC_DIR: {STATIC_DIR}")

def get_ngrok_url():
    try:
        # Ottieni l'URL di ngrok dalle API
        response = requests.get("http://localhost:4040/api/tunnels")
        tunnels = response.json()["tunnels"]
        for tunnel in tunnels:
            if tunnel["proto"] == "https":
                return tunnel["public_url"]
    except:
        return "http://localhost:5005"  # Fallback se ngrok non è in esecuzione
    return "http://localhost:5005"

# Usa invece
NGROK_URL = get_ngrok_url()
logger.debug(f"Using NGROK URL: {NGROK_URL}")

processed_events = set()

def handle_slack_event(data):
    logger.debug("Processing event: %s", data)
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data and data["event"]["type"] == "message":
        event = data["event"]
        event_id = data.get("event_id", "")
        
        # Controlla se l'evento è già stato processato
        if event_id in processed_events:
            logger.debug(f"Ignoring duplicate event: {event_id}")
            return jsonify({"status": "ignored"})
            
        # Aggiungi l'event_id al set degli eventi processati
        processed_events.add(event_id)
        
        # Limita la dimensione del set per evitare memory leaks
        if len(processed_events) > 1000:
            processed_events.clear()
        
        # Ignora i messaggi del bot (versione migliorata)
        if (
            event.get("bot_id") or 
            event.get("subtype") or 
            "bot_profile" in event or
            "retry_num" in request.headers or
            event.get("user") == os.getenv("BOT_USER_ID")
        ):
            logger.debug("Ignoring bot message or retry")
            return jsonify({"status": "ignored"})
            
        text = event["text"]
        user = event["user"]
        channel = event["channel"]
        
        logger.debug(f"Processing user message: {text}")
        
        # Invia il messaggio a Rasa
        rasa_payload = {
            "sender": user,
            "message": text
        }
        
        try:
            logger.debug("Sending to Rasa: %s", rasa_payload)
            rasa_response = requests.post(
                "http://localhost:5006/webhooks/rest/webhook",
                json=rasa_payload,
                timeout=30
            )
            responses = rasa_response.json()
            logger.debug("Rasa response: %s", responses)
            
            if responses:
                for response in responses:
                    if "image" in response:
                        # Invia prima il testo
                        text_message = {
                            "channel": channel,
                            "text": response.get("text", "")
                        }
                        requests.post(
                            "https://slack.com/api/chat.postMessage",
                            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                            json=text_message
                        )
                        
                        # Poi carica l'immagine direttamente
                        image_path = os.path.join(STATIC_DIR, 'images', response["image"].split("/")[-1])
                        logger.debug(f"Trying to open image at: {image_path}")
                        
                        try:
                            with open(image_path, 'rb') as file:
                                slack_response = client.files_upload_v2(
                                    channels=channel,
                                    file=file,
                                    title="Speed Map",
                                    filename=response["image"].split("/")[-1]
                                )
                                logger.debug("Slack file upload response: %s", slack_response)
                        except Exception as e:
                            logger.error(f"Error uploading file: {e}")
                            logger.error(f"File path attempted: {image_path}")
                    else:
                        # Invia solo il testo
                        slack_message = {
                            "channel": channel,
                            "text": response.get("text", "")
                        }
                        slack_response = requests.post(
                            "https://slack.com/api/chat.postMessage",
                            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                            json=slack_message
                        )
                        logger.debug("Slack text response: %s", slack_response.json())
                    
                    time.sleep(0.5)
            else:
                logger.warning("Empty response from Rasa")
                # Invia un messaggio di errore all'utente
                slack_message = {
                    "channel": channel,
                    "text": "Mi dispiace, non ho capito la tua richiesta. Puoi riprovare?"
                }
                requests.post(
                    "https://slack.com/api/chat.postMessage",
                    headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                    json=slack_message
                )
                
        except Exception as e:
            logger.error("Error processing message: %s", e)
            # Invia un messaggio di errore all'utente
            slack_message = {
                "channel": channel,
                "text": "Mi dispiace, sto avendo problemi tecnici. Riprova tra poco."
            }
            requests.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                json=slack_message
            )
    
    return jsonify({"status": "ok"})

@app.route('/', methods=['POST'])
def root():
    return handle_slack_event(request.json)

@app.route('/webhooks/slack', methods=['POST'])
@app.route('/webhooks/slack/webhook', methods=['POST'])
def slack_webhook():
    return handle_slack_event(request.json)

def send_message_to_slack(channel, text=None, image_path=None):
    if text:
        client.chat_postMessage(channel=channel, text=text)
    
    if image_path:
        try:
            # Carica il file direttamente su Slack
            with open(image_path, 'rb') as file:
                response = client.files_upload_v2(
                    channel=channel,
                    file=file,
                    title="Speed Map"
                )
        except Exception as e:
            logger.error(f"Error uploading file: {e}")

# Aggiungi questa route per servire i file statici
@app.route('/static/images/<path:filename>')
def serve_image(filename):
    return send_from_directory(os.path.join(STATIC_DIR, 'images'), filename)

if __name__ == '__main__':
    app.run(port=5005, debug=True)
