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
        
        # Reset slots se è una nuova domanda
        if 'programma' in text:
            gp = None
            year = None
        else:
            # Get GP and year from entities or previous slots
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
        
        print(f"Current slots - GP: {gp}, Year: {year}")
        
        # Se è una risposta diretta con l'anno
        if text.isdigit() and len(text) == 4:
            year = text
            if gp:  # Se abbiamo già il GP memorizzato
                return self.get_schedule(dispatcher, gp, year)
            return [SlotSet("year", year)]
        
        # Se è una risposta diretta con il GP
        if not entities and not text.isdigit() and len(text.strip()) > 0:
            gp = text.strip()
            if year:  # Se abbiamo già l'anno memorizzato
                return self.get_schedule(dispatcher, gp, year)
            return [SlotSet("gp", gp)]
        
        # Estrazione dalle entities
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
        
        # Estrazione dal testo se necessario
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

        print(f"Final values - GP: {gp}, Year: {year}")

        # Gestione dei casi mancanti
        if gp and not year:
            dispatcher.utter_message(response="utter_ask_year")
            return [SlotSet("gp", gp)]
        elif year and not gp:
            dispatcher.utter_message(response="utter_ask_gp")
            return [SlotSet("year", year)]
        elif not gp and not year:
            dispatcher.utter_message(text="Per favore specifica sia il GP che l'anno.")
            return []

        # Se abbiamo entrambi i valori, procedi con la ricerca
        return self.get_schedule(dispatcher, gp, year)

    def get_schedule(self, dispatcher: CollectingDispatcher, gp: str, year: str):
        try:
            # Verifica che l'anno non sia oltre il 2024
            if int(year) >= 2025:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma non posso fornirti informazioni per l'anno {year}. "
                         f"Posso aiutarti solo con gli anni fino al 2024."
                )
                return []

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

            # Ottieni l'evento per determinare il tipo di weekend
            event = fastf1.get_event(int(year), gp)
            
            # Determina le sessioni disponibili per questo evento
            available_sessions = []
            schedule = []
            
            session_names = {
                "FP1": "Prove Libere 1",
                "FP2": "Prove Libere 2",
                "FP3": "Prove Libere 3",
                "Q": "Qualifiche",
                "S": "Sprint",
                "SQ": "Sprint Shootout",
                "R": "Gara"
            }

            # Prova a caricare ogni possibile sessione
            for session_type in ["FP1", "FP2", "FP3", "SQ", "Q", "S", "R"]:
                try:
                    session = fastf1.get_session(int(year), gp, session_type)
                    if session and session.date:
                        schedule.append(f"{session_names.get(session_type, session_type)}: {session.date.strftime('%d %B %Y, %H:%M')}")
                        available_sessions.append(session_type)
                except Exception as session_error:
                    print(f"DEBUG - Sessione {session_type} non disponibile: {str(session_error)}")
                    continue

            if not schedule:
                message = f"Non sono riuscito a trovare il programma per il GP di {gp} nel {year}."
            else:
                print(f"DEBUG - Sessioni disponibili: {available_sessions}")
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
        
        print("\n=== DEBUG INFO ===")
        print(f"Text: {text}")
        print(f"Entities: {entities}")
        
        # Reset slots se è una nuova domanda
        if 'vinto' in text or 'vincitore' in text:
            gp = None
            year = None
        else:
            # Get GP and year from entities or previous slots
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
        
        print(f"Current slots - GP: {gp}, Year: {year}")
        
        # Se è una risposta diretta con l'anno
        if text.isdigit() and len(text) == 4:
            year = text
            if gp:  # Se abbiamo già il GP memorizzato
                return self.get_winner(dispatcher, gp, year)
            return [SlotSet("year", year)]
        
        # Se è una risposta diretta con il GP
        if not entities and not text.isdigit() and len(text.strip()) > 0:
            gp = text.strip()
            if year:  # Se abbiamo già l'anno memorizzato
                return self.get_winner(dispatcher, gp, year)
            return [SlotSet("gp", gp)]
        
        # Estrazione dalle entities
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
        
        print(f"After entities extraction - GP: {gp}, Year: {year}")

        # Gestione dei casi mancanti
        if gp and not year:
            dispatcher.utter_message(response="utter_ask_year")
            return [SlotSet("gp", gp)]
        elif year and not gp:
            dispatcher.utter_message(response="utter_ask_gp")
            return [SlotSet("year", year)]
        elif not gp and not year:
            dispatcher.utter_message(text="Per favore specifica sia il GP che l'anno.")
            return []

        # Se abbiamo entrambi i valori, procedi con la ricerca
        return self.get_winner(dispatcher, gp, year)

    def get_winner(self, dispatcher: CollectingDispatcher, gp: str, year: str):
        try:
            print(f"\n=== DEBUG get_winner ===")
            print(f"Input - GP: {gp}, Year: {year}")
            
            # Verifica che l'anno non sia oltre il 2024
            if int(year) >= 2025:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma non posso fornirti informazioni per l'anno {year}. "
                         f"Posso aiutarti solo con gli anni fino al 2024."
                )
                return []

            # Get list of available events for that year
            print("Getting event schedule...")
            schedule = fastf1.get_event_schedule(int(year))
            
            # Check if GP exists and get its round number
            gp_lower = gp.lower()
            valid_gp = None
            matched_gp = None
            round_number = None
            
            # Cerca una corrispondenza esatta o parziale e ottieni il round number
            for _, row in schedule.iterrows():
                event_name = row['EventName']
                if gp_lower == event_name.lower():
                    valid_gp = True
                    matched_gp = event_name
                    round_number = row['RoundNumber']
                    break
                elif gp_lower in event_name.lower():
                    valid_gp = True
                    matched_gp = event_name
                    round_number = row['RoundNumber']
                    break
            
            print(f"GP validation - Is valid: {valid_gp}, Matched GP: {matched_gp}, Round: {round_number}")
            
            if not valid_gp:
                valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []

            # Usa l'API Ergast con il numero del round
            print(f"Getting results from Ergast API for round {round_number}...")
            ergast = Ergast()
            race_results = ergast.get_race_results(season=int(year), round=round_number)
            
            # Converti i risultati in DataFrame
            results_df = race_results.content[0]
            print(f"Results data: {results_df}")
            
            if results_df.empty:
                dispatcher.utter_message(text=f"Mi dispiace, non ho trovato risultati per il GP di {matched_gp} nel {year}.")
                return []
            
            # Il vincitore è il primo classificato
            winner = results_df.iloc[0]
            print(f"Winner data: {winner}")
            
            # Usa i campi corretti dal DataFrame
            driver_name = f"{winner['givenName']} {winner['familyName']}"
            team_name = winner['constructorName']
            grid_pos = winner['grid']
            laps = winner['laps']
            race_time = winner['totalRaceTime']
            fastest_lap = winner['fastestLapTime']
            
            print(f"Winner found: {driver_name} ({team_name})")
            
            response = (
                f"Il vincitore del GP di {matched_gp} nel {year} è stato {driver_name} del team {team_name}.\n"
                f"È partito dalla {grid_pos}ª posizione, ha completato {laps} giri "
                f"con un tempo totale di {race_time}.\n"
                f"Il suo giro più veloce è stato {fastest_lap}."
            )
            
            dispatcher.utter_message(text=response)
        except Exception as e:
            print(f"\nError in get_winner:")
            print(f"Type: {type(e)}")
            print(f"Message: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            dispatcher.utter_message(text=f"Mi dispiace, si è verificato un errore nel recupero dei risultati.")
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
