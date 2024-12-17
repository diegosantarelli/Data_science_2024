from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fastf1.ergast import Ergast
from fuzzywuzzy import process
import fastf1
from rasa_sdk.events import SlotSet

class ActionGetCircuitInfo(Action):
    def name(self) -> str:
        return "action_get_circuit_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Extract circuit name from entities in the latest message
        latest_message = tracker.latest_message
        entities = latest_message.get('entities', [])
        text = latest_message.get('text', '').lower()
        
        # Extract circuit name from text or entities
        circuit_name = None
        if 'circuito di' in text:
            for entity in entities:
                if entity['entity'] == 'gp':
                    circuit_name = entity['value']
                    break
            
            if not circuit_name:
                circuit_name = text.split('circuito di')[-1].strip()
        else:
            # Se non c'è "circuito di", prova a estrarre il nome dalla parte finale del testo
            circuit_name = text.strip()

        if not circuit_name:
            dispatcher.utter_message(text="Per quale circuito vuoi informazioni?")
            return []

        try:
            # Get circuits from API
            ergast = Ergast(result_type="pandas")
            circuits_df = ergast.get_circuits(season=2023)
            
            # Normalize circuit names for comparison
            circuit_name_lower = circuit_name.lower().strip()
            circuits_df["circuitName_lower"] = circuits_df["circuitName"].str.lower().str.strip()
            
            # Try exact match first
            filtered_circuit = circuits_df[circuits_df["circuitName_lower"].str.contains(circuit_name_lower, na=False, case=False)]
            
            # If no matches found, return list of valid circuits
            if filtered_circuit.empty:
                valid_circuits = sorted(circuits_df["circuitName"].tolist())
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{circuit_name}' non è un circuito valido. "
                         f"Ecco i circuiti disponibili: {', '.join(valid_circuits)}."
                )
                return []

            # If match found, return circuit info
            circuit = filtered_circuit.iloc[0]
            response = (
                f"Il circuito '{circuit['circuitName']}' si trova a {circuit['locality']}, {circuit['country']}.\n"
                f"Coordinate: latitudine {circuit['lat']}, longitudine {circuit['long']}."
            )
            dispatcher.utter_message(text=response)
            return []

        except Exception as e:
            dispatcher.utter_message(text="Si è verificato un errore nel recupero delle informazioni. Riprova più tardi.")
            print(f"Errore: {e}")
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
        # Extract entities from the latest message
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        entities = latest_message.get('entities', [])
        
        print("\n=== DEBUG INFO ===")
        print(f"Text: {text}")
        print(f"Entities: {entities}")
        
        # Get GP and year from entities
        gp = None
        year = None
        
        # Estrai GP e year dalle entities
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
                
        print(f"After entities extraction - GP: {gp}, Year: {year}")
            
        # Se non sono stati trovati nelle entities, prova a estrarli dal testo
        if not gp and ('gp di' in text or 'gran premio di' in text):
            text_parts = text.split('gp di' if 'gp di' in text else 'gran premio di')
            if len(text_parts) > 1:
                gp = text_parts[1].split('nel')[0].strip()
        
        if not year and 'nel' in text:
            year_part = text.split('nel')[1].strip()
            try:
                year = year_part[:4]  # prendi i primi 4 caratteri che dovrebbero essere l'anno
            except:
                year = None

        print(f"After text extraction - GP: {gp}, Year: {year}")
        print(f"Current slots - GP: {tracker.get_slot('gp')}, Year: {tracker.get_slot('year')}")
        print("=== END DEBUG ===\n")

        # Gestione dei casi mancanti
        if not gp and not year:
            print("Both GP and year missing")
            dispatcher.utter_message(response="utter_ask_gp")
            dispatcher.utter_message(response="utter_ask_year")
            return []
        elif not gp:
            print("Only GP missing")
            dispatcher.utter_message(response="utter_ask_gp")
            return []
        elif not year:
            print("Only year missing")
            dispatcher.utter_message(response="utter_ask_year")
            return []

        try:
            # Get list of available events for that year
            schedule = fastf1.get_event_schedule(int(year))
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Check if GP exists
            gp_lower = gp.lower()
            valid_gp = any(gp_lower in event.lower() for event in valid_events)
            
            print(f"GP validation - Is valid: {valid_gp}")
            
            if not valid_gp:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []

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
                try:
                    session = fastf1.get_session(int(year), gp, session_type)
                    if session and session.date:
                        schedule.append(f"{session_names[session_type]}: {session.date.strftime('%d %B %Y, %H:%M')}")
                except Exception as session_error:
                    print(f"Errore nel recupero della sessione {session_type}: {str(session_error)}")
                    continue

            if not schedule:
                message = f"Non sono riuscito a trovare il programma per il GP di {gp} nel {year}."
            else:
                message = f"Programma del GP di {gp} nel {year}:\n" + "\n".join(schedule)

            dispatcher.utter_message(text=message)
            
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero del programma: {str(e)}")
            print(f"Errore generale: {str(e)}")
        return []


