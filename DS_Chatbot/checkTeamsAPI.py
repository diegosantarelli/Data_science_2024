import requests
import time

API_TOKEN = "728961a145e54aa18538db538fe9d634"
BASE_URL = "https://api.football-data.org/v4"
teams_endpoint = "/teams"
team_details_endpoint = "/teams/109"  # ID della Juventus FC
headers = {"X-Auth-Token": API_TOKEN}

def fetch_all_teams():
    teams = []
    url = f"{BASE_URL}{teams_endpoint}?limit=200"  # Aumentiamo il limite per ottenere più squadre per pagina
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            data = response.json()
            teams.extend(data['teams'])
            url = data.get('next', None)  # Gestiamo la paginazione
            print(f"Totale squadre trovate finora: {len(teams)}")
            # Aggiungi una pausa per evitare di superare il rate limit
            time.sleep(1)
        else:
            print(f"Errore nell'API: {response.status_code}")
            break
    return teams

def fetch_team_details(team_id):
    url = f"{BASE_URL}{team_details_endpoint}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        team_details = response.json()
        print(f"Dettagli della squadra con ID {team_id}:")
        print(f"Nome: {team_details['name']}")
        print(f"Stadio: {team_details.get('venue', 'N/A')}")
        print(f"Sito web: {team_details.get('website', 'N/A')}")
        print(f"Data di fondazione: {team_details.get('founded', 'N/A')}")
        print(f"Colore della maglia: {team_details.get('clubColors', 'N/A')}")
    else:
        print(f"Errore nel recuperare i dettagli della squadra {team_id}: {response.status_code}")

# Esegui il fetch di tutte le squadre
teams = fetch_all_teams()

# Stampa l'elenco completo delle squadre con ID
for team in teams:
    print(f"ID: {team['id']} - {team['name']}")

# Recupera e stampa i dettagli della Juventus FC (ID 109)
fetch_team_details(109)
