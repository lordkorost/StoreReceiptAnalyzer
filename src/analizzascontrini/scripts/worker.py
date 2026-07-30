
import time
import os
import json
import requests
import ollama
from datetime import datetime
from psycopg2.extras import RealDictCursor 
from dotenv import load_dotenv, find_dotenv

from analizzascontrini.defaults.ai_settings import PROMPT_ANALISI_DEFAULT, PROMPT_CATEGORIZZAZIONE_DEFAULT, PROMPT_OCR_DEFAULT
from analizzascontrini.scripts.worker_helpers import (get_db_connection, save_receipt_test,
                                                      update_task,retrieve_receipt,
                                                      get_user_ai_config,pre_check_ollama,run_ocr,
                                                      get_store_template_from_db,
                                                      configurable_ocr_normalization_it,
                                                      extract_receipt_data_llm,
                                                      extract_store_name,extract_receipt_date_it, 
                                                      extract_total_from_receipt_it, save_complete_receipt,
                                                      send_event_to_django
                                                      )


# ==========================================================
# INITIAL CONFIG
# ==========================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# django media to find receipt images
MEDIA_PATH = os.path.normpath(os.path.join(BASE_DIR, '../webui/media'))

# ==========================================================
# 1. LOADING .env
# ==========================================================
env_path = find_dotenv()
if env_path:
    load_dotenv(env_path)
    #print(f"✅ Configuration loaded by:{env_path}")
else:
    print("⚠️ .env file not found. Using default values.")

# ==========================================================
# 2. DATABASE (PostgreSQL)
# ==========================================================
DB_CONFIG = {
    'dbname': os.getenv('DB_NAME', 'analizzascontrini_db'),
    'user': os.getenv('DB_USER', 'analizzascontrini_user'),
    'password': os.getenv('DB_PASSWORD', ''),
    'host': os.getenv('DB_HOST', 'localhost'),
    'port': os.getenv('DB_PORT', '5432'),
}

# ==========================================================
# 3. OLLAMA
# ==========================================================
OLLAMA_HOST = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
client = ollama.Client(host=OLLAMA_HOST)

