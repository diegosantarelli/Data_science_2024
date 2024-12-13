# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

# from typing import Any, Text, Dict, List
#
# from rasa_sdk import Action, Tracker
# from rasa_sdk.executor import CollectingDispatcher
#
#
# class ActionHelloWorld(Action):
#
#     def name(self) -> Text:
#         return "action_hello_world"
#
#     def run(self, dispatcher: CollectingDispatcher,
#             tracker: Tracker,
#             domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
#
#         dispatcher.utter_message(text="Hello World!")
#
#         return []

import requests
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher


class ActionFetchCompetitions(Action):
    def name(self) -> Text:
        return "action_fetch_competitions"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        # Token personale
        API_TOKEN = "728961a145e54aa18538db538fe9d634"
        BASE_URL = "https://api.football-data.org/v4"
        endpoint = "/competitions"

        # Effettua la richiesta
        url = f"{BASE_URL}{endpoint}"
        headers = {"X-Auth-Token": API_TOKEN}

        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            competitions = [comp['name'] for comp in data['competitions']]
            message = "Ecco tutte le competizioni disponibili:\n" + "\n".join(competitions)
        else:
            message = f"Errore nel recuperare i dati: {response.status_code}"

        # Invia la risposta al chatbot
        dispatcher.utter_message(text=message)
        return []
    

import requests
from typing import Any, Text, Dict, List
from rasa_sdk import Action
from rasa_sdk.executor import CollectingDispatcher


class ActionFetchTeamDetails(Action):
    def name(self) -> Text:
        return "action_fetch_team_details"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        team_name = tracker.get_slot("team_name")
        print(f"Team name estratto dallo slot: {team_name}")

        if not team_name:
            dispatcher.utter_message(text="Non ho capito di quale squadra vuoi informazioni. Puoi specificare meglio?")
            return []

        # Normalizza il nome della squadra per la ricerca
        team_name_normalized = team_name.strip().lower()
        print(f"Richiesta per la squadra: {team_name_normalized}")

        API_TOKEN = "728961a145e54aa18538db538fe9d634"
        TEAM_API_URL = "https://api.football-data.org/v4/teams"
        headers = {"X-Auth-Token": API_TOKEN}

        teams = []
        offset = 0
        limit = 100  # Limite massimo gestito dall'API
        total_teams = None

        try:
            # Recupera tutte le squadre tramite paginazione
            while True:
                params = {"offset": offset, "limit": limit}
                response = requests.get(TEAM_API_URL, headers=headers, params=params)

                if response.status_code != 200:
                    dispatcher.utter_message(text=f"Errore nell'API. Codice di risposta: {response.status_code}")
                    return []

                data = response.json()

                if total_teams is None and 'count' in data:
                    total_teams = data['count']

                if 'teams' in data:
                    teams.extend(data['teams'])

                print(f"Squadre recuperate finora: {len(teams)} / {total_teams if total_teams else 'sconosciuto'}")

                # Verifica se ci sono altre pagine di dati
                if len(data.get('teams', [])) < limit:
                    break  # Ultima pagina, nessun'altra richiesta necessaria

                offset += limit

            print(f"Risultato finale: {len(teams)} squadre trovate.")

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
                # Log di debug per verificare i dati della squadra
                print(f"Dettagli squadra trovata: {team_info}")
            else:
                message = f"Non ho trovato informazioni su '{team_name}'. Verifica il nome e riprova."

        except Exception as e:
            message = f"Errore durante il recupero delle informazioni: {str(e)}"
            print(f"Eccezione catturata: {str(e)}")

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

