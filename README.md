# Progetto Data Science 2024/2025

Repository Github per il progetto del corso di Data Science tenuto dal Prof. Domenico Ursino durante l'anno accademico 2024/2025 presso l'Università Politecnica delle Marche.

# Attivazione ambiente virtuale conda:

```bash
conda activate ChatBot
```

# Se il modello non è trainato:

```bash
rasa train
```

# Runnare le actions

```bash
rasa run actions
```

# Per parlare con il chatbot (porta 5006):

```bash
rasa shell --port 5006
```

# Con un chatbot per il calcio, puoi implementare una vasta gamma di funzionalità basate sull'analisi e sulla presentazione di dati calcistici. Ecco una panoramica delle possibili analisi, organizzata per categoria:

---

### **1. Analisi delle Partite**
- **Risultati Recenti**:
  - Mostrare i risultati delle ultime partite di una squadra o di un campionato.
  - Es.: "Qual è stato l'ultimo risultato del Milan?"

- **Calendario Partite**:
  - Fornire il programma delle partite future per una squadra o competizione.
  - Es.: "Quando gioca il Napoli?"

- **Statistiche di Partita**:
  - Analizzare statistiche dettagliate di una specifica partita, come possesso palla, tiri, passaggi.
  - Es.: "Statistiche della partita Milan vs Inter."

---

### **2. Analisi dei Campionati**
- **Classifiche**:
  - Mostrare la classifica aggiornata di un campionato o torneo.
  - Es.: "Qual è la classifica della Serie A?"

- **Capocannonieri**:
  - Elenco dei migliori marcatori di un campionato o torneo.
  - Es.: "Chi è il capocannoniere della Premier League?"

- **Analisi Storiche**:
  - Mostrare statistiche storiche del campionato, come i vincitori delle ultime edizioni.
  - Es.: "Chi ha vinto la Champions League nel 2019?"

---

### **3. Analisi delle Squadre**
- **Statistiche Squadra**:
  - Fornire statistiche su gol fatti, gol subiti, rendimento in casa e fuori casa.
  - Es.: "Statistiche della Juventus in questa stagione."

- **Formazione**:
  - Mostrare l'elenco dei giocatori o la probabile formazione per la prossima partita.
  - Es.: "Chi gioca nel Real Madrid?"

- **Rendimento Storico**:
  - Analisi del rendimento negli ultimi anni.
  - Es.: "Quanti scudetti ha vinto l'Inter?"

---

### **4. Analisi dei Giocatori**
- **Statistiche Individuali**:
  - Fornire dati sui gol segnati, assist, ammonizioni, espulsioni.
  - Es.: "Quanti gol ha segnato Haaland questa stagione?"

- **Carriera Giocatore**:
  - Riassumere la carriera di un giocatore, inclusi i club e i titoli vinti.
  - Es.: "Qual è la carriera di Lionel Messi?"

- **Confronti tra Giocatori**:
  - Mettere a confronto due giocatori su statistiche come gol, assist, o performance.
  - Es.: "Chi è meglio tra Ronaldo e Messi?"

---

### **5. Analisi dei Tornei**
- **Statistiche Torneo**:
  - Informazioni sui gol totali, squadre partecipanti, media gol per partita.
  - Es.: "Quante squadre partecipano alla Champions League?"

- **Fase a Eliminazione**:
  - Aggiornamenti sui progressi delle squadre nei tornei a eliminazione diretta.
  - Es.: "Chi gioca in semifinale dei Mondiali?"

---

### **6. Analisi in Tempo Reale**
- **Aggiornamenti Live**:
  - Fornire aggiornamenti in tempo reale su gol, ammonizioni, o altri eventi.
  - Es.: "Cosa sta succedendo nella partita Milan-Napoli?"

- **Notifiche Personalizzate**:
  - Configurare il chatbot per inviare notifiche sui gol o eventi delle squadre preferite.
  - Es.: "Avvisami quando la Juventus segna."

---

### **7. Analisi Storica**
- **Record e Statistiche Storiche**:
  - Elencare record, come i migliori marcatori o le squadre con più trofei.
  - Es.: "Chi ha vinto più scudetti in Italia?"

- **Confronto tra Generazioni**:
  - Comparare squadre o giocatori di epoche diverse.
  - Es.: "La squadra del Barcellona 2009 è migliore del Real Madrid 2023?"

---

### **8. Analisi di Mercato**
- **Trasferimenti Recenti**:
  - Informazioni sugli acquisti e le vendite delle squadre.
  - Es.: "Chi ha comprato il Chelsea quest'anno?"

- **Valore di Mercato**:
  - Analizzare il valore di mercato di un giocatore o di una squadra.
  - Es.: "Qual è il valore di Mbappé?"

---

### **9. Analisi Utente-Centriche**
- **Quiz sul Calcio**:
  - Proporre domande per testare la conoscenza calcistica dell'utente.
  - Es.: "Chi ha segnato più gol nella Serie A 2022-23?"

- **Suggerimenti Personalizzati**:
  - Raccomandare partite o notizie basate sulle preferenze dell'utente.
  - Es.: "Consigliami una partita interessante da guardare oggi."

---

### **10. Analisi Predittive**
- **Previsioni Partite**:
  - Mostrare previsioni sui risultati basate su statistiche.
  - Es.: "Chi vincerà tra Barcellona e Bayern Monaco?"

- **Previsioni di Classifica**:
  - Calcolare la posizione finale in base alle prestazioni attuali.
  - Es.: "Il Milan può arrivare in Champions League quest'anno?"

---

### **11. Integrazioni Avanzate**
- **Integrazione con API esterne**:
  - Collegare il chatbot ad API come `Football Data API` o `SportRadar` per arricchire i dati.
- **Supporto per più lingue**:
  - Rendere il chatbot multilingue per utenti internazionali.

---

Se desideri implementare una di queste analisi o aggiungere funzionalità, posso aiutarti a svilupparle nel tuo chatbot! 😊
