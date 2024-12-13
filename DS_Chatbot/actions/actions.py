import requests
import json
import os
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


# Percorso del file per la cache
CACHE_FILE_TEAMS = "teams_cache.json"
CACHE_FILE_COMPETITIONS = "competitions_cache.json"

# Funzione per salvare i dati nella cache
def save_to_cache(data, file_path):
    with open(file_path, "w") as f:
        json.dump(data, f)

# Funzione per caricare i dati dalla cache
def load_from_cache(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r") as f:
            return json.load(f)
    return None


class ActionFetchCompetitions(Action):
    def name(self) -> Text:
        return "action_fetch_competitions"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Prova a caricare i dati dalla cache
        cached_data = load_from_cache(CACHE_FILE_COMPETITIONS)

        if cached_data:
            # Usa i dati dalla cache
            competitions = cached_data
            message = "Ecco tutte le competizioni disponibili (dalla cache):\n" + "\n".join(competitions)
        else:
            # Effettua la richiesta se non ci sono dati in cache
            API_TOKEN = "728961a145e54aa18538db538fe9d634"
            BASE_URL = "https://api.football-data.org/v4"
            endpoint = "/competitions"

            url = f"{BASE_URL}{endpoint}"
            headers = {"X-Auth-Token": API_TOKEN}

            response = requests.get(url, headers=headers)

            if response.status_code == 200:
                data = response.json()
                competitions = [comp['name'] for comp in data['competitions']]
                save_to_cache(competitions, CACHE_FILE_COMPETITIONS)
                message = "Ecco tutte le competizioni disponibili:\n" + "\n".join(competitions)
            else:
                message = f"Errore nel recuperare i dati: {response.status_code}"

        dispatcher.utter_message(text=message)
        return []


class ActionFetchTeamDetails(Action):
    def name(self) -> Text:
        return "action_fetch_team_details"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        team_name = tracker.get_slot("team_name")

        if not team_name:
            dispatcher.utter_message(text="Non ho capito di quale squadra vuoi informazioni. Puoi specificare meglio?")
            return []

        team_name_normalized = team_name.strip().lower()

        # Prova a caricare i dati dalla cache
        cached_data = load_from_cache(CACHE_FILE_TEAMS)

        if cached_data:
            teams = cached_data
        else:
            # Effettua la richiesta all'API
            API_TOKEN = "123e4e24e9544052867f013ded06279d"
            TEAM_API_URL = "https://api.football-data.org/v4/teams"
            headers = {"X-Auth-Token": API_TOKEN}

            teams = []
            offset = 0
            limit = 100

            while True:
                params = {"offset": offset, "limit": limit}
                response = requests.get(TEAM_API_URL, headers=headers, params=params)

                if response.status_code != 200:
                    dispatcher.utter_message(text=f"Errore nell'API. Codice di risposta: {response.status_code}")
                    return []

                data = response.json()

                if 'teams' in data:
                    teams.extend(data['teams'])

                if len(data.get('teams', [])) < limit:
                    break

                offset += limit

            # Salva i dati nella cache
            save_to_cache(teams, CACHE_FILE_TEAMS)

        # Cerca le informazioni sulla squadra richiesta
        team_info = next((team for team in teams if team['name'].strip().lower() == team_name_normalized), None)

        if team_info:
            message = (
                f"Ecco le informazioni sulla squadra {team_info['name']}:\n"
                f"- Nome: {team_info['name']}\n"
                f"- Stadio: {team_info.get('venue', 'N/A')}\n"
                f"- Sito web: {team_info.get('website', 'N/A')}\n"
                f"- Data di fondazione: {team_info.get('founded', 'N/A')}\n"
                f"- Colore della maglia: {team_info.get('clubColors', 'N/A')}\n"
            )
        else:
            message = f"Non ho trovato informazioni su '{team_name}'. Verifica il nome e riprova."

        dispatcher.utter_message(text=message)
        return []


class ActionFetchLiveScores(Action):
    def name(self) -> Text:
        return "action_fetch_live_scores"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        API_TOKEN = "728961a145e54aa18538db538fe9d634"
        BASE_URL = "https://api.football-data.org/v4/matches"
        headers = {"X-Auth-Token": API_TOKEN}

        response = requests.get(BASE_URL, headers=headers)
        if response.status_code == 200:
            matches = response.json().get("matches", [])
            live_matches = [m for m in matches if m.get("status") == "LIVE"]
            print(f"Partite LIVE: {live_matches}")  # Log per debug

            if live_matches:
                message = "Ecco le partite in corso:\n"
                for match in live_matches:
                    message += (f"{match['homeTeam']['name']} "
                                f"{match['score']['fullTime']['home']} - "
                                f"{match['score']['fullTime']['away']} "
                                f"{match['awayTeam']['name']}\n")
            else:
                message = "Non ci sono partite in corso al momento."
        else:
            print(f"Errore API: {response.status_code}")  # Log errore
            message = "Errore nel recupero dei dati dall'API."

        dispatcher.utter_message(text=message)
        return []