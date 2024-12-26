from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from fastf1.ergast import Ergast
from fuzzywuzzy import fuzz, process
import fastf1
from rasa_sdk.events import SlotSet
from typing import Dict, Any, List, Text
import sys
import os
import io
import pandas as pd
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.types import DomainDict

from dotenv import load_dotenv
import os
import requests
import logging

# Carica le variabili d'ambiente
load_dotenv()

# Recupera i token
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Usa i token nel tuo codice
print(f"Slack Bot Token: {SLACK_BOT_TOKEN}")
print(f"Slack Signing Secret: {SLACK_SIGNING_SECRET}")

import asyncio
asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())

logger = logging.getLogger(__name__)

class ActionGetCircuitInfo(Action):
    def name(self) -> str:
        return "action_get_circuit_info"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        # Evita esecuzioni multiple controllando l'ultima azione
        if tracker.latest_action_name == self.name():
            return []
            
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
            # Modifica URL per usare HTTPS invece di HTTP
            url = "https://ergast.com/api/f1/2023/circuits.json"
            
            # Configura la sessione con headers appropriati
            session = requests.Session()
            session.headers.update({
                'User-Agent': 'Mozilla/5.0',
                'Accept': 'application/json'
            })
            
            # Fai la richiesta con la sessione configurata
            response = session.get(url, timeout=15, verify=True)
            logger.debug(f"Status code: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            
            if response.status_code != 200:
                logger.error(f"API returned status code {response.status_code}")
                raise requests.exceptions.RequestException(f"API returned status code {response.status_code}")
            
            # Converti la risposta JSON in un formato simile al DataFrame
            data = response.json()
            circuits = data['MRData']['CircuitTable']['Circuits']
            
            # Cerca il circuito
            circuit_name_lower = circuit_name.lower().strip()
            filtered_circuits = [
                c for c in circuits 
                if circuit_name_lower in c['circuitName'].lower()
            ]
            
            # Se non trova corrispondenze
            if not filtered_circuits:
                valid_circuits = sorted(c['circuitName'] for c in circuits)
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{circuit_name}' non è un circuito valido. "
                         f"Ecco i circuiti disponibili: {', '.join(valid_circuits)}."
                )
                return []

            # Se trova una corrispondenza
            circuit = filtered_circuits[0]
            response = (
                f"Il circuito '{circuit['circuitName']}' si trova a {circuit['Location']['locality']}, "
                f"{circuit['Location']['country']}.\n"
                f"Coordinate: latitudine {circuit['Location']['lat']}, "
                f"longitudine {circuit['Location']['long']}."
            )
            dispatcher.utter_message(text=response)
            return []

        except requests.exceptions.Timeout:
            logger.error("Timeout nella richiesta all'API Ergast")
            dispatcher.utter_message(
                text="Mi dispiace, il servizio sta impiegando troppo tempo a rispondere. "
                     "Riprova tra qualche minuto."
            )
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore di rete nell'API Ergast: {e}")
            dispatcher.utter_message(
                text="Mi dispiace, il servizio è temporaneamente non disponibile. "
                     "Riprova tra qualche minuto."
            )
            return []
        except Exception as e:
            logger.error(f"Errore generico: {e}")
            dispatcher.utter_message(
                text="Si è verificato un errore nel recupero delle informazioni. "
                     "Riprova più tardi."
            )
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
        # Verifica che l'intent sia quello corretto
        if tracker.latest_message['intent']['name'] != "ask_event_schedule":
            return []

        try:
            # Verifica l'intent corrente
            current_intent = tracker.latest_message.get('intent', {}).get('name')
            
            # Ottieni gli slot
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
            
            # Controlla le entities del messaggio corrente
            entities = tracker.latest_message.get('entities', [])
            for entity in entities:
                if entity['entity'] == 'gp':
                    gp = entity['value']
                if entity['entity'] == 'year':
                    year = entity['value']
                    
            # Se riceviamo solo un numero nel messaggio, è probabilmente l'anno
            if not entities and tracker.latest_message.get('text', '').strip().isdigit():
                year = tracker.latest_message.get('text').strip()

            # Verifica se il GP è valido
            if gp:
                ergast = Ergast()
                races = ergast.get_race_schedule(int(year) if year else 2023)
                available_gps = [race['raceName'] for race in races]
                
                if gp not in available_gps:
                    message = f"Mi dispiace, ma '{gp}' non è un GP valido. Ecco i GP disponibili: {', '.join(available_gps)}."
                    dispatcher.utter_message(text=message)
                    return [SlotSet("gp", None), SlotSet("year", None)]

            # Se l'intent è ask_event_schedule, procedi con la logica del programma
            if current_intent == 'ask_event_schedule':
                # Se abbiamo il GP ma non l'anno
                if gp and not year:
                    dispatcher.utter_message(text="Per quale anno vuoi sapere il programma?")
                    return [SlotSet("gp", gp)]
                
                # Se abbiamo entrambi i valori
                if gp and year:
                    schedule = fastf1.get_event(int(year), gp)
                    if schedule is None:
                        dispatcher.utter_message(text=f"Non ho trovato il programma per il GP di {gp} nel {year}")
                        return [SlotSet("gp", None), SlotSet("year", None)]

                    message = f"Programma del GP di {gp} nel {year}:\n"
                    message += f"Prove Libere 1: {schedule['Session1Date'].strftime('%d %B %Y, %H:%M')}\n"
                    message += f"Prove Libere 2: {schedule['Session2Date'].strftime('%d %B %Y, %H:%M')}\n"
                    message += f"Prove Libere 3: {schedule['Session3Date'].strftime('%d %B %Y, %H:%M')}\n"
                    message += f"Qualifiche: {schedule['Session4Date'].strftime('%d %B %Y, %H:%M')}\n"
                    message += f"Gara: {schedule['Session5Date'].strftime('%d %B %Y, %H:%M')}"

                    dispatcher.utter_message(text=message)
                    return [SlotSet("gp", None), SlotSet("year", None)]

        except Exception as e:
            dispatcher.utter_message(text=f"Si è verificato un errore: {str(e)}")
            return [SlotSet("gp", None), SlotSet("year", None)]
        
        return []


