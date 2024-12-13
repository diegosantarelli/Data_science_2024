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
    
class ActionFetchTeamDetails(Action):

    def name(self) -> Text:
        return "action_fetch_team_details"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        team_name = tracker.get_slot("team_name")
        print(f"Team name nello slot: {team_name}")  # Log per debug
        dispatcher.utter_message(text=f"Sto cercando informazioni per la squadra: {team_name}")
    
        if not team_name:
            dispatcher.utter_message(text="Non ho capito di quale squadra vuoi informazioni. Puoi specificare meglio?")
            return []

        API_TOKEN = "728961a145e54aa18538db538fe9d634"
        TEAM_API_URL = "https://api.football-data.org/v4/teams"
        headers = {"X-Auth-Token": API_TOKEN}

        try:
            response = requests.get(TEAM_API_URL, headers=headers)
            print(f"Richiesta API effettuata. Status code: {response.status_code}")  # Log per debug

            # Aggiungi qui per stampare il corpo della risposta
            print(f"Contenuto della risposta: {response.text}")  # Visualizza il corpo della risposta come testo

            if response.status_code == 200:
                teams = response.json().get('teams', [])
                print(f"Squadre trovate: {len(teams)}")  # Log per debug

                # Cerca i dettagli della squadra
                team_info = next((team for team in teams if team['name'].lower() == team_name.lower()), None)

                if team_info:
                    message = (
                        f"Ecco le informazioni sulla squadra {team_name}:\n"
                        f"- Nome: {team_info['name']}\n"
                        f"- Sito web: {team_info.get('website', 'N/A')}\n"
                        f"- Stadio: {team_info.get('venue', 'N/A')}\n"
                    )
                else:
                    message = f"Non ho trovato informazioni su '{team_name}'. Verifica il nome e riprova."
            else:
                message = f"Errore nell'API. Codice di risposta: {response.status_code}"

        except Exception as e:
            message = f"Errore durante il recupero delle informazioni: {str(e)}"
            print(f"Errore: {str(e)}")  # Log per debug

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

