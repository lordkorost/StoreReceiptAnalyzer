import json
from pathlib import Path
import re
import psycopg2
import os
import threading
import requests
import ollama
from decimal import Decimal
from datetime import datetime, date
from dotenv import load_dotenv, find_dotenv


# Il percorso della cartella in cui si trova worker.py 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Il percorso della cartella media di Django (src/analizzascontrini/webui/media)
MEDIA_PATH = os.path.normpath(os.path.join(BASE_DIR, '../webui/media'))

# ==========================================================
# 1. LOADING (.env)
# ==========================================================
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
    # print(f" Configurazione caricata da: {env_path}")
else:
    print("[WORKER-HELPERS] .env file not found. Using default values.")

# ==========================================================
# 2.  DATABASE (PostgreSQL)
# ==========================================================
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'analizzascontrini_db'),
    'user': os.getenv('DB_USER', 'analizzascontrini_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
}

# ==========================================================
# DJANGO_EVENT_URL
# ==========================================================
DJANGO_EVENT_URL = (
    f"http://{os.getenv('AS_HOST', 'localhost')}:"
    f"{os.getenv('AS_PORT', '8000')}"
    "/api/internal/events/"
)

# ==========================================================
# 3. CONFIGURAZIONE OLLAMA
# ==========================================================
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
client = ollama.Client(host=OLLAMA_HOST)



def get_db_connection():
    """Create a connection to the PostgreSQL database."""
    return psycopg2.connect(**DB_CONFIG)

#send django event
def send_event_to_django(task_id, status, progress=0, error=None, step=None):
    payload = {
        "task_id": task_id,
        "status": status,
        "progress": progress,
        "error": error,
        "step": step
    }

    def send():
        try:
            requests.post(
                DJANGO_EVENT_URL,
                json=payload,
                timeout=(1,2)
            )
        except Exception as e:
            print(f"[WORKER ERROR] Django notification error: {e}")

    threading.Thread(
        target=send,
        daemon=True
    ).start()

#update task and send django event
def update_task(cursor, conn, task_id, status, progress=0, error=None, step=None):

    cursor.execute(
        "UPDATE spese_task SET status = %s, error = %s, progress = %s, step = %s WHERE id = %s;", 
        (status, error, progress, step, task_id)
    )
    conn.commit()
    

    send_event_to_django(
        task_id=task_id, 
        status=status, 
        progress=progress, 
        error=error, 
        step=step
    )

def pre_check_ollama(config, requested_models):
    """
    Verifies that Ollama is reachable and that the required models are present.
    
    Args:
        config: Dictionary containing the user's AI configuration (from get_user_ai_config)
        requested_models: List of model names to verify (e.g., ['qwen2.5vl:7b'])
    
    Returns:
        (True, None) if everything is fine
        (False, error_message) if there is a problem
    """
    host = config['ollama_host']
    
    try:
        # Short timeout: 3 seconds. If Ollama doesn't respond, it's better to know right away.
        response = requests.get(f"{host}/api/tags", timeout=3)
        
        if response.status_code != 200:
            return False, f"Ollama ({host}) responded with status {response.status_code}"
        
        models_data = response.json().get('models', [])
        available_models = [m['name'] for m in models_data]
        
        # Check that all the required forms are present.
        missing_models = [m for m in requested_models if m not in available_models]
        
        if missing_models:
            # To avoid making the message too long, we are showing only the first 10 available models.
            short_list = ", ".join(available_models[:10])
            if len(available_models) > 10:
                short_list += f" ... e altri {len(available_models) - 10}"
            
            return False, (
                f"Missing models on Ollama: {', '.join(missing_models)}. "
                f"Go to AI Settings to change the models."
                f"available_models {short_list}"
            )
        
        return True, None
        
    except requests.exceptions.Timeout:
        return False, f"Timeout: Ollama ({host}) is not responding within 3 seconds. Check that it is running."
    except requests.exceptions.ConnectionError:
        return False, f"Unable to connect to Ollama ({host}). Check the IP and firewall."
    except Exception as e:
        return False, f"Error during Ollama check: {str(e)}"


