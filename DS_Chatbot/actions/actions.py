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

import fastf1
from typing import Any, Text, Dict, List
from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.events import SlotSet

class ActionGetEventInfo(Action):

    def name(self) -> str:
        return "action_get_event_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Recupera i valori degli slot
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")

        if not gp or not year:
            dispatcher.utter_message(text="Per favore specifica sia il nome del GP che l'anno.")
            return []

        try:
            # Usa l'API di FastF1 per ottenere i dettagli dell'evento
            event = fastf1.get_event(int(year), gp)

            if event.empty:  # Se non ci sono risultati
                response = f"Non ho trovato informazioni per il GP di {gp} nel {year}."
            else:
                event_name = event['EventName']
                location = event['Location']
                date = event['EventDate']
                response = f"Il GP di {event_name} si tiene a {location} il {date}."

        except Exception as e:
            response = f"Errore nel recupero dei dati: {str(e)}"

        dispatcher.utter_message(text=response)
        return []


class ActionGetEventSchedule(Action):
    def name(self) -> str:
        return "action_get_event_schedule"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")

        if not gp or not year:
            dispatcher.utter_message(text="Per favore specifica il GP e l'anno.")
            return []

        try:
            # Sessioni standard di un weekend di gara
            session_types = ["FP1", "FP2", "FP3", "Q", "R"]
            session_names = {
                "FP1": "Prove Libere 1",
                "FP2": "Prove Libere 2",
                "FP3": "Prove Libere 3",
                "Q": "Qualifiche",
                "R": "Gara"
            }

            schedule = []
            for session_type in session_types:
                session = fastf1.get_session(int(year), gp, session_type)
                if session.date:
                    schedule.append(f"{session_names[session_type]}: {session.date.strftime('%d %B %Y, %H:%M')}")

            if not schedule:
                message = f"Non sono riuscito a trovare il programma per il GP di {gp} nel {year}."
            else:
                message = f"Programma del GP di {gp} nel {year}:\n" + "\n".join(schedule)

            dispatcher.utter_message(text=message)
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero del programma: {str(e)}")
        return []


class ActionGetRaceWinner(Action):
    def name(self) -> str:
        return "action_get_race_winner"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")

        if not gp or not year:
            dispatcher.utter_message(text="Per favore specifica il GP e l'anno.")
            return []

        try:
            session = fastf1.get_session(int(year), gp, "R")
            session.load()
            winner = session.results.iloc[0]
            driver = winner["FullName"]
            team = winner["TeamName"]
            dispatcher.utter_message(
                text=f"Il vincitore del GP di {gp} nel {year} è stato {driver} del team {team}."
            )
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero dei risultati: {str(e)}")
        return []

class ActionGetWeatherInfo(Action):
    def name(self) -> str:
        return "action_get_weather_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Recupera gli slot
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")

        # Controlla se gli slot sono impostati
        if not gp or not year:
            missing_slots = []
            if not gp:
                dispatcher.utter_message(response="utter_ask_gp")
                missing_slots.append("gp")
            if not year:
                dispatcher.utter_message(response="utter_ask_year")
                missing_slots.append("year")
            return []  # Interrompe l'azione finché gli slot non sono completati

        try:
            # Usa FastF1 per ottenere i dati meteo
            session = fastf1.get_session(int(year), gp, "R")
            session.load()
            weather = session.weather_data
            temp_avg = weather['AirTemp'].mean()
            response = f"Durante il GP di {gp} nel {year}, la temperatura media era di {temp_avg:.2f}°C."
            dispatcher.utter_message(text=response)
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero del meteo: {str(e)}")
        return []



class ActionGetFastestLap(Action):
    def name(self) -> str:
        return "action_get_fastest_lap"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")
        driver = tracker.get_slot("driver")

        if not gp or not year or not driver:
            dispatcher.utter_message(text="Per favore specifica il GP, l'anno e il pilota.")
            return []

        try:
            session = fastf1.get_session(int(year), gp, "R")
            session.load()
            laps = session.laps.pick_driver(driver.upper())
            fastest_lap = laps.pick_fastest()
            lap_time = fastest_lap['LapTime']
            dispatcher.utter_message(
                text=f"Il giro più veloce di {driver} nel GP di {gp} nel {year} è stato {lap_time}."
            )
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero del giro più veloce: {str(e)}")
        return []


from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
import fastf1

class ActionGetCircuitInfo(Action):
    def name(self) -> str:
        return "action_get_circuit_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Recupera lo slot GP
        gp = tracker.get_slot("gp")
        year = 2023  # Specifica un anno (può essere dinamico)

        if not gp:
            dispatcher.utter_message(text="Per quale GP vuoi informazioni sul circuito?")
            return []

        try:
            # Carica la sessione del GP
            session = fastf1.get_session(year, gp, "R")  # Sessione di gara
            session.load()

            # Recupera informazioni sul circuito
            circuit_info = session.get_circuit_info()

            if not circuit_info:
                response = f"Non ho trovato informazioni sul circuito del GP di {gp}."
            else:
                # Estrai dati
                corners = circuit_info.corners  # DataFrame delle curve
                marshal_lights = circuit_info.marshal_lights  # DataFrame delle luci
                marshal_sectors = circuit_info.marshal_sectors  # DataFrame dei settori
                rotation = circuit_info.rotation  # Rotazione del circuito

                # Dettagli principali
                num_corners = len(corners) if corners is not None else "Non disponibile"
                num_lights = len(marshal_lights) if marshal_lights is not None else "Non disponibile"
                num_sectors = len(marshal_sectors) if marshal_sectors is not None else "Non disponibile"

                # Formatta la risposta
                response = (
                    f"Il circuito del GP di {gp} ha un totale di {num_corners} curve, "
                    f"{num_lights} luci dei marshal e {num_sectors} settori dei marshal. "
                    f"La rotazione del circuito è di {rotation:.2f} gradi."
                )

        except Exception as e:
            response = f"Errore nel recupero delle informazioni sul circuito: {str(e)}"

        dispatcher.utter_message(text=response)
        return []
