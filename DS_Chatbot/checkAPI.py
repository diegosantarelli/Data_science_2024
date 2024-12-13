import requests

def check_live_matches():
    API_TOKEN = "728961a145e54aa18538db538fe9d634"  # Sostituisci con il tuo token
    BASE_URL = "https://api.football-data.org/v4/matches"
    headers = {"X-Auth-Token": API_TOKEN}

    try:
        response = requests.get(BASE_URL, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("Dati ricevuti dall'API:", data)
            matches = data.get("matches", [])
            print("Partite disponibili:", matches)
        else:
            print(f"Errore API: {response.status_code}")
            print("Dettaglio errore:", response.text)
    except Exception as e:
        print(f"Errore durante la connessione all'API: {e}")

if __name__ == "__main__":
    check_live_matches()