###########################################################
#                   TASK OCR EXTRACTION                   #
###########################################################
def retrieve_receipt(cursor, conn, receipt_id):
    """
    Retrieve the receipt from the PostgreSQL database.
    With RealDictCursor, `row` is already a dictionary.
    """
    #print(f"[DEBUG retrieve_receipt] receipt_id: {receipt_id}")
    query = """
        SELECT 
            id,
            user_id,
            created_at,
            receipt_date,
            ocr_store_name,
            store_id,
            image,
            total,
            confirmed
        FROM spese_receipt
        WHERE id = %s
    """
    
    try:
        cursor.execute(query, (receipt_id,))
        row = cursor.fetchone()
        
        if row:
            scontrino_dict = dict(row)
            
            #print(f"[DEBUG retrieve_receipt] receipt_dict: {scontrino_dict}")
            
            # Handle only None values.
            if scontrino_dict.get('total') is None:
                scontrino_dict['total'] = Decimal('0.00')
            
            return scontrino_dict
        return None
    except Exception as e:
        print(f"[WORKER] Database error retrieving receipt: {e}")
        return None

def get_user_ai_config(cursor, user_id):
    """
    Reads the user's AI configuration from the database.
    If a field is empty, it returns the default value.
    """
    cursor.execute("""
        SELECT ollama_host, ocr_model, analysis_model, categorization_model,chat_model,
               ocr_prompt, analysis_prompt, categorization_prompt
        FROM spese_useraiconfig
        WHERE user_id = %s
    """, (user_id,))
    
    row = cursor.fetchone()
    
    # default 
    default_ocr = 'qwen2.5vl:7b'
    default_analisi = 'gpt-oss:20b'
    default_cat = 'gpt-oss:20b'
    default_chat = 'gpt-oss:20b'
    default_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')

    if row:
        config_dict = dict(row)
        
        return {
            # get() row name + strip and fallback
            'ollama_host': (config_dict.get('ollama_host') or '').strip() or default_host,
            'ocr_model': (config_dict.get('ocr_model') or '').strip() or default_ocr,
            'analysis_model': (config_dict.get('analysis_model') or '').strip() or default_analisi,
            'categorization_model': (config_dict.get('categorization_model') or '').strip() or default_cat,
            'chat_model': (config_dict.get('chat_model') or '').strip() or default_chat,
            # Prompts can be None
            'ocr_prompt': config_dict.get('ocr_prompt'),
            'analysis_prompt': config_dict.get('analysis_prompt'),
            'categorization_prompt': config_dict.get('categorization_prompt')
        }
    else:
        # Fallback
        return {
            'ollama_host': default_host,
            'ocr_model': default_ocr,
            'analysis_model': default_analisi,
            'categorization_model': default_cat,
            'chat_model': default_chat,
            'ocr_prompt': None,
            'analysis_prompt': None,
            'categorization_prompt': None
        }

def run_ocr(img_receipt,prompt,model):
    try:
        response = client.chat(
            model = model,
            messages=[{
                'role': 'user', 
                'content': prompt, 
                'images': [img_receipt]
            }],
            options={
                'temperature': 0.1,  
                'num_ctx': 32768,
                'num_predict': 8192,
                'seed': 42
            }
        )
        
        excerpt_text = response['message']['content']
        
        # # PRINT DEBUG
        # print("\n" + "="*20 + "OCR TEXT " + "="*20)
        # print(excerpt_text)
        # print("="*68 + "\n")
        # # FINE PRINT DEBUG

        if not excerpt_text or len(excerpt_text.strip()) < 10:
            raise Exception("The model returned an empty or overly brief response.")
        
        return excerpt_text
    
    except Exception as e:
        print(f"[WORKER ERROR] OCR failed: {e}")
        return None