#dispatcher
def search_and_process_task():
    conn = get_db_connection()

    # RealDictCursor to access fields by name (task['id'])
    cursor = conn.cursor(cursor_factory=RealDictCursor)

    #  Select a task 
    cursor.execute("""
        SELECT id, receipt_id, receipt_test_id, task_type 
        FROM spese_task 
        WHERE status = 'PENDING' 
        ORDER BY created_at ASC LIMIT 1
    """)
    task = cursor.fetchone()

    if not task:
        conn.close()
        return

    task_id = task['id']
    receipt_id = task['receipt_id']
    receipt_test_id = task['receipt_test_id'] 
    task_type = task['task_type']

    print(f"\n[*] Dispatcher: Assigned Task #{task_id} of type[{task_type}]")

    try:
        if task_type == 'OCR_EXTRACTION':
            run_ocr_extraction(cursor, conn, task_id, receipt_id)
        elif task_type == 'CATEGORIZATION':
            run_llm_categorization(cursor, conn, task_id, receipt_id)
        #test receipt on store template
        elif task_type == 'STORE_TEMPLATE_TEST':
            run_store_template_test(cursor, conn, task_id, receipt_test_id)
        #check ollama settings/models
        elif task_type == 'OLLAMA_CHECK':  
            run_check_ollama(cursor, conn, task_id)
        #chat with ollama model
        elif task_type == 'CHAT':
            run_chat(cursor, conn, task_id)
        else:
            print(f"[WORKER ERROR] Unknown task type: {task_type}")
            
    except Exception as e:
        print(f"[WORKER ERROR] Exception caught: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        update_task(cursor=cursor, conn=conn, task_id=task_id, status='FAILED', progress=0, error=str(e))


######### TASK 1 OCR - PRODUCT LIST WITH QUANTITY AND DISCOUNTS #########
def run_ocr_extraction(cursor, conn, task_id, receipt_id):
    print(f"[DEBUG OCR] Starting OCR on Receipt: {receipt_id}")
    
    ##receipt data
    scontrino = retrieve_receipt(cursor=cursor, conn=conn, receipt_id=receipt_id)
    
    print(f"[DEBUG OCR] Receipt data: {scontrino}")
    print(f"[DEBUG OCR] Receipt['image']: '{scontrino.get('image')}'")
    cursor.execute(
        """
        SELECT data
        FROM spese_task
        WHERE id = %s
        """,
        (task_id,)
    )

    row = cursor.fetchone()

    if not row:
        print(f"[WORKER] Error: Task {task_id} not found")
        update_task(
            cursor=cursor,
            conn=conn,
            task_id=task_id,
            status="FAILED",
            step="DB_QUERY"
        )
        return

    task_data = row["data"] or {}

    path_img_receipt = task_data.get("image_path")

    print(
        f"[DEBUG OCR] receipt_path_img: {path_img_receipt}"
    )

    # path_img_receipt = os.path.join(MEDIA_PATH, scontrino['image'])
    # print(f"[DEBUG OCR] receipt_path_img: {path_img_receipt}")
   

    # print(f"[WORKER] Start OCR via  Ollama for Task #{task_id}")

    if not scontrino:
        print(f"[WORKER] Error: Receipt {receipt_id} not found")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", step="DB_QUERY")
        return

    # file exists?
    if not scontrino['image'] or not os.path.exists(path_img_receipt):
        print(f"[WORKER] Error: Image not found in {path_img_receipt}")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error="FILE_MISSING")
        return

    # 1. ocr with qwen2.5vl:7b
    user_id = scontrino['user_id']
    print(f"[WORKER] Processing for User ID: {user_id}")
    # 2. Retrieve this user's specific AI configuration.
    config = get_user_ai_config(cursor, user_id)
    
    # 3. Solve the prompt
    ocr_prompt = config['ocr_prompt'] or PROMPT_OCR_DEFAULT
    ocr_model = config['ocr_model']

    # PRE-CHECK OLLAMA
    ok, error = pre_check_ollama(config, [ocr_model])
    if not ok:
        print(f"[WORKER] Pre-check ollama failed: {error}")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error=error, progress=0)
        return
    
    #print(f"[OCR] Using model: {ocr_model}")
    update_task(cursor, conn, task_id, status="PROCESSING", step="Running OCR with Ollama...", progress=30)
    
    # 4. OCR
    ocr_text = run_ocr(
        img_receipt=path_img_receipt,
        model=ocr_model,
        prompt=ocr_prompt
    )

  
    update_task(cursor=cursor,conn=conn,task_id=task_id,status="PROCESSING",progress=50,step="Receipt processing")

  
    store_id = scontrino['store_id']
   
    if store_id:
        #print(f"[WORKER] Store template ID: {store_id}")
        store_template = get_store_template_from_db(cursor,conn,store_id)
        if not store_template:
            update_task(cursor=cursor,conn=conn,task_id=task_id,status="FAILED",progress=0,error="Error retrieving template")
    else:
        update_task(cursor=cursor,conn=conn,task_id=task_id,status="FAILED",progress=0,errore="Error: No store ID")
        return

    
    # #DEBUG
    # if store_template:
    #     print(f"[WORKER] Template loaded: {store_template['name']}")
    #     print(f"[WORKER] Keyword : {store_template['keyword']}")
    #     print(f"[WORKER] Repeated items: {store_template['repeated_items']}")
    #     print(f"[WORKER] Ignored lines: {store_template['ignored_lines']}")
    # #FINE DEBUG

   
    # 5. OCR normalization
    normalized_text = configurable_ocr_normalization_it(ocr_text=ocr_text, store_template=store_template)

    # DEBUG
    print("\n" + "="*80)
    print("TESTO FINALE")
    print("="*80)
    print(normalized_text)
    print("="*80)
    # END DEBUG
    
    analysis_prompt = config['analysis_prompt'] or PROMPT_ANALISI_DEFAULT
    analysis_model = config['analysis_model']


    ok, error = pre_check_ollama(config, [analysis_model])
    if not ok:
        print(f"[WORKER] Pre-check Ollama failed: {error}")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error=error, progress=0)
        return
    #print(f"[ANALYSIS] Use model: {analysis_model}")
    
    # Analysis data extraction
    update_task(cursor=cursor, conn=conn, task_id=task_id, status="PROCESSING", progress=80, step="Receipt data extraction")
    
    products = extract_receipt_data_llm(
        normalized_text=normalized_text,
        model=analysis_model,
        prompt=analysis_prompt
    )
    
    update_task(cursor=cursor,conn=conn,task_id=task_id,status="PROCESSING",progress=80,step="Search Article List")
    # ============================================
    # MAPPING: italian → english
    # ============================================
    # The LLM returns the fields in Italian, but the rest of the code
    # expects the names in English. Perform conversion here.

    def normalize_product(p):
        return {
            "name": p.get("nome", p.get("name", "")),
            "quantity": p.get("quantita", p.get("quantity", 1)),
            "unit_price": p.get("prezzo_unitario", p.get("unit_price", 0.0)),
            "discount": p.get("sconto", p.get("discount", 0.0)),
            "price": p.get("prezzo_totale", p.get("price", 0.0)),
        }

    products = [normalize_product(p) for p in products]

    # Debug articoli
    print("\n" + "="*80)
    print("ARTICOLI ESTRATTI")
    print("="*80)

    totale_calcolato = 0.0
    for idx, art in enumerate(products, 1):
        print(f"\n{idx}. {art['name']}")
        
        if art.get('quantity', 1) > 1:
            print(f"   {art['quantity']} × {art['unit_price']}€ = {art['price']}€")
        else:
            print(f"   Prezzo: {art['price']}€")
        
        if art.get('discount', 0) > 0:
            print(f"   ⚠️ discount: {art['discount']}€")
        
        totale_calcolato += art['price']

    #Total Control Logic (Scenario A vs. Scenario B)
    somma_prezzi_totali = totale_calcolato
    somma_sconti = sum(art.get('discount', 0) for art in products)

    # receipt info
    store_name = extract_store_name(ocr_text, store_template)
    print(f"[DEBUG] extracted store name: {store_name}")
    receipt_date = extract_receipt_date_it(ocr_text)
    receipt_ocr_total = extract_total_from_receipt_it(ocr_text)

    # Scenario check: prices already discounted or yet to be discounted?
    if receipt_ocr_total:
        differenza_senza_sconti = abs(somma_prezzi_totali - receipt_ocr_total)
        differenza_con_sconti = abs((somma_prezzi_totali - somma_sconti) - receipt_ocr_total)
        
        if differenza_senza_sconti < 0.05:
            print("\nScenario A: Prices already discounted (I do not deduct discounts)")
            totale_calcolato = somma_prezzi_totali
        elif differenza_con_sconti < 0.05:
            print(f"\nScenario B: Full prices (I subtract discounts: {somma_sconti:.2f}€)")
            totale_calcolato = somma_prezzi_totali - somma_sconti
        else:
            print(f"\nNo scenario matches perfectly.")
            print(f"   Sum of prices: {somma_prezzi_totali:.2f}€")
            print(f"   Total discounts: {somma_sconti:.2f}€")
            print(f"   Receipt total: {receipt_ocr_total:.2f}€")
            # Fallback: use the nearest one
            if differenza_senza_sconti < differenza_con_sconti:
                totale_calcolato = somma_prezzi_totali
            else:
                totale_calcolato = somma_prezzi_totali - somma_sconti

    # DEBUG PRINT
    # print("\n" + "="*80)
    # print("INFO SCONTRINO")
    # print("="*80)
    # print(f"Negozio: {store_name}")
    # print(f"Data: {receipt_date if receipt_date else 'Not found (will use current date)'}")
    # print(f"Totale calcolato: {totale_calcolato:.2f}€")


    # if receipt_ocr_total:
    #     print(f"Total printed: {receipt_ocr_total:.2f}€")
    #     differenza = abs(totale_calcolato - receipt_ocr_total)
    #     if differenza > 0.05:
    #         print(f"Difference: {differenza:.2f}€")
    #     else:
    #         print(f"Corresponding totals")

    # Prepara il dict per il salvataggio
    receipt_data = {
        "ocr_store_name": store_name,
        "receipt_date": receipt_date,  # None -> date.today()
        "total": totale_calcolato,
        "products": products
    }

    update_task(cursor=cursor, conn=conn, task_id=task_id, status="PROCESSING", progress=90, step="Database backup and completion.")

    # Save on db
    successo = save_complete_receipt(cursor, conn, receipt_id, receipt_data)

    if successo:
        #print("\nReceipt saved successfully!")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="COMPLETED", progress=100)
    else:
        print("\nError while saving")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", progress=100, step="", error="Database save error")


