from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fastf1.ergast import Ergast
from fuzzywuzzy import fuzz, process
import fastf1
from rasa_sdk.events import SlotSet
from typing import Dict, Any, List, Text

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
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        entities = latest_message.get('entities', [])
        
        # Ottieni la lista dei GP validi all'inizio
        try:
            schedule = fastf1.get_event_schedule(2023)
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
        except Exception as e:
            dispatcher.utter_message(text="Si è verificato un errore nella validazione del GP.")
            return []
        
        # Reset slots se è una nuova domanda
        if 'programma' in text or 'orari' in text:
            gp = None
            year = None
        else:
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
        
        # Estrai l'anno dalle entities o dal testo
        for entity in entities:
            if entity['entity'] == 'year':
                year = entity['value']
                break
        
        # Se è una risposta diretta con l'anno
        if text.isdigit() and len(text) == 4:
            year = text
            if gp:  # Se abbiamo già il GP memorizzato
                return self.get_schedule(dispatcher, gp, year)
            return [SlotSet("year", year)]
        
        if not year and 'nel' in text:
            try:
                year = text.split('nel')[1].strip()[:4]
            except:
                year = None
        
        # Estrai il GP dal testo o dalle entities
        if not gp:
            # Prima cerca nelle entities
            for entity in entities:
                if entity['entity'] == 'gp':
                    gp = entity['value']
                    break
            
            # Se non trovato nelle entities, usa il testo completo se è una risposta a utter_ask_gp
            if not gp and tracker.latest_action_name == "utter_ask_gp":
                gp = text.strip()
            
            # Altrimenti prova a pulire il testo
            elif not gp:
                text_clean = text
                words_to_remove = [
                    'mostrami', 'gli orari', 'del', 'gp di', 'gran premio di', 'nel',
                    year if year else '', 'qual è', 'il programma', 'qual', 'è',
                    '?', '.', '!'  # Rimuovi la punteggiatura
                ]
                for remove in words_to_remove:
                    text_clean = text_clean.replace(remove, '')
                text_clean = text_clean.strip()
                
                if text_clean and not text_clean.isdigit():
                    gp = text_clean

        # Se non è stato specificato un GP
        if not gp or gp.isspace():
            dispatcher.utter_message(
                text=f"Non hai specificato un GP. "
                     f"Ecco i GP disponibili: {', '.join(valid_events)}."
            )
            return []

        # Verifica validità del GP
        try:
            # Cerca la corrispondenza migliore
            gp_lower = gp.lower()
            matching_events = [event for event in valid_events if gp_lower in event.lower()]
            
            if not matching_events:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return []
            
            # Usa il nome esatto del GP
            gp = matching_events[0]
            
        except Exception as e:
            dispatcher.utter_message(text="Si è verificato un errore nella validazione del GP.")
            return []

        # Se il GP è valido ma non abbiamo l'anno, chiediamo l'anno
        if not year:
            dispatcher.utter_message(response="utter_ask_year")
            return [SlotSet("gp", gp)]

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
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Ottieni gli slot esistenti
        gp = None
        year = None
        
        # Verifica se è una nuova domanda sul vincitore o se stiamo rispondendo all'anno
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        intent = latest_message.get('intent', {}).get('name')
        entities = latest_message.get('entities', [])
        
        # Lista di frasi che indicano una nuova domanda sul vincitore
        winner_phrases = [
            'chi ha vinto', 'vincitore', 'chi ha trionfato', 'chi è arrivato primo',
            'dimmi chi ha vinto', 'chi è stato il vincitore', 'chi è il vincitore'
        ]
        
        # Se è una nuova domanda, prendi gli slot solo se non ci sono entities
        if not any(phrase in text for phrase in winner_phrases):
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
        
        # Estrai l'anno dalle entities se presente
        for entity in entities:
            if entity['entity'] == 'year' and entity['value'].isdigit():
                year = entity['value']
                
        # Estrai il GP dalle entities se presente
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
        
        # Se è una risposta con il GP (intent: inform) e non è un anno
        if intent == 'inform' and not text.isdigit():
            # Pulisci il testo da parole comuni
            text_clean = text.strip().lower()
            words_to_remove = [
                'gp', 'gran premio', 'di', 'the', 'nel', year if year else '',
                'grand prix', 'prix', 'gran', 'premio', 'vincitore', 'chi ha vinto',
                'chi è stato', 'chi ha trionfato', 'chi è arrivato primo', 'dimmi chi ha vinto',
                'chi è il vincitore', 'della gara', 'a', 'nel'
            ]
            for word in words_to_remove:
                text_clean = text_clean.replace(word.lower(), '')
            text_clean = text_clean.strip()
            
            if text_clean:
                gp = text_clean
        
        # Se è una risposta con l'anno (intent: inform)
        if intent == 'inform' and text.isdigit():
            year = text
        
        # Se abbiamo sia GP che anno, procedi con la ricerca
        if gp and year and str(year).isdigit():
            return self.get_winner(dispatcher, gp, year)
        
        # Se non abbiamo il GP, chiediamolo
        if not gp:
            dispatcher.utter_message(text="Per quale GP vuoi informazioni?")
            return [SlotSet("year", year)] if year and str(year).isdigit() else []
        
        # Se non abbiamo l'anno, chiediamolo
        if not year or not str(year).isdigit():
            dispatcher.utter_message(response="utter_ask_year")
            return [SlotSet("gp", gp)]
        
        return []

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
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Usa fuzzy matching per trovare il GP più simile
            gp_lower = gp.lower()
            best_match = process.extractOne(gp_lower, valid_events, scorer=fuzz.ratio)
            
            if best_match and best_match[1] > 60:  # Se la similarità è > 60%
                matched_gp = best_match[0]
                # Trova il round number per il GP corrispondente
                for _, row in schedule.iterrows():
                    if row['EventName'] == matched_gp:
                        round_number = row['RoundNumber']
                        break
                
                print(f"GP validation - Best match: {matched_gp}, Similarity: {best_match[1]}%, Round: {round_number}")
            else:
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
            
            # Estrai le informazioni del vincitore
            winner_name = f"{winner['givenName']} {winner['familyName']}"
            team_name = winner['constructorName']
            grid_position = winner['grid']
            laps = winner['laps']
            nationality = winner['driverNationality']
            avg_speed = winner['fastestLapAvgSpeed']
            
            # Rimuovi "0 days" dai tempi
            total_time = str(winner['totalRaceTime']).replace('0 days ', '')
            fastest_lap = str(winner['fastestLapTime']).replace('0 days ', '')
            
            # Costruisci il messaggio di risposta
            message = (
                f"Il vincitore del GP di {matched_gp} nel {year} è stato {winner_name} ({nationality}) del team {team_name}.\n"
                f"È partito dalla {grid_position}ª posizione, ha completato {laps} giri "
                f"con un tempo totale di {total_time}.\n"
                f"Il suo giro più veloce è stato {fastest_lap} "
                f"con una velocità media di {avg_speed:.3f} km/h."
            )
            
            dispatcher.utter_message(text=message)
            return [SlotSet("gp", matched_gp), SlotSet("year", year)]

        except Exception as e:
            print(f"\nError in get_winner:")
            print(f"Type: {type(e)}")
            print(f"Message: {str(e)}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            dispatcher.utter_message(text=f"Mi dispiace, si è verificato un errore nel recupero delle informazioni.")
        return []

class ActionGetWeatherInfo(Action):
    def name(self) -> str:
        return "action_get_weather_info"

    def get_session_identifier(self, session_name: str) -> str:
        session_mapping = {
            'gara': 'R',
            'race': 'R',
            'qualifiche': 'Q',
            'qualifica': 'Q',
            'qualifying': 'Q',
            'sprint': 'S',
            'prove libere 1': 'FP1',
            'fp1': 'FP1',
            'prove libere 2': 'FP2',
            'fp2': 'FP2',
            'prove libere 3': 'FP3',
            'fp3': 'FP3',
            'sprint shootout': 'SQ'
        }
        return session_mapping.get(session_name.lower() if session_name else None, 'R')

    def get_available_sessions(self, year: str, gp: str) -> list:
        try:
            event = fastf1.get_event(int(year), gp)
            available_sessions = []
            
            session_names = {
                'FP1': 'Prove Libere 1',
                'FP2': 'Prove Libere 2',
                'FP3': 'Prove Libere 3',
                'Q': 'Qualifiche',
                'S': 'Sprint',
                'SQ': 'Sprint Shootout',
                'R': 'Gara'
            }
            
            for session_type in ['FP1', 'FP2', 'FP3', 'SQ', 'Q', 'S', 'R']:
                try:
                    session = fastf1.get_session(int(year), gp, session_type)
                    if session and session.date:
                        available_sessions.append(session_names[session_type])
                except:
                    continue
            
            return available_sessions
        except:
            return []

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Get slots and entities
        latest_message = tracker.latest_message
        text = latest_message.get('text', '').lower()
        intent = latest_message.get('intent', {}).get('name')
        entities = latest_message.get('entities', [])
        
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")
        session_name = tracker.get_slot("session")
        
        # Estrai entità dal messaggio
        for entity in entities:
            if entity['entity'] == 'gp':
                gp = entity['value']
            elif entity['entity'] == 'year':
                year = entity['value']
            elif entity['entity'] == 'session':
                session_name = entity['value']

        # Se è una risposta con l'anno
        if intent == 'inform' and text.isdigit():
            year = text
            if gp:  # Se abbiamo già il GP
                if not session_name:  # Se non abbiamo la sessione, mostra tutte le sessioni disponibili
                    available_sessions = self.get_available_sessions(year, gp)
                    if available_sessions:
                        dispatcher.utter_message(
                            text=f"Per il GP di {gp} nel {year} sono disponibili queste sessioni:\n" +
                                 "\n".join(f"- {session}" for session in available_sessions) +
                                 "\nPer quale sessione vuoi le informazioni meteo?"
                        )
                        return [SlotSet("year", year), SlotSet("gp", gp)]
                return self.get_weather_info(dispatcher, gp, year, session_name)
            return [SlotSet("year", year)]

        # Se è una risposta con una sessione
        if intent == 'inform' and not text.isdigit() and gp and year:
            session_input = text.strip().lower()
            available_sessions = self.get_available_sessions(year, gp)
            
            # Verifica se la sessione richiesta è disponibile
            session_found = False
            matched_session = None
            
            for available_session in available_sessions:
                if session_input == available_session.lower() or session_input in available_session.lower():
                    matched_session = available_session
                    session_found = True
                    break
            
            if not session_found:
                dispatcher.utter_message(
                    text=f"Mi dispiace, la sessione '{text.strip()}' non è disponibile per il GP di {gp} nel {year}.\n"
                         f"Le sessioni disponibili sono:\n" +
                         "\n".join(f"- {session}" for session in available_sessions)
                )
                return [SlotSet("year", year), SlotSet("gp", gp)]
            
            try:
                session_id = self.get_session_identifier(matched_session)
                session = fastf1.get_session(int(year), gp, session_id)
                session.load()
                
                weather_info = self.get_weather_details(session)
                response = f"Condizioni meteo durante la {matched_session} del GP di {gp} nel {year}:\n{weather_info}"
                
                dispatcher.utter_message(text=response)
                return []
                
            except Exception as e:
                dispatcher.utter_message(text=f"Mi dispiace, non riesco a trovare i dati meteo per questa sessione.")
                print(f"Errore: {str(e)}")
                return [SlotSet("year", year), SlotSet("gp", gp)]

        # Se non abbiamo il GP, chiediamolo
        if not gp:
            dispatcher.utter_message(text="Per quale GP vuoi informazioni?")
            return [SlotSet("year", year), SlotSet("session", session_name)] if year or session_name else []

        # Se non abbiamo l'anno, chiediamolo
        if not year:
            dispatcher.utter_message(response="utter_ask_year")
            return [SlotSet("gp", gp), SlotSet("session", session_name)] if gp or session_name else []

        # Se abbiamo GP e anno ma non la sessione, mostra le sessioni disponibili
        if not session_name:
            available_sessions = self.get_available_sessions(year, gp)
            if available_sessions:
                dispatcher.utter_message(
                    text=f"Per il GP di {gp} nel {year} sono disponibili queste sessioni:\n" +
                         "\n".join(f"- {session}" for session in available_sessions) +
                         "\nPer quale sessione vuoi le informazioni meteo?"
                )
                return [SlotSet("year", year), SlotSet("gp", gp)]

        return self.get_weather_info(dispatcher, gp, year, session_name)

    def get_weather_info(self, dispatcher: CollectingDispatcher, gp: str, year: str, session_name: str = None):
        try:
            session_id = self.get_session_identifier(session_name)
            session = fastf1.get_session(int(year), gp, session_id)
            session.load()
            
            weather_info = self.get_weather_details(session)
            session_type = session_name if session_name else "gara"
            response = f"Condizioni meteo durante la {session_type} del GP di {gp} nel {year}:\n{weather_info}"
            
            dispatcher.utter_message(text=response)
            return []
            
        except Exception as e:
            dispatcher.utter_message(text=f"Mi dispiace, non riesco a trovare i dati meteo per questa sessione. "
                                        f"Verifica che il GP e la sessione esistano per l'anno selezionato.")
            print(f"Errore: {str(e)}")
            return []

    def get_weather_details(self, session) -> str:
        weather = session.weather_data
        if weather.empty:
            return "Dati meteo non disponibili per questa sessione."
        
        temp_avg = weather['AirTemp'].mean()
        humidity_avg = weather['Humidity'].mean()
        pressure_avg = weather['Pressure'].mean()
        track_temp_avg = weather['TrackTemp'].mean()
        wind_speed_avg = weather['WindSpeed'].mean()
        
        # Calcola la direzione del vento predominante
        wind_dir = weather['WindDirection'].mode().iloc[0] if not weather['WindDirection'].empty else None
        wind_dir_text = self.get_wind_direction_text(wind_dir) if wind_dir is not None else "N/A"
        
        # Verifica se c'è stata pioggia
        rain = "Sì" if weather['Rainfall'].any() else "No"
        
        return (f"Temperatura aria: {temp_avg:.1f}°C\n"
                f"Temperatura pista: {track_temp_avg:.1f}°C\n"
                f"Umidità: {humidity_avg:.1f}%\n"
                f"Pressione: {pressure_avg:.1f} mbar\n"
                f"Vento: {wind_speed_avg:.1f} m/s, direzione {wind_dir_text}\n"
                f"Pioggia: {rain}")

    def get_wind_direction_text(self, degrees: int) -> str:
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / (360 / len(directions))) % len(directions)
        return f"{degrees}° ({directions[index]})"



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