def get_store_template_from_db(cursor, conn, store_id):
    """Retrieve the template from the PostgreSQL database with all fields."""
    #print(f"[DEBUG get_template_from_db] store_id = {store_id}")
    query = """
        SELECT 
            id,
            user_id,
            name,
            keyword,
            prompt_instruction,
            quantity_regex,
            ignored_lines,
            discount_regex,
            remove_vat_pattern,
            store_keywords,
            repeated_items
        FROM spese_storetemplate
        WHERE id = %s
    """
    
    try:
        cursor.execute(query, (store_id,))
        row = cursor.fetchone()
       
        if not row:
            print(f"[DEBUG get_template_from_db] Template not found!")
            return None
        
        template = dict(row)
        
        for campo_json in ['ignored_lines', 'store_keywords']:
            value = template.get(campo_json)
            if value is None:
                template[campo_json] = []
           
            elif isinstance(value, str):
                try:
                    template[campo_json] = json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    template[campo_json] = []
        
      
        template['repeated_items'] = bool(template.get('repeated_items', False))
        
        return template
        
    except Exception as e:
        print(f"Database error retrieving template: {e}")
        return None

def configurable_ocr_normalization_it(ocr_text, store_template):
    #TODO - Make normalizer headers configurable

    # - item_start_keywords
    # - subtotal_keywords
    # - total_keywords
    # - remove hardcoded DESCRIPTION/SUBTOTAL/TOTAL from the code
    # - support multiple keywords per item
    # - keep configuration simple (lists of strings, not regex)
    
    """
    Generic normalizer that uses configuration from the database.
    """
    righe = ocr_text.strip().split('\n')
    risultato = []
    
    regex_quantita = store_template.get('quantity_regex')
    regex_sconti = store_template.get('discount_regex')
    pattern_rimuovi_iva = store_template.get('remove_vat_pattern')
    righe_da_ignorare = store_template.get('ignored_lines') or []
    parole_chiave_negozio = store_template.get('store_keywords') or []
    
    def pulisci_riga(riga):
        # Remove VAT/VI* using the configured regex.
        if pattern_rimuovi_iva:
            riga = re.sub(pattern_rimuovi_iva, '', riga)
        # Correct OCR errors (G → 0) It also corrects 50G to 500 (TODO:FIX)
        riga = re.sub(r'([\d,]+)G', r'\g<1>0', riga)
        return riga.strip()
    
    # Find the store name using the configured keywords
    nome_negozio = None
    for riga in righe:
        riga_strip = riga.strip()
        if any(keyword in riga_strip.lower() for keyword in parole_chiave_negozio):
            nome_negozio = riga_strip
            break
    
    if nome_negozio:
        risultato.append(f"NEGOZIO: {nome_negozio}")
    
    # find date
    data_scontrino = None
    for riga in righe:
        data_match = re.search(r'(\d{2}[-/]\d{2}[-/]\d{4})', riga)
        if data_match:
            data_scontrino = data_match.group(1).replace('/', '-')
            break
    
    if data_scontrino:
        risultato.append(f"DATA: {data_scontrino}")
    
    risultato.append("")
    
    # Find the beginning of the articles
    inizio_articoli = 0
    for i, riga in enumerate(righe):
        if 'DESCRIZIONE' in riga or 'Descrizione' in riga:
            inizio_articoli = i + 1
            break
    
    # Process the items
    i = inizio_articoli
    while i < len(righe):
        riga = pulisci_riga(righe[i])
        
        # Skip lines to ignore
        if any(pattern in riga for pattern in righe_da_ignorare):
            i += 1
            continue
        
        # SUBTOTALE / TOTALE COMPLESSIVO
        if 'SUBTOTALE' in riga:
            match = re.search(r'SUBTOTALE\s+([\d,]+)', riga)
            if match:
                risultato.append(f"SUBTOTALE: {match.group(1)}")
            i += 1
            continue
        
        if 'TOTALE COMPLESSIVO' in riga or 'Totale Complessivo' in riga:
            match = re.search(r'(?:TOTALE COMPLESSIVO|Totale Complessivo)\s+([\d,]+)', riga)
            if match:
                risultato.append(f"TOTALE COMPLESSIVO: {match.group(1)}")
                break
            i += 1
            continue
        
        # Salta righe vuote
        # if not riga:
        #     i += 1
        #     continue
        # Salta righe vuote
        if not riga:
            i += 1
            continue
        
        # Skip lines containing mathematical calculations (e.g., "2.89 - 0.60 = 2.29")
        # if re.match(r'^[\d,]+\s*-\s*[\d,]+\s*=\s*[\d,]+$', riga):
        if re.match(r'^\d+(?:[.,]\d+)?\s*-\s*\d+(?:[.,]\d+)?\s*=\s*\d+(?:[.,]\d+)?$',riga):
            print(f"[DEBUG] Salto calcolo matematico: '{riga}'")
            i += 1
            continue
        
        # Recognize quantity lines using the configured regex
        qty_match = re.match(regex_quantita, riga, re.IGNORECASE) if regex_quantita else None
        if qty_match:
            if i + 2 < len(righe):
                nome_riga = pulisci_riga(righe[i + 1])
                prezzo_riga = pulisci_riga(righe[i + 2])
                
                # If the third line is a number, it is the price.
                if re.match(r'^\d+(?:[.,]\d+)?$', prezzo_riga):
                    risultato.append(f"{riga} | {nome_riga} | {prezzo_riga}")
                    i += 3
                    continue
                # Otherwise, the second line already contains the price.
                elif re.search(r'[\d,]+$', nome_riga):
                    risultato.append(f"{riga} | {nome_riga}")
                    i += 2
                    continue
            
            # Fallback: take only the next line
            if i + 1 < len(righe):
                nome_prezzo = pulisci_riga(righe[i + 1])
                risultato.append(f"{riga} | {nome_prezzo}")
                i += 2
            else:
                risultato.append(riga)
                i += 1
            continue
        
        
        # Apply discounts using the configured regex
        if regex_sconti and re.search(regex_sconti, riga, re.IGNORECASE):
            print(f"[DEBUG SCONTO] Match trovato! riga: '{riga}' | i: {i}")
            
            if risultato:
                # If the line already matches the full regex_sconti, it is an inline discount
                # Example: "(5.78 - disc. 1.20)" → attach directly
                if re.fullmatch(regex_sconti, riga.strip(), re.IGNORECASE):
                    print(f"[DEBUG DISCOUNT] Full inline discount, attachment to: '{risultato[-1]}'")
                    risultato[-1] = risultato[-1] + ' | ' + riga
                    i += 1
                    continue
          
                if re.search(r'-\d+(?:[.,]\d+)?', riga):
                    risultato[-1] = risultato[-1] + ' | ' + riga
                else:
                    if i + 1 < len(righe):
                        prossimo = pulisci_riga(righe[i + 1])
                        #print(f"[DEBUG SCONTO] Prossima riga: '{prossimo}'")
                        if re.match(r'^-\d+(?:[.,]\d+)?$', prossimo):
                            risultato[-1] = risultato[-1] + ' | ' + riga + ' | ' + prossimo
                            i += 2
                            continue
            i += 1
            continue
        
       # Standard product
        risultato.append(riga)
        i += 1
    
    return '\n'.join(risultato)

