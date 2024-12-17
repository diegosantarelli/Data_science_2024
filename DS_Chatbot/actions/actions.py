from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fastf1.ergast import Ergast



class ActionGetCircuitInfo(Action):
    def name(self) -> str:
        return "action_get_circuit_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Recupera lo slot "gp" (nome del circuito)
        circuit_name = tracker.get_slot("gp")
        year = 2023  # Anno di default

        if not circuit_name:
            dispatcher.utter_message(text="Per quale circuito vuoi informazioni?")
            return []

        try:
            # Inizializza l'interfaccia Ergast per ottenere la lista dei circuiti
            ergast = Ergast(result_type="pandas")
            circuits_df = ergast.get_circuits(season=year)

            # Controlliamo se i risultati esistono
            if circuits_df.empty:
                dispatcher.utter_message(text="Non ho trovato alcun circuito per la stagione specificata.")
                return []

            # Normalizza i nomi per cercare in modo insensibile a maiuscole/minuscole
            circuits_df["circuitName_lower"] = circuits_df["circuitName"].str.lower()
            circuit_name_lower = circuit_name.lower()

            # Filtra il DataFrame per trovare il circuito desiderato
            filtered_circuit = circuits_df[circuits_df["circuitName_lower"] == circuit_name_lower]

            # Se non ci sono risultati, restituisci un messaggio all'utente
            if filtered_circuit.empty:
                valid_circuits = circuits_df["circuitName"].tolist()
                dispatcher.utter_message(
                    text=f"Non ho trovato il circuito '{circuit_name}'. "
                         f"Prova con uno di questi: {', '.join(valid_circuits)}."
                )
                return []

            # Estrai informazioni sul circuito
            circuit = filtered_circuit.iloc[0]
            response = (
                f"Il circuito '{circuit['circuitName']}' si trova a {circuit['locality']}, {circuit['country']}.\n"
                f"Coordinate: latitudine {circuit['lat']}, longitudine {circuit['long']}."
            )

        except Exception as e:
            # Gestione errore generico
            dispatcher.utter_message(
                text="Si è verificato un errore nel recupero delle informazioni. Riprova più tardi."
            )
            print(f"Errore: {e}")
            return []

        dispatcher.utter_message(text=response)
        return []

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