######### TASK 2 CATEGORIZATION FOR PRODUCTS #########
def run_llm_categorization(cursor, conn, task_id, receipt_id):
    print(f"[WORKER] Start Task Categorization #{task_id}")

    try:
        #print("[DEBUG 1] Prima di aggiorna_task (PROCESSING 20%)")
        update_task(cursor=cursor, conn=conn, task_id=task_id,status="PROCESSING", progress=20)

        #print("[DEBUG 2] Dopo aggiorna_task (PROCESSING 20%)")

        cursor.execute("""
            SELECT user_id
            FROM spese_receipt
            WHERE id = %s
        """, (receipt_id,))
        receipt_row = cursor.fetchone()
        
        if not receipt_row:
            raise Exception(f"Scontrino {receipt_id} non trovato")
        
        user_id = receipt_row['user_id'] 
        print(f"[DEBUG 2.5] User ID recuperato: {user_id}")

       
        config = get_user_ai_config(cursor, user_id)
        prompt_cat = config['categorization_prompt'] or PROMPT_CATEGORIZZAZIONE_DEFAULT
        modello_cat = config['categorization_model']
    
        ok, error = pre_check_ollama(config, [modello_cat])
        if not ok:
            print(f"[WORKER] Pre-check fallito: {error}")
            update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error=error, progress=0)
            return
        
        #print(f"[DEBUG 2.6] Modello categorizzazione: {modello_cat}")

        # Retrieving receipt items
        #print(f"[DEBUG 3] Prima della query articoli, scontrino_id={receipt_id}")
        cursor.execute("""
            SELECT DISTINCT
                a.id,
                a.name
            FROM spese_receiptitem v
            JOIN spese_product a
            ON v.product_id = a.id
            WHERE v.receipt_id = %s
            AND a.category_id IS NULL
        """, (receipt_id,))
        #print("[DEBUG 4] Dopo cursor.execute, prima di fetchall")

        articoli = cursor.fetchall()
        #print(f"[DEBUG 5] Dopo fetchall, trovati {len(articoli)} articoli")
        
        print("\n===== ARTICOLI DA CATEGORIZZARE =====")
        for a in articoli:
            print(f"ID: {a['id']} | Nome: {a['name']}")
        print("=====================================\n")

        #print(f"[DEBUG 6] Prima del controllo if not articoli, len={len(articoli)}")
        if not articoli:
            #print("[DEBUG 7] Entrato nel blocco if not articoli")
            print("[CATEGORY] No items to categorize")

            update_task(cursor=cursor, conn=conn, task_id=task_id,
                          status="COMPLETED", progress=100
            )
            #print("[DEBUG 8] Dopo aggiorna_task COMPLETED, prima di return")
            return

        #print("[DEBUG 9] Dopo il controllo if, ci sono articoli da processare")

        # Recupero categorie disponibili
        #print("[DEBUG 10] Prima della query categorie")
        cursor.execute("""
            SELECT id, name
            FROM spese_category
            WHERE user_id = %s
            ORDER BY name
        """, (user_id,))  
        #print("[DEBUG 11] Dopo cursor.execute categorie, prima di fetchall")

        categorie_db = cursor.fetchall()
        #print(f"[DEBUG 12] Dopo fetchall categorie, trovate {len(categorie_db)} categorie")
        
        # print("\n===== CATEGORIE DISPONIBILI =====")
        # for c in categorie_db:
        #     print(f"ID: {c['id']} | Nome: {c['name']}")
        # print("=================================\n")

        categorie = [
            {
                "id": c['id'],
                "nome": c['name']
            }
            for c in categorie_db
        ]
        #print(f"[DEBUG 13] Lista categorie creata: {len(categorie)} elementi")

        lista_articoli = [
            {
                "id": a['id'],
                "nome": a['name']
            }
            for a in articoli
        ]
        #print(f"[DEBUG 14] Lista articoli creata: {len(lista_articoli)} elementi")

  
        prompt = prompt_cat.replace('__CATEGORIE__', json.dumps(categorie, ensure_ascii=False))
        prompt = prompt.replace('__ARTICOLI__', json.dumps(lista_articoli, ensure_ascii=False))

        # print("\n===== PROMPT CATEGORIZZAZIONE =====")
        # print(prompt)
        # print("===================================\n")
        
        # print("[DEBUG 15] Prima di client.generate (chiamata Ollama)")
       
        response = client.generate(
            model=modello_cat,  
            prompt=prompt,
            options={
                "temperature": 0.2,
                'num_ctx': 32768,
            }
        )
        # print("[DEBUG 16] Dopo client.generate, risposta ricevuta")

        raw = response.get("response", "").strip()
        # print(f"[DEBUG 17] Raw response length: {len(raw)}")
        
        # print("\n===== RISPOSTA LLM CATEGORIA =====")
        # print(raw)
        # print("==================================\n")

        # print("[DEBUG 18] Prima di json.loads")
       
        risultati = json.loads(raw)
        # print(f"[DEBUG 19] Dopo json.loads, {len(risultati)} risultati")

        update_task(cursor=cursor, conn=conn, task_id=task_id,
                      status="PROCESSING", progress=70
        )
        # print("[DEBUG 20] Dopo aggiorna_task (PROCESSING 70%)")

    
        for r in risultati:
            product_id = r.get('articolo_id')
            category_id = r.get('categoria_id')
            
            # Safety check: update only if both keys exist
            if product_id and category_id:
                #print(f"[UPDATE] Articolo {product_id} -> Categoria {category_id}")
                
                cursor.execute("""
                    UPDATE spese_product
                    SET category_id = %s
                    WHERE id = %s
                """, (category_id, product_id))
            else:
                print(f"[WARNING] Incomplete LLM result ignored: {r}")
                
        conn.commit()
        # print("[DEBUG 21] Dopo conn.commit")

        update_task(cursor=cursor, conn=conn, task_id=task_id,
                      status="COMPLETED", progress=100
        )
        # print("[DEBUG 22] Dopo aggiorna_task COMPLETED finale")
        print("[WORKER] Categorizzazione completata")

    except Exception as e:
        print(f"[DEBUG EXCEPTION] Exception: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        print("[CATEGORY ERROR]", e)
        update_task(cursor=cursor, conn=conn, task_id=task_id,
                      status="FAILED", progress=0, error=str(e)
        )

######### TASK 3 TEST STORE TEMPLATE  OCR AND ANALYSIS #########
def run_store_template_test(cursor, conn, task_id, receipt_test_id):
    """
    Runs the configuration test for a supermarket.
    Simplified workflow: OCR → Normalizer → Single LLM call
    """
    print(f"[WORKER] Starting TEST Store Template  Task #{task_id}")
    #  debug
    # print(f"[DEBUG] Parametri ricevuti:")
    # print(f"  - task_id: {task_id}")
    # print(f"  - scontrino_test_id: {receipt_test_id}")
    # print(f"  - cursor: {cursor}")
    # print(f"  - conn: {conn}")
    # ========================================
    # HELPER: Structured log in the datas field
    # ========================================
    
    def log_debug(messaggio, details=None):
        print(f"[LOG_DEBUG] {messaggio}")  
        cursor.execute("SELECT data FROM spese_task WHERE id = %s;", (task_id,))
        row = cursor.fetchone()
        
        # PostgreSQL: data is a  dict 
        datas = row['data'] if row and row['data'] else {}
        
        # If for some reason it is still a string (fallback)
        if isinstance(datas, str):
            try:
                datas = json.loads(datas)
            except json.JSONDecodeError:
                datas = {}
        
        if 'debug_log' not in datas:
            datas['debug_log'] = []
        
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'message': messaggio
        }
        if details:
            log_entry['details'] = details
        
        datas['debug_log'].append(log_entry)
        
        cursor.execute(
            "UPDATE spese_task SET data = %s WHERE id = %s;",
            (json.dumps(datas), task_id)  
        )
        conn.commit()
    
    def salva_sezione_datas(nome_sezione, dati):
        cursor.execute("SELECT data FROM spese_task WHERE id = %s;", (task_id,))
        row = cursor.fetchone()
        
        # PostgreSQL: data is a dict
        datas = row['data'] if row and row['data'] else {}
        
        if isinstance(datas, str):
            try:
                datas = json.loads(datas)
            except json.JSONDecodeError:
                datas = {}
            
        datas[nome_sezione] = dati
        
        cursor.execute(
            "UPDATE spese_task SET data = %s WHERE id = %s;",
            (json.dumps(datas), task_id) 
        )
        conn.commit()
    
    timing = {}
    
    try:
        # ========================================
        # STEP 1: DATA RECOVERY TEST
        # ========================================
        #print("[DEBUG] Prima di STEP 1: Recupero dati test")  
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=5,
            step="Step 1/5: Data recovery test..."
        )
        #print("[DEBUG] Dopo aggiorna_task, prima della query SELECT") 
        cursor.execute(
            """
            SELECT tested_store_id, image 
            FROM spese_receipttest 
            WHERE id = %s;
            """,
            (receipt_test_id,)
        )
        #print("[DEBUG] Dopo query SELECT, prima di fetchone")  
        row = cursor.fetchone()
        #print(f"[DEBUG] row = {row}")  
        if not row:
            raise Exception("ScontrinoTest non trovato")
        
        store_id = row['tested_store_id']

        # retrieving the image path from the task
        cursor.execute(
            """
            SELECT data
            FROM spese_task
            WHERE id = %s
            """,
            (task_id,)
        )

        task_row = cursor.fetchone()

        if not task_row:
            raise Exception("Task non trovato")

        task_data = task_row['data'] or {}

        path_img_test = task_data.get("image_path")

        print(f"[DEBUG] path_img_test = {path_img_test}")

        if not path_img_test or not os.path.exists(path_img_test):
            raise Exception(
                f"Immagine test non trovata: {path_img_test}"
            )


        if not os.path.exists(path_img_test):
            raise Exception(f"Test image not found: {path_img_test}")
  
        log_debug("Dati test recuperati", {
            'receipt_test_id': receipt_test_id,
            'store_id': store_id,
            'image': row['image']
        })
        
        # ========================================
        # STEP 2:TEMPLATE RECOVERY
        # ========================================
        
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=15,
            step="Step 2/5: Retrieving supermarket configuration..."
        )
        
        store_template = get_store_template_from_db(cursor, conn, store_id)
        
        if not store_template:
            raise Exception(f"Store template #{store_id} not found")
        
        # print("\n" + "="*80)
        # print("DEBUG TEMPLATE DAL DB")
        # print("="*80)
        # print(f"Tipo: {type(store_template)}")
        # print(f"Chiavi: {store_template.keys()}")
        # print(f"regex_quantita: {repr(store_template.get('quantity_regex'))}")
        # print(f"regex_sconti: {repr(store_template.get('discount_regex'))}")
        # print(f"pattern_rimuovi_iva: {repr(store_template.get('remove_vat_pattern'))}")
        # print("="*80)


        log_debug("Template recuperato", {
            'supermercato_id': store_id,
            'nome': store_template.get('name'),
            'parola_chiave': store_template.get('keyword')
        })
        
        salva_sezione_datas('snapshot_config', {
            'store_id': store_id,
            'name': store_template.get('name'),
            'prompt_instruction': store_template.get('prompt_instruction'),
            'quantity_regex': store_template.get('quantity_regex'),
            'discount_regex': store_template.get('discount_regex'),
            'remove_vat_pattern': store_template.get('remove_vat_pattern'),
            'ignored_lines': store_template.get('ignored_lines'),
            'store_keywords': store_template.get('store_keywords'),
            'repeated_items': store_template.get('repeated_items')
        })
        
        # ========================================
        # STEP 3: OCR
        # ========================================
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=25,
            step="Step 3/5: Reading image with OCR..."
        )
        log_debug("Avvio OCR via SDK Ollama")

        user_id = store_template['user_id']
        config = get_user_ai_config(cursor, user_id)
        
        ocr_prompt = config['ocr_prompt'] or PROMPT_OCR_DEFAULT
        ocr_model = config['ocr_model']
        ok, error = pre_check_ollama(config, [ocr_model])

        if not ok:
            print(f"[WORKER] Pre-check failed: {error}")
            update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error=error, progress=0)
            return
        t_start = time.time()
        testo_estratto = run_ocr(img_receipt=path_img_test,prompt=ocr_prompt,model=ocr_model)
        timing['ocr'] = round(time.time() - t_start, 2)
        
        log_debug("OCR completato", {
            'durata_secondi': timing['ocr'],
            'lunghezza_testo': len(testo_estratto) if testo_estratto else 0
        })
        salva_sezione_datas('testo_ocr', testo_estratto)
        
        # ========================================
        # STEP 4: NORMALIZZAZIONE + LLM
        # ========================================
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=50,
            step="Step 4/5: Normalization and extraction of articles..."
        )
        log_debug("Avvio normalizzazione OCR")
        
        # Normalizza con il template
        t_start = time.time()
        testo_normalizzato = configurable_ocr_normalization_it(testo_estratto, store_template)
        timing['normalizzazione'] = round(time.time() - t_start, 2)
        
        log_debug("Normalizzazione completata", {
            'durata_secondi': timing['normalizzazione'],
            'lunghezza_testo_normalizzato': len(testo_normalizzato)
        })
        salva_sezione_datas('testo_normalizzato', testo_normalizzato)
        
        #  DEBUG
        # print("\n" + "="*80)
        # print("TESTO NORMALIZZATO")
        # print("="*80)
        # print(testo_normalizzato)
        # print("="*80)
        
        
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=65,
            step="Step 4/5:Article extraction using LLMs..."
        )
        log_debug("Avvio estrazione articoli con LLM")

        analysis_prompt = config['analysis_prompt'] or PROMPT_ANALISI_DEFAULT
        analysis_model = config['analysis_model']

        ok, error = pre_check_ollama(config, [analysis_model])
        if not ok:
            print(f"[WORKER] Pre-check failed: {error}")
            update_task(cursor=cursor, conn=conn, task_id=task_id, status="FAILED", error=error, progress=0)
            return
        
        t_start = time.time()
        articoli = extract_receipt_data_llm(normalized_text=testo_normalizzato,model=analysis_model,prompt=analysis_prompt)
        timing['llm'] = round(time.time() - t_start, 2)
        
        if not isinstance(articoli, list):
            raise Exception(f"The LLM did not return a valid list. Type: {type(articoli)}")
        
        log_debug("Articoli estratti", {
            'durata_secondi': timing['llm'],
            'numero_articoli': len(articoli),
            'articoli': articoli[:10]  
        })
        
        # # Debug articoli
        # print("\n" + "="*80)
        # print("ARTICOLI ESTRATTI")
        # print("="*80)
        
        totale_calcolato = 0.0
        for idx, art in enumerate(articoli, 1):
            nome = art.get('nome', 'Articolo senza nome')
            quantita = art.get('quantita', 1)
            prezzo_unitario = art.get('prezzo_unitario', 0)
            prezzo_totale = art.get('prezzo_totale', 0)
            sconto = art.get('sconto', 0)
            
            print(f"\n{idx}. {nome}")
            
            if quantita > 1:
                print(f"   {quantita} × {prezzo_unitario}€ = {prezzo_totale}€")
            else:
                print(f"   Prezzo: {prezzo_totale}€")
            
            if sconto > 0:
                print(f"   ⚠️ SCONTO: {sconto}€")
            
            totale_calcolato += prezzo_totale

       
        somma_prezzi_totali = totale_calcolato 
        somma_sconti = sum(art.get('sconto', 0) for art in articoli)

        # Receipt info
        nome_negozio = extract_store_name(testo_estratto, store_template)
        data_scontrino = extract_receipt_date_it(testo_estratto)
        totale_scontrino_ocr = extract_total_from_receipt_it(testo_estratto)

    
        if totale_scontrino_ocr:
            differenza_senza_sconti = abs(somma_prezzi_totali - totale_scontrino_ocr)
            differenza_con_sconti = abs((somma_prezzi_totali - somma_sconti) - totale_scontrino_ocr)
            
            if differenza_senza_sconti < 0.05:
                print("\n Scenario A: Prices already discounted (I do not deduct discounts)")
                totale_calcolato = somma_prezzi_totali
            elif differenza_con_sconti < 0.05:
                print(f"\n Scenario B: Full prices (discounts subtracted): {somma_sconti:.2f}€)")
                totale_calcolato = somma_prezzi_totali - somma_sconti
            else:
                print(f"\n  No scenario is a perfect match.")
                print(f"   Price sum: {somma_prezzi_totali:.2f}€")
                print(f"   Discount sum: {somma_sconti:.2f}€")
                print(f"   Receipt total: {totale_scontrino_ocr:.2f}€")
                # Fallback
                if differenza_senza_sconti < differenza_con_sconti:
                    totale_calcolato = somma_prezzi_totali
                else:
                    totale_calcolato = somma_prezzi_totali - somma_sconti
        # ========================================
        # STEP 5: METADATA EXTRACTION + SAVING
        # ========================================
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=85,
            step="Step 5/5: Metadata extraction and test saving..."
        )
        log_debug("Avvio estrazione metadata")
        

        
        log_debug("Metadata estratti", {
            'nome_negozio': nome_negozio,
            'data_scontrino': str(data_scontrino) if data_scontrino else None,
            'totale_ocr': totale_scontrino_ocr,
            'totale_calcolato': round(totale_calcolato, 2),
            'scenario': 'A' if differenza_senza_sconti < 0.05 else 'B'
        })

        # print("\n" + "="*80)
        # print("INFO SCONTRINO")
        # print("="*80)
        # print(f"Negozio: {nome_negozio}")
        # print(f"Data: {data_scontrino if data_scontrino else 'Non trovata'}")
        # print(f"Totale calcolato: {totale_calcolato:.2f}€")
        # if totale_scontrino_ocr:
        #     print(f"Totale stampato: {totale_scontrino_ocr:.2f}€")
        #     differenza = abs(totale_calcolato - totale_scontrino_ocr)
        #     if differenza > 0.05:
        #         print(f"⚠️  Differenza: {differenza:.2f}€")
        #     else:
        #         print(f"✅ Totali corrispondenti")

        scontrino_data = {
            "ocr_store_name": nome_negozio,  # ✅ CAMBIATO da nome_negozio_ocr
            "receipt_date": data_scontrino,   # ✅ CAMBIATO da data_scontrino
            "total": totale_calcolato,        # ✅ CAMBIATO da totale
            "articoli": articoli              # Gli articoli hanno già chiavi italiane, le gestiamo sotto
        }
        
        
        riepilogo = {
            'totale_ocr': totale_scontrino_ocr,
            'totale_calcolato': round(totale_calcolato, 2),
            'differenza': round(abs(totale_calcolato - (totale_scontrino_ocr or 0)), 2) if totale_scontrino_ocr else None,
            'match_totali': abs(totale_calcolato - totale_scontrino_ocr) < 0.05 if totale_scontrino_ocr else False,
            'numero_articoli': len(articoli),
            'articoli_con_sconto': sum(1 for art in articoli if art.get('sconto', 0) > 0),
            'articoli_multipli': sum(1 for art in articoli if art.get('quantita', 1) > 1),
            'totale_sconti': round(sum(art.get('sconto', 0) for art in articoli), 2)
        }
        
        log_debug("Riepilogo test", riepilogo)
        salva_sezione_datas('riepilogo', riepilogo)
        salva_sezione_datas('timing', timing)
        salva_sezione_datas('articoli_finali', articoli)
        
        # Salva nelle tabelle test
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="PROCESSING", progress=95,
            step="Step 5/5: Saving test results..."
        )
        
        successo = save_receipt_test(
            cursor, conn, receipt_test_id, scontrino_data
        )
        
        if successo:
            log_debug("✅ Test saved successfully")
            step_finale = "✅ Test completed – totals match!" if riepilogo['match_totali'] else f"⚠️ Test completed - difference: {riepilogo['differenza']}€"
            
            update_task(
                cursor=cursor, conn=conn, task_id=task_id,
                status="COMPLETED", progress=100,
                step=step_finale
            )
        else:
            raise Exception("Error saving the test")
    
    except Exception as e:
        error_msg = str(e)
        log_debug(f"ERROR: {error_msg}")

        print(f"[WORKER ERROR] Test failed: {error_msg}")
        
        salva_sezione_datas('timing', timing)
        
        update_task(
            cursor=cursor, conn=conn, task_id=task_id,
            status="FAILED", progress=0,
            error=error_msg,
            step="Test failed"
        )


