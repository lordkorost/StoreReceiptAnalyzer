PROMPT_OCR_DEFAULT ="""
Estrai TUTTO il testo dallo scontrino, riga per riga, dall'alto verso il basso.

REGOLE FONDAMENTALI:
1. NON interpretare, NON riassumere, NON modificare.
2. UNISCI NOME E PREZZO: Se vedi un nome prodotto a sinistra e un prezzo a destra sulla STESSA riga visiva, 
   mettili sulla STESSA riga di output separati da spazio. 
   Esempio: "DANETTE CREMA DESS 4,58" NON "DANETTE CREMA DESS\n4,58"
3. Includi TUTTO: nomi prodotti, prezzi, quantità, sconti, footer, ecc.
4. Separa ogni riga con un a capo (\n).
5. Non aggiungere testo tuo, solo quello presente nell'immagine.

Rispondi SOLO con il testo estratto dallo scontrino, nient'altro.
"""

PROMPT_ANALISI_DEFAULT = """
        Analizza questo testo normalizzato da uno scontrino e estrai tutti gli articoli in formato JSON.

        IL TESTO È GIÀ NORMALIZZATO NEL FORMATO STANDARD:
        [Quantità] [Prezzo Unitario] | [Nome Prodotto] [Prezzo Totale] [| Sconto]

        REGOLE DI PARSING:

        1. SE c'è "N PZ x E. PREZZO" o "N x PREZZO" o "N Kg x PREZZO" PRIMA della "|":
        → quantita = N
        → prezzo_unitario = PREZZO
        → Esempio: "2 PZ x E. 6,99 | ALGIDA CORNETTO 13,98"
            → quantita=2, prezzo_unitario=6.99, nome="ALGIDA CORNETTO", prezzo_totale=13.98

        2. SE c'è "VALORE Kg x E. PREZZO" PRIMA della "|":
        → quantita = VALORE (in Kg, può essere decimale)
        → prezzo_unitario = PREZZO
        → Esempio: "5,480 Kg x E. 1,00 | BANCO SALUMI 5,48"
            → quantita=5.48, prezzo_unitario=1.00, nome="BANCO SALUMI", prezzo_totale=5.48

        3. SE NON c'è nulla PRIMA della "|" (solo "| NOME PREZZO"):
        → quantita = 1
        → prezzo_unitario = prezzo_totale
        → Esempio: "| DAILY PANE SEGALE 1,99"
            → quantita=1, prezzo_unitario=1.99, nome="DAILY PANE SEGALE", prezzo_totale=1.99

        4. SE c'è una seconda "|" con "SCONTO", "Taglio Prezzo", "sc.", ecc.:
        → sconto = valore assoluto (senza il segno meno)
        → Esempio: "*BOUNTY X4 3,99 | Taglio Prezzo -1,00"
            → quantita=1, prezzo_unitario=3.99, nome="*BOUNTY X4", prezzo_totale=3.99, sconto=1.00

        5. SE NON c'è la seconda "|":
        → sconto = 0.0

        REGOLE CRITICHE:
        - Il "prezzo_totale" DEVE essere ESATTAMENTE come appare dopo il nome
        - NON sottrarre lo sconto dal prezzo_totale
        - Se il nome contiene "X3", "X4" ecc., è PARTE DEL NOME (non è la quantità)
        - Ignora righe come "SUBTOTALE", "TOTALE COMPLESSIVO", "CASSA"

        Rispondi SOLO con un array JSON valido, senza markdown e senza spiegazioni:
        [
        {
            "nome": "ALGIDA CORNETTO CIÖCC",
            "quantita": 2,
            "prezzo_unitario": 6.99,
            "sconto": 0.0,
            "prezzo_totale": 13.98
        }
        ]

        Testo da analizzare:
        """ 

PROMPT_CATEGORIZZAZIONE_DEFAULT = """
Devi assegnare una categoria agli articoli.
Puoi scegliere SOLO tra queste categorie:
__CATEGORIE__

Articoli:
__ARTICOLI__

Regole:
- Non creare nuove categorie.
- Usa esclusivamente gli id categoria forniti.
- Rispondi solamente con JSON valido.

Formato risposta:

[
    {
        "articolo_id": 10,
        "categoria_id": 2
    }
]
"""


OCR_MODEL_DEFAULT = "qwen2.5vl:7b"
ANALISI_MODEL_DEFAULT="gpt-oss:20b"
CATEGORIZZAZIONE_MODEL_DEFAULT="gpt-oss:20b"
CHAT_MODEL_DEFAULT ="qwen2.5-coder:7b"