class ActionGetRaceWinner(Action):
    def name(self) -> str:
        return "action_get_race_winner"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        if tracker.latest_message['intent']['name'] != "ask_race_winner":
            return []
            
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
            
            # Costruisci il messaggio di risposta SENZA il giro veloce
            message = (
                f"Il vincitore del GP di {matched_gp} nel {year} è stato {winner_name} ({nationality}) del team {team_name}.\n"
                f"È partito dalla {grid_position}ª posizione, ha completato {laps} giri "
                f"con un tempo totale di {total_time}."
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
        print(f"DEBUG - get_session_identifier - Input session_name: {session_name}", flush=True)
        sys.stdout.flush()
        
        session_mapping = {
            'gara': 'R',
            'race': 'R',
            'qualifiche': 'Q',
            'qualifica': 'Q',
            'qualifying': 'Q',
            'sprint': 'S',
            'prove libere 1': 'FP1',
            'prove libere 2': 'FP2',
            'prove libere 3': 'FP3',
            'sprint shootout': 'SQ'
        }
        
        if not session_name:
            print("DEBUG - session_name is None or empty, returning 'R'", flush=True)
            sys.stdout.flush()
            return 'R'
        
        session_id = session_mapping.get(session_name.lower(), session_name)
        print(f"DEBUG - Mapped session_id: {session_id}", flush=True)
        sys.stdout.flush()
        return session_id

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
        if tracker.latest_message['intent']['name'] != "ask_weather_info":
            return []
            
        try:
            # Get slots and entities
            latest_message = tracker.latest_message
            text = latest_message.get('text', '').lower()
            intent = latest_message.get('intent', {}).get('name')
            entities = latest_message.get('entities', [])
            
            # Ottieni i valori attuali degli slot
            gp = tracker.get_slot("gp")
            year = tracker.get_slot("year")
            
            print(f"DEBUG - Initial slots: gp={gp}, year={year}")
            print(f"DEBUG - Latest message: {text}")
            print(f"DEBUG - Intent: {intent}")
            print(f"DEBUG - Entities: {entities}")
            
            # Salva il valore originale dell'anno
            original_year = year
            
            # Estrai solo le entità pertinenti
            for entity in entities:
                if entity['entity'] == 'gp':
                    gp = entity['value']
                    print(f"DEBUG - Found GP entity: {gp}")
                elif entity['entity'] == 'year':
                    year = entity['value']
                    print(f"DEBUG - Found year entity: {year}")
            
            # Ripristina l'anno originale se non è stata trovata una nuova entità year
            if not any(entity['entity'] == 'year' for entity in entities):
                year = original_year
            
            print(f"DEBUG - After entity extraction: gp={gp}, year={year}")

            # Se non abbiamo il GP, chiediamolo
            if not gp:
                print("DEBUG - No GP found, asking for it")
                dispatcher.utter_message(text="Per quale GP vuoi sapere le informazioni meteorologiche?")
                return [SlotSet("year", year)] if year else []

            # Se non abbiamo l'anno, chiediamolo
            if not year:
                print("DEBUG - No year found, asking for it")
                dispatcher.utter_message(text=f"Per quale anno vuoi sapere le condizioni meteo del GP di {gp}?")
                return [SlotSet("gp", gp)]

            # Se abbiamo entrambi GP e anno, procedi con il recupero dei dati meteo
            if gp and year:
                try:
                    print(f"DEBUG - Attempting to get available sessions for GP={gp}, year={year}")
                    available_sessions = self.get_available_sessions(year, gp)
                    print(f"DEBUG - Available sessions: {available_sessions}")
                    
                    if available_sessions:
                        # Ottieni il riepilogo meteo del weekend
                        print("DEBUG - Getting weather summary")
                        weekend_summary = self.get_gp_weather_summary(year, gp)
                        response = weekend_summary + "\nDETTAGLI PER SESSIONE:\n"

                        # Ottieni i dati meteo per ogni sessione
                        for session_name in available_sessions:
                            try:
                                session_type = self.get_session_identifier(session_name)
                                print(f"DEBUG - Processing session {session_name} (type: {session_type})")
                                session = fastf1.get_session(int(year), gp, session_type)
                                session.load()
                                
                                weather_info = self.get_weather_details(session)
                                response += f"\n{session_name}:\n{weather_info}\n"
                                response += "-" * 40 + "\n"
                                
                            except Exception as e:
                                print(f"DEBUG - Error getting weather for session {session_name}: {str(e)}")
                                response += f"\n{session_name}: Dati meteo non disponibili\n"
                                response += "-" * 40 + "\n"

                        dispatcher.utter_message(text=response)
                        return [SlotSet("gp", gp), SlotSet("year", year)]
                    else:
                        print(f"DEBUG - No available sessions found for GP={gp}, year={year}")
                        dispatcher.utter_message(text=f"Mi dispiace, non trovo sessioni disponibili per il GP di {gp} nel {year}.")
                        return []

                except Exception as e:
                    print(f"DEBUG - General error: {str(e)}")
                    dispatcher.utter_message(text=f"Mi dispiace, c'è stato un errore nel recupero dei dati meteo.")
                    return []

            return [SlotSet("gp", gp), SlotSet("year", year)]
        except Exception as e:
            print(f"Error: {str(e)}")
            return [SlotSet("gp", None), SlotSet("year", None)]

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
        
        # Valori medi
        temp_avg = weather['AirTemp'].mean()
        temp_min = weather['AirTemp'].min()
        temp_max = weather['AirTemp'].max()
        
        track_temp_avg = weather['TrackTemp'].mean()
        track_temp_min = weather['TrackTemp'].min()
        track_temp_max = weather['TrackTemp'].max()
        
        humidity_avg = weather['Humidity'].mean()
        humidity_min = weather['Humidity'].min()
        humidity_max = weather['Humidity'].max()
        
        pressure_avg = weather['Pressure'].mean()
        
        wind_speed_avg = weather['WindSpeed'].mean()
        wind_speed_max = weather['WindSpeed'].max()
        
        # Direzione del vento predominante
        wind_dir = weather['WindDirection'].mode().iloc[0] if not weather['WindDirection'].empty else None
        wind_dir_text = self.get_wind_direction_text(wind_dir) if wind_dir is not None else "N/A"
        
        # Verifica se c'è stata pioggia
        rain = "Sì" if weather['Rainfall'].any() else "No"
        
        return (f"Temperatura aria: {temp_avg:.1f}°C (min: {temp_min:.1f}°C, max: {temp_max:.1f}°C)\n"
                f"Temperatura pista: {track_temp_avg:.1f}°C (min: {track_temp_min:.1f}°C, max: {track_temp_max:.1f}°C)\n"
                f"Umidità: {humidity_avg:.1f}% (min: {humidity_min:.1f}%, max: {humidity_max:.1f}%)\n"
                f"Pressione: {pressure_avg:.1f} mbar\n"
                f"Vento: media {wind_speed_avg:.1f} m/s (max: {wind_speed_max:.1f} m/s), direzione {wind_dir_text}\n"
                f"Pioggia: {rain}")

    def get_wind_direction_text(self, degrees: int) -> str:
        directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                     "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
        index = round(degrees / (360 / len(directions))) % len(directions)
        return f"{degrees}° ({directions[index]})"

    def get_gp_weather_summary(self, year: str, gp: str) -> str:
        try:
            # Ottieni tutte le sessioni
            available_sessions = self.get_available_sessions(year, gp)
            total_sessions = len(available_sessions)
            sessions_with_rain = 0
            
            # Statistiche temperatura
            all_temps = []
            all_track_temps = []
            all_humidity = []
            all_pressure = []
            all_wind_speeds = []
            
            for session_name in available_sessions:
                try:
                    session_type = self.get_session_identifier(session_name)
                    session = fastf1.get_session(int(year), gp, session_type)
                    session.load()
                    
                    weather = session.weather_data
                    if not weather.empty:
                        # Controlla pioggia
                        if weather['Rainfall'].any():
                            sessions_with_rain += 1
                        
                        # Raccogli tutti i dati meteo
                        all_temps.extend(weather['AirTemp'].tolist())
                        all_track_temps.extend(weather['TrackTemp'].tolist())
                        all_humidity.extend(weather['Humidity'].tolist())
                        all_pressure.extend(weather['Pressure'].tolist())
                        all_wind_speeds.extend(weather['WindSpeed'].tolist())
                        
                except Exception as e:
                    print(f"Errore nel recupero dati per {session_name}: {str(e)}")
                    continue
            
            # Calcola le statistiche del weekend
            rain_percentage = (sessions_with_rain / total_sessions) * 100 if total_sessions > 0 else 0
            
            summary = f"Le informazioni meteorologiche relative al GP di {gp} del {year} sono le seguenti:\n"
            summary += "-" * 40 + "\n"
            summary += "RIEPILOGO DEL WEEKEND:\n"
            summary += f"Temperatura aria: min {min(all_temps):.1f}°C, max {max(all_temps):.1f}°C, media {sum(all_temps)/len(all_temps):.1f}°C\n"
            summary += f"Temperatura pista: min {min(all_track_temps):.1f}°C, max {max(all_track_temps):.1f}°C, media {sum(all_track_temps)/len(all_track_temps):.1f}°C\n"
            summary += f"Umidità: min {min(all_humidity):.1f}%, max {max(all_humidity):.1f}%, media {sum(all_humidity)/len(all_humidity):.1f}%\n"
            summary += f"Pressione: min {min(all_pressure):.1f} mbar, max {max(all_pressure):.1f} mbar, media {sum(all_pressure)/len(all_pressure):.1f} mbar\n"
            summary += f"Velocità vento: min {min(all_wind_speeds):.1f} m/s, max {max(all_wind_speeds):.1f} m/s, media {sum(all_wind_speeds)/len(all_wind_speeds):.1f} m/s\n"
            summary += f"Sessioni con pioggia: {sessions_with_rain} su {total_sessions} ({rain_percentage:.1f}%)\n"
            summary += "-" * 40 + "\n"
            
            return summary
            
        except Exception as e:
            print(f"Errore nel calcolo del riepilogo meteo: {str(e)}")
            return f"Mi dispiace, non è stato possibile calcolare il riepilogo meteo del GP di {gp} del {year}."



class ActionGetFastestLap(Action):
    def name(self) -> Text:
        return "action_get_fastest_lap"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        
        # Ottieni i valori degli slot dalla form
        gp = tracker.get_slot("gp")
        year = tracker.get_slot("year")
        
        # Se l'azione è già stata eseguita per questi slot, non ripetere
        if tracker.get_slot("fastest_lap_done"):
            return []
        
        try:
            year_int = int(year)
            # Ottieni la lista dei GP validi per quell'anno
            schedule = fastf1.get_event_schedule(year_int)
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            # Usa fuzzy matching per trovare il GP più simile
            gp_lower = gp.lower()
            best_match = process.extractOne(gp_lower, valid_events, scorer=fuzz.ratio)
            
            if best_match and best_match[1] > 60:  # Se la similarità è > 60%
                matched_gp = best_match[0]
                session = fastf1.get_session(year_int, matched_gp, 'R')
                session.load(laps=True, telemetry=False, weather=False)
                
                fastest_lap = session.laps.pick_fastest()
                if not fastest_lap.empty and 'LapTime' in fastest_lap and 'DriverNumber' in fastest_lap:
                    driver_number = fastest_lap['DriverNumber']
                    driver_info = session.get_driver(driver_number)
                    driver_name = f"{driver_info['FirstName']} {driver_info['LastName']}"
                    lap_time = fastest_lap['LapTime']
                    
                    if hasattr(lap_time, 'total_seconds'):
                        seconds = lap_time.total_seconds()
                    else:
                        seconds = float(lap_time)
                        
                    minutes = int(seconds // 60)
                    remaining_seconds = seconds % 60
                    response = f"Il giro più veloce nel GP di {matched_gp} del {year} è stato fatto da {driver_name} con {minutes}:{remaining_seconds:.3f}"
                    dispatcher.utter_message(text=response)
                else:
                    dispatcher.utter_message(text="Non ho trovato giri validi per questa gara.")
            else:
                dispatcher.utter_message(
                    text=f"Mi dispiace, ma '{gp}' non è un GP valido per il {year}. "
                         f"Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                
            # Alla fine dell'esecuzione, imposta il flag
            return [SlotSet("gp", None), 
                    SlotSet("year", None), 
                    SlotSet("fastest_lap_done", True)]
                
        except Exception as e:
            print(f"Errore dettagliato: {str(e)}")
            dispatcher.utter_message(text="Mi dispiace, non sono riuscito a trovare le informazioni per questo GP.")
            return [SlotSet("gp", None), 
                    SlotSet("year", None), 
                    SlotSet("fastest_lap_done", True)]
        
        return []

class ActionCompareTelemetry(Action):
    def name(self) -> str:
        return "action_compare_telemetry"

    def create_telemetry_plot(self, fastest_driver_1, fastest_driver_2, driver_1, driver_2, gp, year):
        import fastf1.plotting
        from matplotlib import pyplot as plt
        from fastf1 import utils
        
        # Get telemetry data
        telemetry_driver_1 = fastest_driver_1.get_telemetry().add_distance()
        telemetry_driver_2 = fastest_driver_2.get_telemetry().add_distance()
        
        # Calculate delta time
        delta_time, ref_tel, compare_tel = utils.delta_time(fastest_driver_1, fastest_driver_2)
        
        # Get team colors
        session = fastest_driver_1.session
        driver_1_num = fastest_driver_1['DriverNumber']
        driver_2_num = fastest_driver_2['DriverNumber']
        team_driver_1 = session.get_driver(driver_1_num)['TeamName']
        team_driver_2 = session.get_driver(driver_2_num)['TeamName']
        color_driver_1 = fastf1.plotting.team_color(team_driver_1)
        color_driver_2 = fastf1.plotting.team_color(team_driver_2)
        
        # Create plot
        plt.style.use('dark_background')
        fig = plt.figure(figsize=(16, 20))
        gs = plt.GridSpec(7, 1, height_ratios=[1, 3, 2, 1, 1, 2, 1], hspace=0.4)
        ax = []
        for i in range(7):
            ax.append(fig.add_subplot(gs[i]))
        
        # Set title
        plot_title = f"{year} {gp} - Qualifying - {driver_1} VS {driver_2}"
        fig.suptitle(plot_title, y=0.98, fontsize=16)
        
        # Delta time
        ax[0].plot(ref_tel['Distance'], delta_time)
        ax[0].axhline(0)
        ax[0].set(ylabel=f"Gap to {driver_1} (s)")
        
        # Speed
        ax[1].plot(telemetry_driver_1['Distance'], telemetry_driver_1['Speed'], label=driver_1, color=color_driver_1)
        ax[1].plot(telemetry_driver_2['Distance'], telemetry_driver_2['Speed'], label=driver_2, color=color_driver_2)
        ax[1].set(ylabel='Speed')
        ax[1].legend(loc="lower right")
        
        # Throttle
        ax[2].plot(telemetry_driver_1['Distance'], telemetry_driver_1['Throttle'], label=driver_1, color=color_driver_1)
        ax[2].plot(telemetry_driver_2['Distance'], telemetry_driver_2['Throttle'], label=driver_2, color=color_driver_2)
        ax[2].set(ylabel='Throttle')
        ax[2].legend(loc="lower right")
        
        # Brake
        ax[3].plot(telemetry_driver_1['Distance'], telemetry_driver_1['Brake'], label=driver_1, color=color_driver_1)
        ax[3].plot(telemetry_driver_2['Distance'], telemetry_driver_2['Brake'], label=driver_2, color=color_driver_2)
        ax[3].set(ylabel='Brake')
        ax[3].legend(loc="lower right")
        
        # Gear
        ax[4].plot(telemetry_driver_1['Distance'], telemetry_driver_1['nGear'], label=driver_1, color=color_driver_1)
        ax[4].plot(telemetry_driver_2['Distance'], telemetry_driver_2['nGear'], label=driver_2, color=color_driver_2)
        ax[4].set(ylabel='Gear')
        ax[4].legend(loc="lower right")
        
        # RPM
        ax[5].plot(telemetry_driver_1['Distance'], telemetry_driver_1['RPM'], label=driver_1, color=color_driver_1)
        ax[5].plot(telemetry_driver_2['Distance'], telemetry_driver_2['RPM'], label=driver_2, color=color_driver_2)
        ax[5].set(ylabel='RPM')
        ax[5].legend(loc="lower right")
        
        # DRS
        ax[6].plot(telemetry_driver_1['Distance'], telemetry_driver_1['DRS'], label=driver_1, color=color_driver_1)
        ax[6].plot(telemetry_driver_2['Distance'], telemetry_driver_2['DRS'], label=driver_2, color=color_driver_2)
        ax[6].set(ylabel='DRS')
        ax[6].set(xlabel='Distance (meters)')
        ax[6].legend(loc="lower right")
        
        # Add grid to all subplots
        for axis in ax:
            axis.grid(color='grey', linestyle='-', linewidth=0.5)
            axis.tick_params(axis='both', which='major', labelsize=10)
            axis.yaxis.label.set_size(12)
        
        # Aumenta la dimensione della label dell'asse x
        ax[6].xaxis.label.set_size(12)
        
        # Save plot to static folder
        plot_filename = f"telemetry_{gp}_{year}_{driver_1}_{driver_2}.png"
        plot_path = os.path.join("static", "images", plot_filename)
        os.makedirs(os.path.dirname(plot_path), exist_ok=True)
        plt.savefig(plot_path, dpi=300, bbox_inches='tight', 
                    facecolor=fig.get_facecolor(), edgecolor='none',
                    pad_inches=0.5)
        plt.close()
        return plot_filename

    def generate_telemetry_comparison(self, year: str, gp: str, driver_1: str, driver_2: str) -> str:
        try:
            print(f"\nDEBUG - Starting telemetry comparison with params:")
            print(f"Year: {year}, GP: {gp}, Driver 1: {driver_1}, Driver 2: {driver_2}")
            
            # Load session
            session = fastf1.get_session(int(year), gp, 'Q')
            session.load()
            
            # Get list of drivers in the session
            drivers = session.drivers
            print(f"\nDEBUG - Drivers type: {type(drivers)}")
            print(f"DEBUG - Drivers content: {drivers}")
            
            # Crea un dizionario per mappare sia i cognomi che le abbreviazioni ai numeri dei piloti
            driver_info = {}
            for driver_number in drivers:
                info = session.get_driver(driver_number)
                print(f"\nDEBUG - Driver info for {driver_number}:")
                print(f"Raw info: {info}")
                
                if info is not None:
                    try:
                        driver_info[info['LastName']] = driver_number
                        driver_info[info['Abbreviation']] = driver_number
                        print(f"Processed: {info['LastName']} / {info['Abbreviation']} -> {driver_number}")
                    except Exception as e:
                        print(f"Error processing driver info: {str(e)}")
                        print(f"Info keys available: {info.keys() if hasattr(info, 'keys') else 'No keys'}")
            
            # Check if both drivers were in the session
            if driver_1 not in driver_info:
                available_drivers = sorted(set(info['LastName'] for d in drivers if (info := session.get_driver(d)) is not None))
                raise ValueError(f"{driver_1} non ha partecipato a questo GP. Piloti disponibili: {', '.join(available_drivers)}")
            if driver_2 not in driver_info:
                available_drivers = sorted(set(info['LastName'] for d in drivers if (info := session.get_driver(d)) is not None))
                raise ValueError(f"{driver_2} non ha partecipato a questo GP. Piloti disponibili: {', '.join(available_drivers)}")
            
            # Il resto del codice rimane invariato
            driver_1_num = driver_info[driver_1]
            driver_2_num = driver_info[driver_2]
            
            # Get laps
            laps_driver_1 = session.laps.pick_driver(driver_1_num)
            laps_driver_2 = session.laps.pick_driver(driver_2_num)
            
            # Get fastest laps
            fastest_driver_1 = laps_driver_1.pick_fastest()
            fastest_driver_2 = laps_driver_2.pick_fastest()
            
            # Check if both drivers have valid fastest laps
            if fastest_driver_1.empty or fastest_driver_2.empty:
                raise ValueError("Non sono disponibili giri validi per il confronto")
            
            # Get plot filename
            plot_filename = self.create_telemetry_plot(fastest_driver_1, fastest_driver_2, driver_1, driver_2, gp, year)
            
            return plot_filename
            
        except ValueError as ve:
            print(f"Error in telemetry comparison: {str(ve)}")
            raise ve
        except Exception as e:
            print(f"Unexpected error in telemetry comparison: {str(e)}")
            raise ValueError("Si è verificato un errore nel recupero dei dati telemetrici")

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        try:
            gp = tracker.get_slot("gp")
            driver_1 = tracker.get_slot("driver_1")
            driver_2 = tracker.get_slot("driver_2")
            year = tracker.get_slot("year")
            
            print(f"DEBUG - Initial slots: gp={gp}, driver_1={driver_1}, driver_2={driver_2}, year={year}")
            
            # Se l'intent è inform, verifica se stiamo aspettando l'anno
            latest_intent = tracker.latest_message.get('intent', {}).get('name')
            if latest_intent == 'inform':
                # Estrai l'anno dal messaggio
                text = tracker.latest_message.get('text', '')
                try:
                    year = int(text)
                except ValueError:
                    pass

            # Se manca qualche dato necessario, chiedi all'utente
            if not all([gp, driver_1, driver_2, year]):
                if not year:
                    dispatcher.utter_message(response="utter_ask_year")
                    return []
                return []

            try:
                # Get plot filename
                plot_filename = self.generate_telemetry_comparison(year, gp, driver_1, driver_2)
                plot_path = os.path.join("static", "images", plot_filename)
                
                # Check if the channel is Telegram
                input_channel = tracker.get_latest_input_channel()
                
                if input_channel == "telegram":
                    # For Telegram, send the file directly
                    dispatcher.utter_message(
                        text=f"Ecco il confronto telemetrico tra {driver_1} e {driver_2} nel GP di {gp} {year}",
                        image=plot_path  # Telegram può gestire path locali
                    )
                else:
                    # For other channels, use URL
                    dispatcher.utter_message(
                        text=f"Ecco il confronto telemetrico tra {driver_1} e {driver_2} nel GP di {gp} {year}",
                        image=f"http://localhost:5005/static/images/{plot_filename}"
                    )
            except ValueError as ve:
                dispatcher.utter_message(text=f"Mi dispiace, {str(ve)}.")
            except Exception as e:
                dispatcher.utter_message(text="Mi dispiace, si è verificato un errore inaspettato.")
                print(f"Unexpected error: {str(e)}")
            return []
        except Exception as e:
            dispatcher.utter_message(text="Mi dispiace, si è verificato un errore nel processare la richiesta.")
            print(f"Error in run method: {str(e)}")
            return []

class ActionShowSpeedMap(Action):
    def name(self) -> str:
        return "action_show_speed_map"

    def create_speed_map(self, session, driver, gp, year):
        print(f"DEBUG - Creating speed map for {driver} at {gp} {year}")
        import fastf1.plotting
        from matplotlib import pyplot as plt
        import numpy as np
        from matplotlib.collections import LineCollection
        import matplotlib as mpl
        
        # Get driver number/code
        drivers = session.drivers
        driver_info = {}
        for d in drivers:
            info = session.get_driver(d)
            driver_info[info['LastName']] = d           # es. "Verstappen" -> "33"
            driver_info[info['Abbreviation']] = d  # es. "VER" -> "33"
        
        if driver not in driver_info:
            raise ValueError(f"{driver} non ha partecipato a questo GP")
            
        driver_num = driver_info[driver]
        print(f"DEBUG - Driver number: {driver_num}")
        
        # Get weekend info
        weekend = session.event
        print(f"DEBUG - Weekend info: {weekend}")
        
        # Get fastest lap for the driver
        driver_laps = session.laps.pick_driver(driver_num)
        print(f"DEBUG - Driver laps: {driver_laps}")
        
        if driver_laps.empty:
            raise ValueError(f"Nessun dato disponibile per {driver} in questa sessione")
            
        fastest_lap = driver_laps.pick_fastest()
        if fastest_lap is None or fastest_lap.empty:
            raise ValueError(f"Nessun giro veloce disponibile per {driver}")
        
        # Get telemetry data
        x = fastest_lap.telemetry['X']              # values for x-axis
        y = fastest_lap.telemetry['Y']              # values for y-axis
        color = fastest_lap.telemetry['Speed']      # value to base color gradient on
        
        if x.isnull().all() or y.isnull().all() or color.isnull().all():
            raise ValueError(f"Dati di posizione o velocità non disponibili per {driver}")
        
        # Create line segments
        points = np.array([x, y]).T.reshape(-1, 1, 2)
        segments = np.concatenate([points[:-1], points[1:]], axis=1)
        
        # Create plot
        fig, ax = plt.subplots(sharex=True, sharey=True, figsize=(12, 6.75))
        fig.suptitle(f'{weekend.name} {year} - {driver} - Speed', size=24, y=0.97)
        
        # Adjust margins and turn off axis
        plt.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.12)
        ax.axis('off')
        
        # Create background track line
        ax.plot(fastest_lap.telemetry['X'], fastest_lap.telemetry['Y'],
                color='black', linestyle='-', linewidth=16, zorder=0)
        
        # Create a continuous norm to map from data points to colors
        norm = plt.Normalize(color.min(), color.max())
        lc = LineCollection(segments, cmap='plasma', norm=norm,
                          linestyle='-', linewidth=5)
        
        # Set the values used for colormapping
        lc.set_array(color)
        
        # Merge all line segments together
        line = ax.add_collection(lc)
        
        # Create a color bar as a legend
        cbaxes = fig.add_axes([0.25, 0.05, 0.5, 0.05])
        normlegend = mpl.colors.Normalize(vmin=color.min(), vmax=color.max())
        legend = mpl.colorbar.ColorbarBase(cbaxes, norm=normlegend, cmap='plasma',
                                         orientation="horizontal")
        legend.set_label('Speed (km/h)', size=12)
        
        # Save plot
        plot_filename = f"speed_map_{gp}_{year}_{driver}.png"
        plot_path = os.path.join("static", "images", plot_filename)
        os.makedirs(os.path.dirname(plot_path), exist_ok=True)
        plt.savefig(plot_path, dpi=300, bbox_inches='tight',
                   facecolor='white', edgecolor='none')
        plt.close()
        
        return plot_filename

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: dict) -> list:
        try:
            gp = tracker.get_slot("gp")
            driver = tracker.get_slot("driver")
            year = tracker.get_slot("year")
            
            print(f"DEBUG - Slots: gp={gp}, driver={driver}, year={year}")
            
            if not all([gp, driver, year]):
                if not year:
                    dispatcher.utter_message(response="utter_ask_year")
                return []
            
            try:
                # Get event to find weekend number
                event = fastf1.get_event(int(year), gp)
                print(f"DEBUG - Event: {event}")
                
                if event is None:
                    raise ValueError(f"Evento non trovato per il GP di {gp} nel {year}")
                
                weekend_number = event['RoundNumber']
                print(f"DEBUG - Weekend number: {weekend_number}")
                
                # Load race session
                session = fastf1.get_session(int(year), weekend_number, 'R')
                print(f"DEBUG - Session loaded: {session}")
                session.load()
                
                # Create speed map
                plot_filename = self.create_speed_map(session, driver, gp, year)
                print(f"DEBUG - Plot filename: {plot_filename}")
                plot_path = os.path.join("static", "images", plot_filename)
                
                # Check channel and send image
                input_channel = tracker.get_latest_input_channel()
                if input_channel == "telegram":
                    dispatcher.utter_message(
                        text=f"Ecco la mappa delle velocità di {driver} nella gara del GP di {gp} {year}",
                        image=plot_path
                    )
                else:
                    dispatcher.utter_message(
                        text=f"Ecco la mappa delle velocità di {driver} nella gara del GP di {gp} {year}",
                        image=f"http://localhost:5005/static/images/{plot_filename}"
                    )
                return []
                
            except Exception as e:
                print(f"DEBUG - Error details: {str(e)}")
                print(f"DEBUG - Error type: {type(e)}")
                dispatcher.utter_message(text=f"Mi dispiace, non sono disponibili dati di velocità per {driver} nella gara del GP di {gp} {year}")
                
        except Exception as e:
            dispatcher.utter_message(text="Mi dispiace, si è verificato un errore nel processare la richiesta.")
            print(f"Error: {str(e)}")
            
        return []

class ActionResetSlots(Action):
    def name(self) -> Text:
        return "action_reset_slots"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        return [SlotSet("gp", None), SlotSet("year", None)]

class ValidateFastestLapForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_fastest_lap_form"

    def validate_gp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            # Verifica che il GP sia valido
            schedule = fastf1.get_event_schedule(2023)
            valid_events = sorted([event['EventName'] for _, event in schedule.iterrows()])
            
            best_match = process.extractOne(slot_value.lower(), valid_events, scorer=fuzz.ratio)
            if best_match and best_match[1] > 60:
                return {"gp": best_match[0]}
            else:
                dispatcher.utter_message(
                    text=f"'{slot_value}' non è un GP valido. Ecco i GP disponibili: {', '.join(valid_events)}."
                )
                return {"gp": None}
        except Exception as e:
            dispatcher.utter_message(text="Si è verificato un errore nella validazione del GP.")
            return {"gp": None}

    def validate_year(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            year = int(slot_value)
            if 1950 <= year <= 2024:
                return {"year": str(year)}
            else:
                dispatcher.utter_message(text=f"Per favore inserisci un anno tra 1950 e 2024.")
                return {"year": None}
        except ValueError:
            dispatcher.utter_message(text="Per favore inserisci un anno valido.")
            return {"year": None}

class ValidateTelemetryForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_telemetry_form"

    def validate_driver_1(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        # Verifica che il pilota sia valido
        if slot_value:
            return {"driver_1": slot_value}
        return {"driver_1": None}

    def validate_driver_2(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value:
            return {"driver_2": slot_value}
        return {"driver_2": None}

    def validate_gp(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        if slot_value:
            return {"gp": slot_value}
        return {"gp": None}

    def validate_year(
        self,
        slot_value: Any,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: DomainDict,
    ) -> Dict[Text, Any]:
        try:
            year = int(slot_value)
            if 1950 <= year <= 2024:
                return {"year": str(year)}
            else:
                dispatcher.utter_message(text=f"Per favore inserisci un anno tra 1950 e 2024.")
                return {"year": None}
        except ValueError:
            dispatcher.utter_message(text="Per favore inserisci un anno valido.")
            return {"year": None}
