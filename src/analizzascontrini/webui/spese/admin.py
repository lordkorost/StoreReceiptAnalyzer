from django.contrib import admin

# Register your models here.
from django.contrib import admin

from .models import (
    Receipt,
    ReceiptTest,
    UserAIConfig,
    ReceiptItem,
    Product,
    Category,
    StoreTemplate,
    ProductDictionary,
    Task,
    ReceiptTestItem,
)


admin.site.register(ReceiptItem)
admin.site.register(Product)
admin.site.register(UserAIConfig)
admin.site.register(ReceiptTestItem)
admin.site.register(ReceiptTest)
admin.site.register(ProductDictionary)

@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'ocr_store_name', 'store', 'receipt_date', 'total', 'confirmed', 'created_at')
    list_filter = ('confirmed', 'store', 'user', 'receipt_date')
    search_fields = ('user__username', 'ocr_store_name')
    ordering = ('-created_at',)

@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):

    list_display = ('id', 'user', 'task_type', 'status', 'progress', 'created_at')
    list_filter = ('status', 'task_type', 'user', 'created_at')
    search_fields = ('user__username', 'error', 'step')
    ordering = ('-created_at',)

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):

    list_display = ('name', 'user','description')
    search_fields = ('name', 'user__username')
    list_filter = ('user',)


@admin.register(StoreTemplate)
class StoreTemplateAdmin(admin.ModelAdmin):

    list_display = ('name', 'user', 'keyword', 'repeated_items')
    list_filter = ('user', 'repeated_items')
    search_fields = ('name', 'keyword', 'user__username')
    ordering = ('user', 'name')
    fieldsets = (
        ('Informazioni Generali', {
            'fields': ('user', 'name', 'keyword'),
            'description': 'Dati base per identificare il supermercato.'
        }),
        ('Configurazione LLM e Parsing', {
            'fields': (
                'prompt_instruction', 
                'quantity_regex', 
                'discount_regex', 
                'remove_vat_pattern', 
                'ignored_lines', 
                'store_keywords', 
                'repeated_items'
            ),
            'classes': ('collapse',), 
            'description': 'Regole avanzate per l\'estrazione dei dati dallo scontrino.'
        }),
    )