######### TASK 4 OLLAMA CHECK CONN AND MODELS #########
def run_check_ollama(cursor, conn, task_id):
    print(f"[WORKER] Start Check Ollama Task #{task_id}")
    
    try:
        cursor.execute("""
            SELECT user_id, data 
            FROM spese_task 
            WHERE id = %s
        """, (task_id,))
        task_row = cursor.fetchone()
        
        if not task_row:
            raise Exception(f"Task {task_id} non found!")
            
        user_id = task_row['user_id']
        datas = task_row['data'] 
        input_data = datas.get('input', {})
        
    
        host = input_data.get('host', os.getenv('OLLAMA_HOST', 'http://localhost:11434'))
        ocr_model = input_data.get('ocr_model') or input_data.get('modello_ocr', 'qwen2.5vl:7b')
        chat_model = input_data.get('chat_model') or input_data.get('modello_chat', 'gpt-oss:20b') # <-- AGGIUNTO
        analysis_model = input_data.get('analysis_model') or input_data.get('modello_analisi', 'gpt-oss:20b')
        categorization_model = input_data.get('categorization_model') or input_data.get('modello_categorizzazione', 'gpt-oss:20b')

        
        print(f"[CHECK] Check Ollama on: {host}")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="PROCESSING", step="Connection to Ollama...", progress=20)

        # Ollama (GET /api/tags)
        response = requests.get(f"{host}/api/tags", timeout=5)
        
        if response.status_code != 200:
            raise Exception(f"Ollama responded with status {response.status_code}")
            
        models_data = response.json().get('models', [])
        available_models = [m['name'] for m in models_data]
        
        #print(f"[CHECK] Connessione riuscita. Modelli trovati: {available_models}")
        update_task(cursor=cursor, conn=conn, task_id=task_id, status="PROCESSING", step="Verifica modelli...", progress=60)

        # Check for the presence of the required models. 
        output_data = {
            "host_raggiungibile": True,
            "modello_ocr_presente": ocr_model in available_models,
            "modello_chat_presente": chat_model in available_models,  
            "modello_analisi_presente": analysis_model in available_models,
            "modello_categorizzazione_presente": categorization_model in available_models,
            "modelli_disponibili": available_models,
            "errore_dettagliato": None
        }

        datas['output'] = output_data
        
        cursor.execute("""
            UPDATE spese_task 
            SET data = %s, status = 'COMPLETED', step = 'Check complete', progress = 100
            WHERE id = %s
        """, (json.dumps(datas), task_id))
        conn.commit()
        
        # 5. WEBSOCKET
        send_event_to_django(task_id=task_id, status="COMPLETED", progress=100, step="Check completata")

    except requests.exceptions.Timeout:
        _fallisci_check(cursor, conn, task_id, "Timeout: Ollama is not responding within 5 seconds.")
    except requests.exceptions.ConnectionError:
        _fallisci_check(cursor, conn, task_id, f"Unable to connect to {host}. Check the IP and firewall.")
    except Exception as e:
        _fallisci_check(cursor, conn, task_id, str(e))

