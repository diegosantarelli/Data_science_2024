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