def extract_receipt_data_llm(normalized_text,model,prompt):
   
    full_prompt = prompt + normalized_text

    response = client.chat(
        # model="gpt-oss:20b",
        model = model,
        messages=[{'role': 'user', 'content': full_prompt}],
        options={
            'temperature': 0.1,
            'num_ctx': 32768
        }
    )

    response_text = response['message']['content']

    # Try json parsing
    try:
        # Rimuove markdown code blocks
        clean_text = response_text.strip()
        if clean_text.startswith('```'):
            clean_text = clean_text.split('\n', 1)[1]
        if clean_text.endswith('```'):
            clean_text = clean_text.rsplit('```', 1)[0]
        
        products = json.loads(clean_text)
        
        return products
    except Exception as e:
        print(f"[WORKER ERROR]: {e}")
        return None

def extract_store_name(ocr_text, template=None):
    """
    Extracts the store name from the OCR text.
    If a template is available, it uses `store_keywords` (more precise).
    Otherwise, it takes the first non-empty line.
    """
    righe = [r.strip() for r in ocr_text.split('\n') if r.strip()]
    
    if not righe:
        return None
    
    if template and template.get('store_keywords'):
        parole_chiave = [p.lower() for p in template['store_keywords']]
        
        # Search within the first 5 lines (the name is usually at the top)
        for riga in righe[:5]:
            riga_lower = riga.lower()
            for parola in parole_chiave:
                if parola in riga_lower:
                    return riga  
    
    # Fallback: first non-empty line (remove strange characters)
    nome = righe[0]
    # Clean up messy OCR characters
    nome = re.sub(r'[^a-zA-ZàèéìòùÀÈÉÌÒÙ\s\-\.]', '', nome).strip()
    return nome if nome else None