def _fallisci_check(cursor, conn, task_id, errore_msg):
    """Helper function to handle the check failure"""
    print(f"[CHECK ERROR] {errore_msg}")
    
    
    cursor.execute("SELECT data FROM spese_task WHERE id = %s", (task_id,))
    row = cursor.fetchone()

    datas = row['data'] if row else {'input': {}}
    
    datas['output'] = {
        "host_raggiungibile": False,
        "modello_ocr_presente": False,
        "modello_analisi_presente": False,
        "modello_categorizzazione_presente": False,
        "modelli_disponibili": [],
        "errore_dettagliato": errore_msg
    }
    
    # Update db with error
    cursor.execute("""
        UPDATE spese_task 
        SET data = %s, status = 'FAILED', error = %s, progress = 0
        WHERE id = %s
    """, (json.dumps(datas), errore_msg, task_id))
    conn.commit()
    
    #WEBSOCKET 
    send_event_to_django(task_id=task_id, status="FAILED", progress=0, error=errore_msg)

######### TASK 5 CHAT #########
def run_chat(cursor, conn, task_id):
    
    print(f"[CHAT] TASK #{task_id}")
   
    try:
        cursor.execute("""
            SELECT data
            FROM spese_task
            WHERE id = %s
        """, (task_id,))

        task = cursor.fetchone()

        if not task:
            print(f"[CHAT ERROR] Task #{task_id} not found!")
            return

        data = task["data"]

        #print(f"[CHAT DEBUG] Data completo: {data}")

        messages = data.get("messages", [])

        #print(f"[CHAT] Numero messaggi: {len(messages)}")

        for i, message in enumerate(messages):
            print(
                f"[CHAT DEBUG] Messaggio #{i + 1}: "
                f"{message.get('role')} -> "
                f"{message.get('content')}"
            )

        response = client.chat(
            model="qwen2.5-coder:7b",
            messages=messages  # CAMBIATO: messaggi → messages
        )

        
        #print(f"[CHAT DEBUG] Response completa: {response}")

        risposta = response["message"]["content"]

        messages.append({
            "role": "assistant",
            "content": risposta
        })

        data["messages"] = messages

        # print(
        #     f"[CHAT] Numero messaggi dopo risposta: "
        #     f"{len(messages)}"
        # )

        # ==================================================
        # DATABASE
        # ==================================================
        cursor.execute(
            """
            UPDATE spese_task
            SET data = %s
            WHERE id = %s
            """,
            (json.dumps(data), task_id)  
        )

        conn.commit()

        # ==================================================
        # UPDATE TASK STATUS
        # ==================================================
        update_task(
            cursor=cursor,
            conn=conn,
            task_id=task_id,
            status="PROCESSING",
            progress=100,
            step="Risposta inviata"
        )

    except Exception as e:
        print("=" * 80)
        print(f"[CHAT ERROR] ERROR TASK #{task_id}")
        print(f"[CHAT ERROR] Type: {type(e).__name__}")
        print(f"[CHAT ERROR] Message: {e}")
        print("=" * 80)

        conn.rollback()
        raise

######### LOOP #########
if __name__ == "__main__":
    print("[*] Worker started. Monitoring task table...")
    while True:
        search_and_process_task()
        time.sleep(5)  