class ActionGetRaceWinner(Action):
    def name(self) -> str:
        return "action_get_race_winner"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Extract entities from the latest message
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        entities = latest_message.get('entities', [])
        
        # Get GP and year from entities
        gp = None
        year = None
        
        # Estrai GP e year dalle entities
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
                
        # Se non sono stati trovati nelle entities, prova a estrarli dal testo
        if not gp and ('gp di' in text or 'gran premio di' in text):
            text_parts = text.split('gp di' if 'gp di' in text else 'gran premio di')
            if len(text_parts) > 1:
                gp = text_parts[1].split('nel')[0].strip()
        
        if not year and 'nel' in text:
            year_part = text.split('nel')[1].strip()
            try:
                year = year_part[:4]
            except:
                year = None

        # Gestione dei casi mancanti
        if not gp and not year:
            dispatcher.utter_message(response="utter_ask_gp")
            dispatcher.utter_message(response="utter_ask_year")
            return []
        elif not gp:
            dispatcher.utter_message(response="utter_ask_gp")
            return []
        elif not year:
            dispatcher.utter_message(response="utter_ask_year")
            return []

        try:
            # Get list of available events for that year
            schedule = fastf1.get_event_schedule(int(year))
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Check if GP exists
            gp_lower = gp.lower()
            valid_gp = any(gp_lower in event.lower() for event in valid_events)
            
            if not valid_gp:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []

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
            print(f"Errore generale: {str(e)}")
        return []

class ActionGetWeatherInfo(Action):
    def name(self) -> str:
        return "action_get_weather_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Extract entities from the latest message
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        entities = latest_message.get('entities', [])
        
        # Get GP and year from entities
        gp = None
        year = None
        
        # Estrai GP e year dalle entities
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
                
        # Se non sono stati trovati nelle entities, prova a estrarli dal testo
        if not gp and ('gp di' in text or 'gran premio di' in text):
            text_parts = text.split('gp di' if 'gp di' in text else 'gran premio di')
            if len(text_parts) > 1:
                gp = text_parts[1].split('nel')[0].strip()
        
        if not year and 'nel' in text:
            year_part = text.split('nel')[1].strip()
            try:
                year = year_part[:4]  # prendi i primi 4 caratteri che dovrebbero essere l'anno
            except:
                year = None

        if not gp or not year:
            dispatcher.utter_message(text="Per favore specifica sia il GP che l'anno.")
            return []

        try:
            # Get list of available events for that year
            schedule = fastf1.get_event_schedule(int(year))
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Check if GP exists
            gp_lower = gp.lower()
            valid_gp = any(gp_lower in event.lower() for event in valid_events)
            
            if not valid_gp:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []

            # Usa FastF1 per ottenere i dati meteo
            session = fastf1.get_session(int(year), gp, "R")
            session.load()
            weather = session.weather_data
            temp_avg = weather['AirTemp'].mean()
            response = f"Durante il GP di {gp} nel {year}, la temperatura media era di {temp_avg:.2f}°C."
            dispatcher.utter_message(text=response)
            
        except Exception as e:
            dispatcher.utter_message(text=f"Errore nel recupero del meteo: {str(e)}")
            print(f"Errore generale: {str(e)}")
        return []



class ActionGetFastestLap(Action):
    def name(self) -> str:
        return "action_get_fastest_lap"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Extract entities from the latest message
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        entities = latest_message.get('entities', [])
        
        # Get GP, year and driver from entities
        gp = None
        year = None
        driver = None
        
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
            elif entity['entity'] == 'driver':
                driver = entity['value']

        # Gestione dei casi mancanti
        missing_info = []
        if not gp:
            missing_info.append("utter_ask_gp")
        if not year:
            missing_info.append("utter_ask_year")
        if not driver:
            missing_info.append("utter_ask_driver")
            
        if missing_info:
            for response in missing_info:
                dispatcher.utter_message(response=response)
            return []

        try:
            # Get list of available events for that year
            schedule = fastf1.get_event_schedule(int(year))
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Check if GP exists
            gp_lower = gp.lower()
            valid_gp = any(gp_lower in event.lower() for event in valid_events)
            
            if not valid_gp:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []

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
            print(f"Errore generale: {str(e)}")
        return []
