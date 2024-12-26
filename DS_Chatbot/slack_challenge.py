from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import logging
import requests
import time

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)

SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')

def handle_slack_event(data):
    logger.debug("Processing event: %s", data)
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data and data["event"]["type"] == "message":
        event = data["event"]
        
        # Ignora i messaggi del bot
        if (
            event.get("bot_id") or 
            event.get("subtype") or 
            "bot_profile" in event or
            "retry_num" in request.headers
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
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
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
                        slack_message = {
                            "channel": channel,
                            "text": response["text"]
                        }
                        slack_response = requests.post(
                            "https://slack.com/api/chat.postMessage",
                            headers={"Authorization": f"Bearer {SLACK_BOT_TOKEN}"},
                            json=slack_message
                        )
                        logger.debug("Slack response: %s", slack_response.json())
                        
                        # Aggiungi un piccolo delay tra i messaggi
                        time.sleep(0.5)
                    
                    break  # Esci dal loop se tutto è andato bene
                else:
                    logger.warning("Empty response from Rasa")
                    retry_count += 1
                    time.sleep(1)  # Attendi prima di riprovare
                    
            except Exception as e:
                logger.error("Error processing message: %s", e)
                retry_count += 1
                time.sleep(1)  # Attendi prima di riprovare
                
                if retry_count == max_retries:
                    # Invia un messaggio di errore all'utente
                    slack_message = {
                        "channel": channel,
                        "text": "Mi dispiace, sto avendo problemi a processare la tua richiesta. Riprova tra qualche momento."
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

if __name__ == '__main__':
    app.run(port=5005, debug=True)
