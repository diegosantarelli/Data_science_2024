from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/webhooks/slack/webhook', methods=['POST'])
def slack_webhook():
    data = request.json
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    # Inoltra le altre richieste a Rasa
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5005)
