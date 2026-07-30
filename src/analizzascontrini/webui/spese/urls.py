# ---------------------------------------------------------------
# Django core imports
# ---------------------------------------------------------------
from django.urls import path

# ---------------------------------------------------------------
# Views
# ---------------------------------------------------------------

## Receipt
from .views import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    EditReceiptView,
    ReceiptDeleteView,
    ReceiptDetailView,
    ReceiptListView,
    UploadReceiptView,
)

## Review / category for receipt
from .views import (
    ReviewReceiptView,
    CategoryLoadingView,
    CategoryReviewView,
)

## Storetemplate (list/detail/create/update/delete)
from .views import (
    StoreTemplateCreateView,
    StoreTemplateDeleteView,
    StoreTemplateDetailView,
    StoreTemplateListView,
    StoreTemplateUpdateView,
)

## Task / loading / test
from .views import (
    LoadingTaskView,
    TestLoadingView,
    TestResultsView,
    retry_task_test_view,   
    retry_task_view,        
    cancel_analysis,
)

## Storetemplate test upload & confirmation
from .views import (
    StoreTemplateTestUploadView,
    test_store_confirm_view,
)

## Dashboard/home
from .views import ReportSpeseView

## Settings / AI config
from .views import ai_config_detail, ai_config_update

## API endpoints (non‑class‑based)
from .views import api_check_ollama, api_task_status

## Setup view
from .views import setup_view

# ---------------------------------------------------------------
# URL patterns
# ---------------------------------------------------------------
urlpatterns = [
     # ------------------------------------------------------------------
     # Receipt – CRUD + review
     # ------------------------------------------------------------------
     path('scontrini/', ReceiptListView.as_view(), name='scontrino_list'),
     path('upload/', UploadReceiptView.as_view(), name='upload_scontrino'),
     path('scontrino/<int:pk>/modifica/', EditReceiptView.as_view(),
          name='receipt_edit'),
     path('scontrino/<int:pk>/delete/', ReceiptDeleteView.as_view(),
          name='scontrino_delete'),
     path('scontrino/<int:pk>/riepilogo/',
          ReceiptDetailView.as_view(), name='receipt_summary'),
     # Review & categories for a specific receipt
     path('scontrino/<int:pk>/review/',
          ReviewReceiptView.as_view(), name='review_scontrino'),
     path('scontrino/<int:pk>/categorie/',
          CategoryReviewView.as_view(), name='review_categoria'),
     # ------------------------------------------------------------------
     # StoreTemplate – CRUD
     # ------------------------------------------------------------------
     path('supermercati/', StoreTemplateListView.as_view(),
          name='supermercato_list'),
     path('supermercati/<int:pk>/', StoreTemplateDetailView.as_view(),
          name='supermercato_detail'),
     path('supermercati/nuovo/', StoreTemplateCreateView.as_view(),
          name='supermercato_create'),
     path('supermercati/<int:pk>/modifica/',
          StoreTemplateUpdateView.as_view(), name='supermercato_update'),
     path('supermercati/<int:pk>/elimina/',
          StoreTemplateDeleteView.as_view(), name='supermercato_delete'),
   
     # ------------------------------------------------------------------
     # Task / Loading / Test
     # ------------------------------------------------------------------
     # 1. Loading for OCR EXTRACTION 
     path('loading/<int:task_id>/', LoadingTaskView.as_view(), name='loading_task'),

     # 2. Loading for CATEGORIZATION
     path('loadingcategoria/<int:task_id>/', CategoryLoadingView.as_view(),
          name='loading_categoria'),

     # 3. Loading for TEST Store Template
     path('task/test/<int:task_id>/loading/', TestLoadingView.as_view(),
          name='loading_task_test'),

     # Tests Results and confirm
     path('test/risultati/<int:task_id>/', TestResultsView.as_view(),
          name='risultati_task_test'),
     path('task/test/<int:task_id>/conferma/', test_store_confirm_view,
          name='test_supermercato_conferma'),

     # ------------------------------------------------------------------
     # Retry / Cancel 
     # ------------------------------------------------------------------
     # Retry 
     path('task/<int:task_id>/retry/', retry_task_view, name='retry_task'),
     # Retry TEST Store Template
     path('task/<int:task_id>/retry-test/', retry_task_test_view, name='retry_task_test'),
     # Cancel 
     path('task/<int:task_id>/cancel/', cancel_analysis, name='annulla_analisi'),

     # ------------------------------------------------------------------
     # Store Template test upload 
     # ------------------------------------------------------------------
     path('supermercati/<int:pk>/test/upload/',StoreTemplateTestUploadView.as_view(),
          name='test_supermercato_start'),
         
     # ------------------------------------------------------------------
     # Dashboard/home
     # ------------------------------------------------------------------
     path('report/', ReportSpeseView.as_view(), name='report_spese'),
     # ------------------------------------------------------------------
     # Settings / AI config
     # ------------------------------------------------------------------
     path('settings/', ai_config_detail, name='ai_config_detail'),
     path('settings/edit/', ai_config_update, name='ai_config_update'),

     # ------------------------------------------------------------------
     # API endpoints
     # ------------------------------------------------------------------
     path('api/check-ollama/', api_check_ollama, name='api_check_ollama'),
     path('api/task-status/<int:task_id>/', api_task_status,name='api_task_status'),

     # ------------------------------------------------------------------
     # Misc / Setup
     # ------------------------------------------------------------------
     path('setup/', setup_view, name='setup'),

     # ------------------------------------------------------------------
     # CATEGORY
     # ------------------------------------------------------------------
     path("categories/",CategoryListView.as_view(),name="category_list",),
     path("categories/new/",CategoryCreateView.as_view(),name="category_create",),
     path("categories/<int:pk>/edit/",CategoryUpdateView.as_view(),name="category_edit",),
     path("categories/<int:pk>/delete/",CategoryDeleteView.as_view(),name="category_delete",),

]

    