def extract_receipt_date_it(ocr_text):
    """
    Extracts the date from OCR text by looking for common Italian patterns.
    Supported formats: dd/mm/yyyy, dd-mm-yyyy, dd.mm.yyyy, dd/mm/yy
    """
    # Pattern for Italian dates (dd/mm/yyyy or similar)
    pattern_data = r'\b(\d{1,2})[\/\-\.\s](\d{1,2})[\/\-\.\s](\d{2,4})\b'
    
    matches = re.findall(pattern_data, ocr_text)
    
    for match in matches:
        giorno, mese, anno = match
        
        # Normalize year (if 2 digits, add 20)
        if len(anno) == 2:
            anno = '20' + anno
        
        try:
            # Validate the date
            data = datetime(int(anno), int(mese), int(giorno))
            
            # Check that it is a reasonable date (not older than 10 years, not in the future)
            oggi = datetime.now()
            if oggi - data < __import__('datetime').timedelta(days=3650) and data <= oggi:
                return data.date()
        except ValueError:
            continue  # Invalid date, try the next one
    
    return None

def extract_total_from_receipt_it(ocr_text):
    """
    Look for the total printed on the receipt for comparison.
    Look for patterns such as "TOTAL 12.34" or "TOT. € 12.34".
    """
    # Pattern for the total (look for "TOTALE" followed by a number)
    pattern_totale = r'(?:TOTALE|TOT\.?|IMP\.?TOT\.?)\s*[:\-]?\s*€?\s*(\d{1,3}(?:[.,]\d{2})?)'
    
    match = re.search(pattern_totale, ocr_text, re.IGNORECASE)
    if match:
        totale_str = match.group(1).replace(',', '.')
        try:
            return float(totale_str)
        except ValueError:
            pass
    
    return None

