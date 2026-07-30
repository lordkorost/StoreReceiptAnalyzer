# Template Supermercati di default
SUPERMERCATI_DEFAULT = [
    {
        "nome": "Duepi",
        "parola_chiave": "DUEPI",
        "prompt_instruction": "",
        "regex_quantita": r"^([\d,]+)\s*(?:PZ\s*x\s*E\.?|Kg\s*x\s*E\.?)\s*([\d,]+)",
        "righe_da_ignorare": ["Carta N.:", "TIT.CART S.", "Accumulo Punti"],
        "regex_sconti": "Taglio Prezzo",
        "pattern_rimuovi_iva": r"\s+VI\*",
        "parole_chiave_negozio": ["duepi", "supermercato duepi"],
        "articoli_ripetuti": True
    },
    {
        "nome": "Coop",
        "parola_chiave": "COOP",
        "prompt_instruction": "",
        "regex_quantita": r"^(\d+)\s*PZ\s*x\s*([\d,]+)\s*EUR/PZ",
        "righe_da_ignorare": [],
        "regex_sconti": "SCONTO OFFERTA",
        "pattern_rimuovi_iva": r"\s+\d+(?:,\d+)?%",
        "parole_chiave_negozio": ["ipercoop", "coop"],
        "articoli_ripetuti": True
    },
    {
        "nome": "Sagi",
        "parola_chiave": "SAGI",
        "prompt_instruction": "",
        "regex_quantita": r"^(\d+)\s*x\s*([\d,]+)",
        "righe_da_ignorare": [],
        "regex_sconti": "NESSUNO",
        "pattern_rimuovi_iva": r"\s+\d+,\d+%",
        "parole_chiave_negozio": ["sagi", "cash & carry"],
        "articoli_ripetuti": False
    },
    {
        "nome": "Conad",
        "parola_chiave": "CONAD",
        "prompt_instruction": "",
        "regex_quantita": r"^(\d+)\s*x\s*([\d,]+)$",
        "righe_da_ignorare": [
            "scont* unitario", "Carta insieme", "TOT. ALTRI SCONTI", "ALTRI SCONTI",
            "Pagamento elettronico", "Importo pagato", "DOCUMENTO N.", "VI = Ventilazione",
            "P.I.", "TEL.", "ALCOM", "CORIGLIANO", "ROSSANO", "DESCRIZIONE", "Prezzo(€)", "DOCUMENTO COMMERCIALE"
        ],
        "regex_sconti": r"\(\d+,\d+\s*-\s*sc\.\s*\d+,\d+\)",
        "pattern_rimuovi_iva": r"\s+VI\*",
        "parole_chiave_negozio": ["conad"],
        "articoli_ripetuti": False
    }
]