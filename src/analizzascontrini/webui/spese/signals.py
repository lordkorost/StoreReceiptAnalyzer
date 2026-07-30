from django.db.models.signals import post_save
from django.contrib.auth import get_user_model
from django.dispatch import receiver

from analizzascontrini.defaults.ai_settings import (ANALISI_MODEL_DEFAULT, 
                                                    CATEGORIZZAZIONE_MODEL_DEFAULT, 
                                                    OCR_MODEL_DEFAULT,
                                                    CHAT_MODEL_DEFAULT, 
                                                    PROMPT_ANALISI_DEFAULT, 
                                                    PROMPT_CATEGORIZZAZIONE_DEFAULT, 
                                                    PROMPT_OCR_DEFAULT)
from analizzascontrini.defaults.categorie import CATEGORIE_DEFAULT
from analizzascontrini.defaults.supermercatotemplate import SUPERMERCATI_DEFAULT
from .models import Category, StoreTemplate, UserAIConfig


User = get_user_model()

@receiver(post_save, sender=User)
def crea_dati_default_utente(sender, instance, created, **kwargs):
    """
    When a new user is created, it automatically creates:
    - Default categories
    - Default AI configuration
    - Default supermarket templates
    """
    if created:
        #print(f"[BOOTSTRAP] Creation of default data for user {instance.username}")
        
        # 1. Create category
        for nome_categoria in CATEGORIE_DEFAULT:
            Category.objects.get_or_create(
                user=instance,
                name=nome_categoria
            )
        #print(f"[BOOTSTRAP] Create {len(CATEGORIE_DEFAULT)} category for {instance.username}")
        
        # 2. Create AI settings default
        UserAIConfig.objects.get_or_create(
            user=instance,
            defaults={
                'ollama_host': '',  
                'ocr_model': OCR_MODEL_DEFAULT,
                'analysis_model': ANALISI_MODEL_DEFAULT,
                'categorization_model': CATEGORIZZAZIONE_MODEL_DEFAULT,
                'chat_model': CHAT_MODEL_DEFAULT,
                'ocr_prompt': PROMPT_OCR_DEFAULT,
                'analysis_prompt': PROMPT_ANALISI_DEFAULT,
                'categorization_prompt': PROMPT_CATEGORIZZAZIONE_DEFAULT,
            }
        )
        #print(f"[BOOTSTRAP] Created AI configuration for {instance.username}")

        # 3. Create default storetemplate 
        for sup in SUPERMERCATI_DEFAULT:
            StoreTemplate.objects.get_or_create(
                user=instance,
                name=sup["nome"],
                defaults={
                    'keyword': sup["parola_chiave"],
                    'prompt_instruction': sup["prompt_instruction"],
                    'quantity_regex': sup["regex_quantita"],
                    'ignored_lines': sup["righe_da_ignorare"],
                    'discount_regex': sup["regex_sconti"],
                    'remove_vat_pattern': sup["pattern_rimuovi_iva"],
                    'store_keywords': sup["parole_chiave_negozio"],
                    'repeated_items': sup["articoli_ripetuti"],
                }
            )
        #print(f"[BOOTSTRAP] Created {len(SUPERMERCATI_DEFAULT)} store template for {instance.username}")
