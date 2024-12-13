import requests

# Token API
API_TOKEN = "728961a145e54aa18538db538fe9d634"
TEAM_API_URL = "https://api.football-data.org/v4/teams"
headers = {"X-Auth-Token": API_TOKEN}

teams = []
offset = 0
limit = 100  # Limite per ogni richiesta API (verifica il limite supportato dall'API)
total_teams = None  # Variabile per il numero totale di squadre (se disponibile)

# Funzione per ottenere tutte le squadre
while True:
    params = {"offset": offset, "limit": limit}
    response = requests.get(TEAM_API_URL, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Errore nell'API. Codice di risposta: {response.status_code}")
        break

    data = response.json()
    
    # Recupera il numero totale di squadre (se disponibile)
    if total_teams is None and 'count' in data:
        total_teams = data['count']  # Numero totale di squadre

    # Aggiungi le squadre trovate alla lista
    if 'teams' in data:
        teams.extend(data['teams'])

    # Aggiorna il contatore di offset
    offset += limit

    # Verifica se sono stati caricati tutti i dati
    if len(data.get('teams', [])) < limit:
        # Se il numero di squadre nella risposta è inferiore al limite, abbiamo terminato
        break

# Controlla se il numero di squadre è coerente con il totale
if total_teams is not None:
    if len(teams) == total_teams:
        print(f"Tutte le {total_teams} squadre sono state scaricate correttamente!")
    else:
        print(f"Errore: scaricate {len(teams)} squadre su {total_teams} totali.")
else:
    print("Non è stato possibile verificare il numero totale di squadre.")

# Stampa la lista numerata di tutte le squadre
print(f"Totale squadre trovate: {len(teams)}")
for i, team in enumerate(teams, start=1):
    print(f"{i}. {team['name']}")