def save_complete_receipt(cursor, conn, receipt_id, receipt_data):
    """
    Save the complete receipt data to the PostgreSQL database.
    """
    try:
        
        
        # ============================================
        # Type conversion for PostgreSQL
        # ============================================
        totale = Decimal(str(receipt_data.get("total", 0)))
    
        nome_negozio = receipt_data.get("ocr_store_name", "N/A")
        data_str = receipt_data.get("receipt_date")
       
        if data_str and isinstance(data_str, str):
            try:
                data_scontrino = datetime.strptime(data_str, "%Y-%m-%d").date()
            except ValueError:
                try:
                    data_scontrino = datetime.strptime(data_str, "%d-%m-%Y").date()
                except ValueError:
                    data_scontrino = None
        elif isinstance(data_str, date):
            data_scontrino = data_str
        else:
            data_scontrino = None
        
        # 1. Main receipt update
        cursor.execute(
            """
            UPDATE spese_receipt
            SET total = %s,
                ocr_store_name = %s,
                receipt_date = %s
            WHERE id = %s
            """,
            (
                totale,
                nome_negozio,
                data_scontrino,
                receipt_id
            )
        )
       
        
        # 2. INSERT receipt items
        products = receipt_data.get("products", [])
        #print(f"\n Insertion {len(products)} products...")
        
        for idx, articolo in enumerate(products, 1):
            # Explicit conversion to Decimal for monetary fields
            quantita = Decimal(str(articolo.get("quantity", 1)))
            prezzo_unitario = Decimal(str(articolo.get("unit_price", 0)))
            prezzo_totale = Decimal(str(articolo.get("price", 0)))
            sconto = Decimal(str(articolo.get("discount", 0)))
            
            cursor.execute(
                """
                INSERT INTO spese_receiptitem
                (
                    receipt_id,
                    original_text,
                    quantity,
                    unit_price,
                    price,
                    discount
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    receipt_id,
                    articolo.get("name", "").strip(),
                    quantita,
                    prezzo_unitario,
                    prezzo_totale,
                    sconto
                )
            )
            print(f"   {idx}. {articolo.get('name')} - {quantita} pz × {prezzo_unitario}€")
        
        # 3. Commit della transazione
        conn.commit()
       
        
        return True
        
    except Exception as e:
        print(f"\nError while saving")
        print(f"   Errory Type: {type(e).__name__}")
        print(f"   Error: {str(e)}")

        try:
            conn.rollback()
            print(f"   ROLLBACK complete")
        except Exception as rollback_error:
            print(f"   ERROR rollback: {rollback_error}")
        
        return False
    
    finally:
        print("\n" + "=" * 80)



###########################################################
#                   TASK TEST STORE TEMPLATE              #
###########################################################
def save_receipt_test(cursor, conn, receipt_test_id, receipt_data):
    """
    Save the test results to the test tables.
    """
    try:
       
        # 1. Prepare the date
        data_scontrino = receipt_data.get("receipt_date")
        if not data_scontrino:
            data_scontrino = date.today()
            print(f"\n Date not found, using current date: {data_scontrino}")
        
        if isinstance(data_scontrino, datetime):
            data_scontrino = data_scontrino.date()
        elif isinstance(data_scontrino, str):
            # Converts string to date if necessary
            try:
                data_scontrino = datetime.strptime(data_scontrino, "%Y-%m-%d").date()
            except ValueError:
                try:
                    data_scontrino = datetime.strptime(data_scontrino, "%d-%m-%Y").date()
                except ValueError:
                    data_scontrino = date.today()
        
        # 2. UPDATE receipttest
        cursor.execute(
            """
            UPDATE spese_receipttest
            SET total = %s,
                ocr_store_name = %s,
                receipt_date = %s
            WHERE id = %s
            """,
            (
                Decimal(str(receipt_data.get("total", 0))),
                receipt_data.get("ocr_store_name", "N/A"),
                data_scontrino,  
                receipt_test_id
            )
        )
        # print(f"   ✅ Totale: {receipt_data.get('total')}€")
        # print(f"   ✅ Negozio: {receipt_data.get('ocr_store_name')}")
        # print(f"   ✅ Data: {data_scontrino}")
        
        # 3. DELETE prev test items
        cursor.execute("DELETE FROM spese_receipttestitem WHERE receipt_test_id = %s", (receipt_test_id,))
        
        # 4. INSERT test items
        articoli = receipt_data.get("articoli", [])
        
        for idx, articolo in enumerate(articoli, 1):
            cursor.execute(
                """
                INSERT INTO spese_receipttestitem
                (
                    receipt_test_id,
                    original_text,
                    quantity,
                    unit_price,
                    price,
                    discount
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    receipt_test_id,
                    articolo.get("nome", articolo.get("original_text", "")).strip(),
                    Decimal(str(articolo.get("quantita", 1))),
                    Decimal(str(articolo.get("prezzo_unitario", 0))),
                    Decimal(str(articolo.get("prezzo_totale", 0))),
                    Decimal(str(articolo.get("sconto", 0)))
                )
            )
            print(f"   {idx}. {articolo.get('nome')} - {articolo.get('quantita')} pz × {articolo.get('prezzo_unitario')}€")
        
        # 5. Commit
        conn.commit()
        
        return True
        
    except Exception as e:
        print(f"\nError while saving test")
        print(f"   Error type: {type(e).__name__}")
        print(f"   Message: {str(e)}")

        try:
            conn.rollback()
            print(f"   ROLLBACK complete")
        except Exception as rollback_error:
            print(f"   ERROR rollback: {rollback_error}")
        
        return False
    
    finally:
        print("\n" + "=" * 80)
