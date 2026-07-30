from django.apps import AppConfig

class SpeseConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'spese'
    
    def ready(self):
        
        import spese.signals