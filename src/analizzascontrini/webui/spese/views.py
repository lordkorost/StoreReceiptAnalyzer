# ------------------------------------------------------------------
# Django core
# ------------------------------------------------------------------
import uuid
from difflib import SequenceMatcher

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import (
    get_user_model,
    authenticate,
    login,
    logout,
)
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.utils.translation import gettext_lazy as _
from django.contrib import messages

# ------------------------------------------------------------------
# Django ORM / DB helpers
# ------------------------------------------------------------------
from django.db import IntegrityError, transaction
from django.db.models import (
    Sum, Count, Max, Min, Q,
)
from django.utils.dateparse import parse_date
from django.utils import timezone

# ------------------------------------------------------------------
# Channels / async support
# ------------------------------------------------------------------
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# ------------------------------------------------------------------
# File‑handling & misc utilities
# ------------------------------------------------------------------
# from django.core.files.uploadedfile import InMemoryUploadedFile
from django.conf import settings
import os
# import shutil
from pathlib import Path

# ------------------------------------------------------------------
# Miscellaneous Python modules
# ------------------------------------------------------------------
import json
# import re              
# import decimal
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from datetime import timedelta

# ------------------------------------------------------------------
# Django generic CBV imports
# ------------------------------------------------------------------
from django.views.generic import (
    ListView,
    DetailView,
    CreateView,
    UpdateView,
    DeleteView,
    TemplateView,
)
from django.views.generic.edit import DeleteView  # (se usi la versione edit)

# ------------------------------------------------------------------
# URL helpers
# ------------------------------------------------------------------
from django.urls import reverse_lazy

# ------------------------------------------------------------------
# Project‑specific constants
# ------------------------------------------------------------------
from analizzascontrini.defaults.categorie import CATEGORIE_DEFAULT
from analizzascontrini.defaults.supermercatotemplate import SUPERMERCATI_DEFAULT

# ------------------------------------------------------------------
# Django forms 
# ------------------------------------------------------------------
from .forms import UserAIConfigForm, StoreTemplateForm, CategoryForm

# ------------------------------------------------------------------
# Project models
# ------------------------------------------------------------------
from .models import (
    Receipt,
    ReceiptItem,
    Task,
    StoreTemplate,
    Product,
    ProductDictionary,
    Category,
    UserAIConfig,
    ReceiptTest,
)

# ------------------------------------------------------------------
# Decorators & HTTP helpers
# ------------------------------------------------------------------
from django.views.decorators.http import require_POST

User = get_user_model()

# ------------------------------------------------------------------
# API
# ------------------------------------------------------------------
@method_decorator(csrf_exempt, name='dispatch')
class InternalEventsAPIView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            task_id = data.get("task_id")

            task = Task.objects.get(id=task_id)

            items = ReceiptItem.objects.filter(
                receipt=task.receipt
            )

            items_data = [
                {
                    "id": item.id,
                    "original_string": item.original_string,
                    "price": float(item.price)
                }
                for item in items
            ]

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f"task_{task_id}",
                {
                    "type": "task.completed",
                    "task_id": task_id,
                    "items": items_data
                }
            )

            return JsonResponse({"status": "ok"})

        except Task.DoesNotExist:
            return JsonResponse(
                {
                    "status": "error",
                    "message": "Task not found"
                },
                status=404
            )

@method_decorator(csrf_exempt, name='dispatch')
class InternalTaskEventAPIView(View):
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)

            task_id = data.get("task_id")
            status = data.get("status")
            progress = data.get("progress", 0)
            error = data.get("error", "")
            step = data.get("step", "")

            print(
                f"[DJANGO] Received event from Worker for "
                f"Task #{task_id} ({status} - {progress}%)"
            )

            channel_layer = get_channel_layer()

            async_to_sync(channel_layer.group_send)(
                f"task_{task_id}",
                {
                    "type": "task_update",
                    "status": status,
                    "progress": progress,
                    "error": error,
                    "step": step,
                }
            )

            return JsonResponse({
                "status": "sent_to_channel"
            })

        except Exception as e:
            print(f"[DJANGO ERROR] Error forwarding Channel event: {e}")

            return JsonResponse(
                {
                    "status": "error",
                    "message": str(e),
                },
                status=400
            )

@login_required
@require_POST
def retry_task_test_view(request, task_id):
    """
    Reset a failed task to PENDING so the worker can process it again.
    """
    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user
    )

    task.status = "PENDING"
    task.progress = 0
    task.step = "Queued for worker..."
    task.error = ""
    task.data = {}

    task.save()

    return JsonResponse({
        "status": "success",
        "message": "Task restarted successfully"
    })


@login_required
@require_POST
def retry_task_view(request, task_id):
    """
    Reset a failed task to PENDING so the worker can process it again.
    Works for any task type.
    """
    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user
    )

    task.status = "PENDING"
    task.progress = 0
    task.step = "Queued for worker..."
    task.error = ""

    task.save()

    return JsonResponse({
        "status": "success",
        "message": "Task restarted successfully"
    })


@require_POST
@login_required
def cancel_analysis(request, task_id):

    task = get_object_or_404(
        Task,
        id=task_id,
        user=request.user
    )

    receipt = task.receipt

    if receipt:
        if receipt.image:
            receipt.image.delete(save=False)

        receipt.delete()

    task.delete()

    return JsonResponse({
        "status": "cancelled"
    })

def api_check_ollama(request):
    """API to create an Ollama check task using the current form data."""

    host = (
        request.POST.get("ollama_host", "").strip()
        or os.getenv(
            "OLLAMA_HOST",
            "http://host.docker.internal:11434"
        )
    )

    ocr_model = (
        request.POST.get("ocr_model", "").strip()
        or "qwen2.5vl:7b"
    )

    analysis_model = (
        request.POST.get("analysis_model", "").strip()
        or "gpt-oss:20b"
    )

    categorization_model = (
        request.POST.get("categorization_model", "").strip()
        or "gpt-oss:20b"
    )

    task = Task.objects.create(
        user=request.user,
        task_type="OLLAMA_CHECK",
        status="PENDING",
        step="Connecting to Ollama...",
        data={
            "input": {
                "host": host,
                "ocr_model": ocr_model,
                "analysis_model": analysis_model,
                "categorization_model": categorization_model,
            },
            "output": {},
        }
    )

    return JsonResponse({
        "success": True,
        "task_id": task.id,
    })

@login_required
def api_task_status(request, task_id):
    """Return the status and data of a specific task."""

    try:
        task = Task.objects.get(
            id=task_id,
            user=request.user
        )

        return JsonResponse({
            "status": task.status,
            "data": task.data,
            "error": task.error,
        })

    except Task.DoesNotExist:
        return JsonResponse(
            {
                "error": "Task not found"
            },
            status=404
        )

@login_required
def api_chat(request):

    task = Task.objects.filter(
        user=request.user,
        task_type="CHAT",
        status="PROCESSING"
    ).first()

    if not task:

        task = Task.objects.create(
            user=request.user,
            task_type="CHAT",
            status="PROCESSING",
            step="Chat ready",
            progress=0,
            data={
                "messages": []
            }
        )

    if not task.data:
        task.data = {
            "messages": []
        }

        task.save(update_fields=["data"])

    return JsonResponse({
        "task_id": task.id,
        "status": task.status,
        "step": task.step,
        "progress": task.progress,
        "data": task.data,
    })

@login_required
@require_POST
def api_chat_send(request):

    try:
        data = json.loads(request.body)
        message = data.get("message", "").strip()

        # ============================================
        # CHAT CLOSE COMMAND
        # ============================================

        if message.lower() == "/end":

            task = get_object_or_404(
                Task,
                user=request.user,
                task_type="CHAT",
                status="PROCESSING"
            )

            task.status = "COMPLETED"
            task.progress = 100
            task.step = "Chat finished"
            task.error = None
            task.save()

            return JsonResponse({
                "success": True,
                "chat_finished": True,
                "message": "Chat finished"
            })

        print(f"[CHAT] Message received: {message}")

        task = get_object_or_404(
            Task,
            user=request.user,
            task_type="CHAT",
            status="PROCESSING"
        )

        print(f"[CHAT] Task found: #{task.id}")
        print(f"[CHAT] Data before: {task.data}")

        task_data = task.data or {}

        if "messages" not in task_data:
            task_data["messages"] = []

        task_data["messages"].append({
            "role": "user",
            "content": message
        })

        task.data = task_data
        task.status = "PENDING"
        task.step = "Message waiting for processing"
        task.progress = 0
        task.error = None

        task.save()

        print(f"[CHAT] Data after: {task.data}")
        print(f"[CHAT] Task saved as PENDING")

        return JsonResponse({
            "success": True,
            "task_id": task.id,
            "status": task.status,
            "step": task.step
        })

    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "message": "Invalid JSON"
            },
            status=400
        )


@login_required
@require_POST
def api_chat_finished(request):

    task = Task.objects.filter(
        user=request.user,
        task_type="CHAT",
        status="PROCESSING"
    ).first()

    if not task:
        return JsonResponse({
            "success": False,
            "message": "No active chat"
        })

    task.status = "COMPLETED"
    task.progress = 100
    task.step = "Chat finished"
    task.save()

    return JsonResponse({
        "success": True,
        "message": "Chat finished"
    })


# ------------------------------------------------------------------
# RECEIPT ANALYSIS TASK
# ------------------------------------------------------------------

class UploadReceiptView(LoginRequiredMixin, View):

    def get(self, request):

        stores = (
            StoreTemplate.objects
            .filter(user=request.user)
        )

        return render(
            request,
            "spese/upload.html",
            {
                "stores": stores
            }
        )

    def post(self, request):

        image = request.FILES.get("image")
        store_id = request.POST.get("store")

        if not image:
            return render(
                request,
                "spese/upload.html",
                {
                    "error": "You must select an image!",
                    "stores": StoreTemplate.objects.filter(
                        user=request.user
                    )
                }
            )

        store = None

        if store_id:
            store = get_object_or_404(
                StoreTemplate,
                id=store_id,
                user=request.user
            )

        receipt = Receipt.objects.create(
            user=request.user,
            image=image,
            store=store
        )

        task = Task.objects.create(
            user=request.user,
            receipt=receipt,
            task_type="OCR_EXTRACTION",
            status="PENDING",
            data={
                "image_path": receipt.image.path
            }
        )

        return redirect(
            "loading_task",
            task_id=task.id
        )

class LoadingTaskView(LoginRequiredMixin, View):
    """Loading page for the initial OCR task."""

    def get(self, request, task_id):

        task = get_object_or_404(
            Task.objects.filter(
                user=request.user,
                task_type="OCR_EXTRACTION"
            ),
            id=task_id
        )

        return render(
            request,
            "spese/loading.html",
            {
                "task": task
            }
        )

class ReviewReceiptView(LoginRequiredMixin, View):

    def get(self, request, pk):

        receipt = get_object_or_404(
            Receipt.objects
            .filter(user=request.user)
            .select_related("store")
            .prefetch_related("items__product"),
            pk=pk
        )

        if not receipt.store:
            assign_store_from_ocr(receipt)

        apply_receipt_mapping(receipt)

        return render(
            request,
            "spese/review_receipt.html",
            {
                "receipt": receipt,
                "items": receipt.items.all(),
                "stores": (
                    StoreTemplate.objects
                    .filter(user=request.user)
                    .order_by("name")
                ),
                "products": (
                    Product.objects
                    .filter(user=request.user)
                    .order_by("name")
                ),
            }
        )


    @transaction.atomic
    def post(self, request, pk):
        receipt = get_object_or_404(Receipt, pk=pk, user=request.user)

        # ==========================================
        # 1. GENERAL INFORMATION
        # ==========================================
        if 'store_name' in request.POST:
            receipt.ocr_store_name = request.POST.get('store_name', '').strip()
            
        if 'receipt_date' in request.POST:
            date_val = request.POST.get('receipt_date', '').strip()
            receipt.receipt_date = date_val if date_val else None
            
        if 'total' in request.POST:
            try:
                total_val = request.POST.get('total', '0').strip()
                receipt.total = Decimal(total_val) if total_val else receipt.total
            except InvalidOperation:
                pass

        receipt.save()

        # ==========================================
        # 2. Updating existing articles
        # ==========================================
        for item in receipt.items.all():
            # Cerca la chiave INGLESE: item_name_ID
            name_key = f"item_name_{item.id}"
            
            if name_key in request.POST:
                item_name = request.POST.get(name_key, '').strip()
                
                # A. Gestione Prodotto
                if item_name:
                    product, created = Product.objects.get_or_create(
                        user=request.user, 
                        name=item_name
                    )
                    item.product = product
                    
                    if receipt.store:
                        ProductDictionary.objects.update_or_create(
                            user=request.user,
                            store=receipt.store,
                            receipt_text=item.original_text,
                            defaults={'product': product}
                        )
                else:
                    item.product = None

                # Handling Numerical Values
                try:
                    qta_val = request.POST.get(f"quantity_{item.id}", "").strip()
                    if qta_val: item.quantity = Decimal(qta_val)
                    
                    p_unit_val = request.POST.get(f"unit_price_{item.id}", "").strip()
                    if p_unit_val: item.unit_price = Decimal(p_unit_val)
                    
                    price_val = request.POST.get(f"price_{item.id}", "").strip()
                    if price_val: item.price = Decimal(price_val)
                    
                    discount_val = request.POST.get(f"discount_{item.id}", "").strip()
                    if discount_val: item.discount = Decimal(discount_val)
                except InvalidOperation:
                    pass

                item.save()

        # ==========================================
        # 3. Manual entry of new items
        # ==========================================
        new_names = request.POST.getlist("new_item_name")
        new_qtas = request.POST.getlist("new_quantity")
        new_p_units = request.POST.getlist("new_unit_price")
        new_prices = request.POST.getlist("new_price")
        new_discounts = request.POST.getlist("new_discount")

        for name, qta, p_unit, price, discount in zip(new_names, new_qtas, new_p_units, new_prices, new_discounts):
            name_stripped = name.strip()
            if not name_stripped:
                continue
                
            try:
                product, created = Product.objects.get_or_create(
                    user=request.user, 
                    name=name_stripped
                )
                
                ReceiptItem.objects.create(
                    receipt=receipt,
                    original_text=name_stripped,
                    product=product,
                    quantity=Decimal(qta or 1),
                    unit_price=Decimal(p_unit or 0),
                    price=Decimal(price or 0),
                    discount=Decimal(discount or 0)
                )
                
                if receipt.store:
                    ProductDictionary.objects.update_or_create(
                        user=request.user,
                        store=receipt.store,
                        receipt_text=name_stripped,
                        defaults={'product': product}
                    )
            except (InvalidOperation, ValueError):
                continue

        # ==========================================
        # 4. TASK CATEGORIZATION
        # ==========================================
        task = Task.objects.create(
            user=request.user,
            receipt=receipt,
            task_type="CATEGORIZATION",
            status="PENDING"
        )

        return redirect('loading_categoria', task_id=task.id)
class CategoryLoadingView(LoginRequiredMixin, View):
    """Loading page for the categorization task."""

    def get(self, request, task_id):

        task = get_object_or_404(
            Task.objects.filter(
                user=request.user,
                #task_type="CATEGORIZATION"
            ),
            id=task_id
        )

        return render(
            request,
            "spese/loading_category.html",
            {
                "task": task
            }
        )

class CategoryReviewView(LoginRequiredMixin, View):

    def get(self, request, pk):

        receipt = (
            Receipt.objects
            .filter(user=request.user)
            .select_related("store")
            .prefetch_related(
                "items__product__category"
            )
            .get(pk=pk)
        )

        categories = (
            Category.objects
            .filter(user=request.user)
            .order_by("name")
        )

        return render(
            request,
            "spese/review_category.html",
            {
                "receipt": receipt,
                "categories": categories,
                "items": receipt.items.all()
            }
        )

    def post(self, request, pk):

        receipt = get_object_or_404(
            Receipt.objects.filter(
                user=request.user
            ),
            pk=pk
        )

        for item in receipt.items.all():

            category_id = request.POST.get(
                f"category_{item.id}"
            )

            if category_id and item.product:

                category = get_object_or_404(
                    Category.objects.filter(
                        user=request.user
                    ),
                    id=category_id
                )

                if item.product.user != request.user:
                    continue

                item.product.category = category
                item.product.save()

        receipt.confirmed = True
        receipt.save()

        return redirect(
            "receipt_summary",
            pk=receipt.id
        )
class ReceiptSummaryView(LoginRequiredMixin, View):

    def get(self, request, receipt_id):

        receipt = (
            Receipt.objects
            .filter(user=request.user)
            .prefetch_related(
                "items__product__category"
            )
            .get(pk=receipt_id)
        )

        return render(
            request,
            "spese/summary.html",
            {
                "receipt": receipt
            }
        )

# ------------------------------------------------------------------
# RECEIPT ANALYSIS HELPERS
# ------------------------------------------------------------------

def apply_receipt_mapping(receipt):

    #print("!!! ENTERED apply_receipt_mapping !!!")

    if not receipt.store:
        return

    mappings = {
        mapping.receipt_text: mapping.product
        for mapping in ProductDictionary.objects.filter(
            store=receipt.store
        ).select_related("product")
    }

    #print("[MAPPING] Number of mappings:", len(mappings))

    items_to_update = []

    for item in receipt.items.all():

        product = mappings.get(
            item.original_text
        )

        if not product:

            product = find_similar_mapping(
                item.original_text,
                mappings
            )

        if (
            product
            and item.product_id != product.id
        ):

            item.product = product
            items_to_update.append(item)

    # print(
    #     "[MAPPING] Items to update:",
    #     len(items_to_update)
    # )

    if items_to_update:

        ReceiptItem.objects.bulk_update(
            items_to_update,
            ["product"]
        )

def find_similar_mapping(text, mappings):

    best_match = None
    max_score = 0

    for original_text, product in mappings.items():

        score = SequenceMatcher(
            None,
            text,
            original_text
        ).ratio()

        if score > max_score:
            max_score = score
            best_match = product

    # print(
    #     "[SIMILAR]",
    #     text,
    #     "=>",
    #     best_match.name if best_match else None,
    #     max_score
    # )

    if max_score >= 0.85:
        return best_match

    return None

def assign_store_from_ocr(receipt):

    if not receipt.ocr_store_name:
        return

    text = receipt.ocr_store_name.upper()

    for store in StoreTemplate.objects.all():

        if store.keyword.upper() in text:

            receipt.store = store
            receipt.save(update_fields=["store"])

            # print(
            #     "[STORE MATCH]",
            #     text,
            #     "->",
            #     store.name
            # )

            return store

    return None


# ------------------------------------------------------------------
# RECEIPT
# ------------------------------------------------------------------
class ReceiptDetailView(LoginRequiredMixin, View):

    def get(self, request, pk):

        receipt = get_object_or_404(
            Receipt.objects
            .filter(user=request.user)
            .select_related("store")
            .prefetch_related("items__product__category"),
            pk=pk
        )

        # 1. Calculate totals using Decimal for exact precision
        receipt_total = Decimal(
            str(receipt.total or 0)
        )

        items_total = sum(
            Decimal(str(item.price or 0))
            for item in receipt.items.all()
        )

        discounts_total = sum(
            Decimal(str(item.discount or 0))
            for item in receipt.items.all()
        )

        calculated_net_total = (
            items_total - discounts_total
        )

        # Tolerance of 2 cents for small LLM rounding differences
        tolerance = Decimal("0.02")

        # 2. Intelligent comparison logic
        gross_difference = abs(
            items_total - receipt_total
        )

        net_difference = abs(
            calculated_net_total - receipt_total
        )

        if gross_difference <= tolerance:

            # CASE A:
            # Extracted prices are already the final paid prices.
            # The discount is informational only.

            calculated_total = items_total
            difference = gross_difference
            comparison_status = "gross_match"

        elif net_difference <= tolerance:

            # CASE B:
            # Extracted prices are gross prices.
            # Discounts must be subtracted to obtain the final total.

            calculated_total = calculated_net_total
            difference = net_difference
            comparison_status = "net_match"

        else:

            # CASE C:
            # Neither calculation matches the receipt total.
            # This likely indicates an OCR/LLM extraction error.

            calculated_total = calculated_net_total
            difference = net_difference
            comparison_status = "mismatch"

        return render(
            request,
            "spese/receipt_detail.html",
            {
                "receipt": receipt,
                "items": receipt.items.all(),
                "items_total": items_total,
                "discounts_total": discounts_total,
                "calculated_total": calculated_total,
                "difference": difference,
                "comparison_status": comparison_status,
            }
        )

class EditReceiptView(LoginRequiredMixin, View):
    """
    View for editing all receipt data:

    - General data (date, store, total, store template)
    - Individual items (mapped product, quantity, price, discount)
    """

    def get(self, request, pk):

        receipt = get_object_or_404(
            Receipt.objects
            .filter(user=request.user)
            .select_related("store")
            .prefetch_related("items__product__category"),
            pk=pk
        )

        context = {
            "receipt": receipt,
            "selected_store_id": receipt.store_id, 
            "stores": (
                StoreTemplate.objects
                .filter(user=request.user)
                .order_by("name")
            ),

            "products": (
                Product.objects
                .filter(user=request.user)
                .order_by("name")
            ),

            "categories": (
                Category.objects
                .filter(user=request.user)
                .order_by("name")
            ),
        }

        return render(
            request,
            "spese/edit_receipt.html",
            context
        )

    def post(self, request, pk):

        receipt = get_object_or_404(
            Receipt.objects.filter(user=request.user),
            pk=pk
        )

        # ========================================
        # 1. UPDATE GENERAL RECEIPT DATA
        # ========================================

        try:

            receipt.ocr_store_name = (
                request.POST
                .get("ocr_store_name", "")
                .strip()
            )

            receipt_date = request.POST.get("receipt_date")

            receipt.receipt_date = (
                receipt_date
                if receipt_date
                else None
            )

            total = request.POST.get("total", "0")

            receipt.total = (
                Decimal(total)
                if total
                else Decimal("0")
            )

            store_id = request.POST.get("store")

            if store_id:

                store = get_object_or_404(
                    StoreTemplate.objects.filter(
                        user=request.user
                    ),
                    pk=store_id
                )

                receipt.store = store

            else:

                receipt.store = None

            receipt.save()

        except (ValueError, InvalidOperation) as e:

            

            messages.error(
                request,
                _("Error in general receipt data: {}").format(str(e))
            )

            return redirect(
                "edit_receipt",
                receipt_id=pk
            )

        # ========================================
        # 2. UPDATE OR DELETE EXISTING ITEMS
        # ========================================

        updated_items = 0

        for item in receipt.items.all():

            # Delete item if the checkbox is selected
            if request.POST.get(
                f"delete_{item.id}"
            ) == "on":

                item.delete()
                continue

            try:

                quantity_raw = (
                    request.POST
                    .get(f"quantity_{item.id}", "")
                    .strip()
                )

                unit_price_raw = (
                    request.POST
                    .get(f"unit_price_{item.id}", "")
                    .strip()
                )

                price_raw = (
                    request.POST
                    .get(f"price_{item.id}", "")
                    .strip()
                )

                discount_raw = (
                    request.POST
                    .get(f"discount_{item.id}", "")
                    .strip()
                )

                item.quantity = (
                    Decimal(quantity_raw)
                    if quantity_raw
                    else (
                        item.quantity
                        or Decimal("1")
                    )
                )

                item.unit_price = (
                    Decimal(unit_price_raw)
                    if unit_price_raw
                    else (
                        item.unit_price
                        or Decimal("0")
                    )
                )

                item.price = (
                    Decimal(price_raw)
                    if price_raw
                    else item.price
                )

                item.discount = (
                    Decimal(discount_raw)
                    if discount_raw
                    else (
                        item.discount
                        or Decimal("0")
                    )
                )

                product_name = (
                    request.POST
                    .get(
                        f"product_name_{item.id}",
                        ""
                    )
                    .strip()
                )

                category_id = request.POST.get(
                    f"category_{item.id}",
                    ""
                )

                if product_name:

                    product, created = (
                        Product.objects.get_or_create(
                            user=request.user,
                            name=product_name
                        )
                    )

                    if category_id:

                        product.category_id = category_id
                        product.save()

                    item.product = product

                    if receipt.store:

                        ProductDictionary.objects.update_or_create(
                            user=request.user,
                            store=receipt.store,
                            receipt_text=item.original_text,
                            defaults={
                                "product": product
                            }
                        )

                else:

                    item.product = None

                item.save()

                updated_items += 1

            except (ValueError, InvalidOperation) as e:

                messages.warning(
                    request,
                    _(
                        'Error in item "{item_text}": {error}'
                    ).format(
                        item_text=item.original_text,
                        error=str(e)
                    )
                )

                continue

        # ========================================
        # 3. INSERT NEW ITEMS MANUALLY
        # ========================================

        new_names = request.POST.getlist(
            "new_name"
        )

        new_quantities = request.POST.getlist(
            "new_quantity"
        )

        new_unit_prices = request.POST.getlist(
            "new_unit_price"
        )

        new_prices = request.POST.getlist(
            "new_price"
        )

        new_discounts = request.POST.getlist(
            "new_discount"
        )

        new_categories = request.POST.getlist(
            "new_category"
        )

        for (
            name,
            quantity,
            unit_price,
            price,
            discount,
            category_id
        ) in zip(
            new_names,
            new_quantities,
            new_unit_prices,
            new_prices,
            new_discounts,
            new_categories
        ):

            name = name.strip()

            if not name:
                continue

            try:

                product, created = (
                    Product.objects.get_or_create(
                        user=request.user,
                        name=name
                    )
                )

                if category_id:

                    product.category_id = category_id
                    product.save()

                ReceiptItem.objects.create(

                    receipt=receipt,

                    original_text=(
                        f"Manually added: {name}"
                    ),

                    product=product,

                    quantity=Decimal(
                        quantity or "1"
                    ),

                    unit_price=Decimal(
                        unit_price or "0"
                    ),

                    price=Decimal(
                        price or "0"
                    ),

                    discount=Decimal(
                        discount or "0"
                    )
                )

                if receipt.store:

                    ProductDictionary.objects.update_or_create(

                        user=request.user,

                        store=receipt.store,

                        receipt_text=name,

                        defaults={
                            "product": product
                        }
                    )

            except (
                ValueError,
                InvalidOperation
            ):

                continue

        messages.success(
            request,
            _(
                "Receipt updated successfully! ({count} items modified/added)"
            ).format(count=updated_items)
        )
        return redirect(
            "receipt_summary",
            pk=pk
        )

class ReceiptListView(LoginRequiredMixin, ListView):
    model = Receipt
    template_name = "spese/receipt_list.html"
    context_object_name = "receipts"  
    
    def get_queryset(self):
        qs = Receipt.objects.filter(user=self.request.user).order_by('-receipt_date', '-created_at')
        
        # If show_all is not requested, hide failed tasks
        if not self.request.GET.get('show_all'):
            qs = qs.exclude(tasks__status='FAILED')
        
        return qs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Count receipts with failed tasks
        context['num_failed'] = Receipt.objects.filter(
            user=self.request.user,
            tasks__status='FAILED'
        ).count()
        
        context['show_all'] = self.request.GET.get('show_all')
        
        return context
class ReceiptDeleteView(LoginRequiredMixin, DeleteView):

    model = Receipt
    success_url = reverse_lazy("receipts_list")

    def get_queryset(self):

        return Receipt.objects.filter(
            user=self.request.user
        )

    def form_valid(self, form):

        messages.success(self.request,_("Receipt deleted successfully."))

        return super().form_valid(form)
    
# ------------------------------------------------------------------
# STORE TEMPLATE
# ------------------------------------------------------------------

class CreateStoreTemplateView(LoginRequiredMixin, View):

    def post(self, request):
        # 1. Get basic fields
        name = request.POST.get(
            "name",
            ""
        ).strip()

        keyword = request.POST.get(
            "keyword",
            ""
        ).strip()

        quantity_regex = (
            request.POST
            .get("quantity_regex", "")
            .strip()
            or None
        )

        discount_regex = (
            request.POST
            .get("discount_regex", "")
            .strip()
            or None
        )

        remove_vat_pattern = (
            request.POST
            .get("remove_vat_pattern", "")
            .strip()
            or None
        )

        prompt_instruction = (
            request.POST
            .get("prompt_instruction", "")
            .strip()
        )

        repeated_items = (
            request.POST.get(
                "repeated_items"
            ) == "1"
        )

        # 2. Get and validate JSON fields
        ignored_lines_raw = (
            request.POST
            .get("ignored_lines", "[]")
            .strip()
        )

        store_keywords_raw = (
            request.POST
            .get("store_keywords", "[]")
            .strip()
        )

        if not name:
            return JsonResponse({
                "ok": False,
                "error": (
                    "Please enter at least a store name."
                )
            })

        try:
            ignored_lines = (
                json.loads(ignored_lines_raw)
                if ignored_lines_raw
                else []
            )

            store_keywords = (
                json.loads(store_keywords_raw)
                if store_keywords_raw
                else []
            )

        except json.JSONDecodeError:
            return JsonResponse({
                "ok": False,
                "error": (
                    "Invalid JSON format. "
                    "Use square brackets, for example: "
                    '["value1", "value2"]'
                )
            })

        # 3. Create database object
        try:
            store_template = (
                StoreTemplate.objects.create(
                    user=request.user,
                    name=name,
                    keyword=keyword,
                    quantity_regex=quantity_regex,
                    discount_regex=discount_regex,
                    remove_vat_pattern=remove_vat_pattern,
                    prompt_instruction=prompt_instruction,
                    repeated_items=repeated_items,
                    ignored_lines=ignored_lines,
                    store_keywords=store_keywords
                )
            )

        except IntegrityError:
            return JsonResponse({
                "ok": False,
                "error": (
                    "A store with this name "
                    "already exists for your account."
                )
            })

        # 4. Success response
        return JsonResponse({
            "ok": True,
            "id": store_template.id,
            "name": store_template.name
        })

class StoreTemplateListView(LoginRequiredMixin, ListView):

    model = StoreTemplate
    template_name = "spese/store_template_list.html"
    context_object_name = "store_templates"
    ordering = ["name"]

    def get_queryset(self):

        return StoreTemplate.objects.filter(
            user=self.request.user
        )

class StoreTemplateDetailView(
    LoginRequiredMixin,
    DetailView
):

    """
    Detail view for a store template
    and all its configurations.
    """

    model = StoreTemplate
    template_name = "spese/store_template_detail.html"
    context_object_name = "store_template"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        # Number of receipts associated with this store
        context["num_receipts"] = (
            self.object.receipt_set.count()
        )

        # Number of product dictionary entries
        context["num_mappings"] = (
            self.object.product_dictionary.count()
        )

        return context

    def get_queryset(self):
        # Security: users can only view their own store templates
        return StoreTemplate.objects.filter(
            user=self.request.user
        )

class StoreTemplateCreateView(LoginRequiredMixin, CreateView):
    model = StoreTemplate
    form_class = StoreTemplateForm
    template_name = "spese/store_template_form.html"
    success_url = reverse_lazy("store_template_list")

    def form_valid(self, form):
       
        form.instance.user = self.request.user
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            _('Store "{store_name}" saved successfully!').format(store_name=self.object.name)
        )

        # If "Save and Test" was pressed, redirect to the update
        action = self.request.POST.get("action")
        if action == "save_and_test":
            from django.shortcuts import redirect
            return redirect('supermercato_update', pk=self.object.pk)

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["test_files"] = self._get_test_files()
        return context

    def _get_test_files(self):
        """List files in /media/test/."""
        test_dir = Path(settings.MEDIA_ROOT) / "test"
        
        if not test_dir.exists():
            return []

        files = []
        for file in test_dir.iterdir():
            if file.is_file() and file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                files.append({
                    "name": file.name,
                    "size_kb": round(file.stat().st_size / 1024, 1)
                })

        return sorted(files, key=lambda item: item["name"])

class StoreTemplateUpdateView(LoginRequiredMixin, UpdateView):
    model = StoreTemplate
    form_class = StoreTemplateForm
    template_name = "spese/store_template_form.html"
    success_url = reverse_lazy("supermercato_list")

    def get_queryset(self):
        return StoreTemplate.objects.filter(user=self.request.user)

    def form_valid(self, form):
        response = super().form_valid(form)
        
        messages.success(
            self.request,
            _('Store "{store_name}" saved successfully!').format(store_name=self.object.name)
        )

        # Check which button was pressed
        action = self.request.POST.get("action")
        
        if action == "save_and_test":
            # test modal
            context = self.get_context_data(form=form)
            context["open_modal"] = True
            return render(self.request, self.template_name, context)

        return response

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["test_files"] = self._get_test_files()
        return context

    def _get_test_files(self):
        """List files in /media/test/."""
        test_dir = Path(settings.MEDIA_ROOT) / "test"
        
        if not test_dir.exists():
            return []

        files = []
        for file in test_dir.iterdir():
            if file.is_file() and file.suffix.lower() in [".jpg", ".jpeg", ".png", ".webp"]:
                files.append({
                    "name": file.name,
                    "size_kb": round(file.stat().st_size / 1024, 1)
                })

        return sorted(files, key=lambda item: item["name"])

class StoreTemplateDeleteView(
    LoginRequiredMixin,
    DeleteView
):
    """
    Delete a store template after confirmation.
    """

    model = StoreTemplate
    template_name = (
        "spese/store_template_confirm_delete.html"
    )

    success_url = reverse_lazy(
        "store_template_list"
    )

    def get_queryset(self):

        # Security: users can delete only their own templates
        return StoreTemplate.objects.filter(
            user=self.request.user
        )

    def delete(
        self,
        request,
        *args,
        **kwargs
    ):

        self.object = self.get_object()
        name = self.object.name

        response = super().delete(
            request,
            *args,
            **kwargs
        )

        messages.success(
            request,
            _('Store "{store_name}" deleted successfully!').format(store_name=name)
        )
        return response

# ------------------------------------------------------------------
# STORE TEMPLATE TEST TASK
# ------------------------------------------------------------------
class StoreTemplateTestLoadingView(
    LoginRequiredMixin,
    View
):
    """
    Loading page for a store template test task.
    """

    def get(
        self,
        request,
        task_id
    ):

        task = get_object_or_404(
            Task.objects.filter(
                user=request.user,
                task_type="STORE_TEMPLATE_TEST"
            ),
            id=task_id
        )

        return render(
            request,
            "spese/loading_test.html",
            {
                "task": task
            }
        )
    
class StoreTemplateTestUploadView(LoginRequiredMixin, View):
    """
    Handle uploading or selecting an image
    for a store template test.
    """

    def post(self, request, pk): 
        
        store_template = get_object_or_404(
            StoreTemplate,
            pk=pk,
            user=request.user
        )

        # Ensure /media/test/ exists
        test_dir = (
            Path(settings.MEDIA_ROOT)
            / "test"
        )

        test_dir.mkdir(
            parents=True,
            exist_ok=True
        )

        image_file = None
        file_name = None

        # CASE 1: Upload a new file
        if request.FILES.get("new_file"):
            uploaded = request.FILES[
                "new_file"
            ]
            file_name = uploaded.name
            destination_path = (
                test_dir
                / file_name
            )

            # Add suffix if file already exists
            counter = 1

            while destination_path.exists():
                stem = Path(
                    file_name
                ).stem

                extension = Path(
                    file_name
                ).suffix

                file_name = (
                    f"{stem}_{counter}"
                    f"{extension}"
                )

                destination_path = (
                    test_dir
                    / file_name
                )

                counter += 1

            with open(
                destination_path,
                "wb+"
            ) as destination:
                for chunk in uploaded.chunks():
                    destination.write(
                        chunk
                    )
            image_file = (
                f"test/{file_name}"
            )

        # CASE 2: Select an existing file
        elif request.POST.get("existing_file"):
            file_name = request.POST[
                "existing_file"
            ]
            file_path = (
                test_dir
                / file_name
            )
            if not file_path.exists():
                messages.error(
                    request,
                    _("Selected file not found.")
                )
                return redirect(
                    "supermercato_update",
                    pk=pk
                )

            image_file = (
                f"test/{file_name}"
            )

        else:
            messages.error(
                request,
                _("You must select or upload an image.")
            )
            return redirect(
                "supermercato_update",
                pk=pk
            )

        # Create ReceiptTest
        receipt_test = ReceiptTest.objects.create(
            user=request.user,
            tested_store=store_template,
            image=image_file
        )

        # Create Task
        task = Task.objects.create(
            user=request.user,
            receipt_test=receipt_test,
            task_type="STORE_TEMPLATE_TEST",
            status="PENDING",
            data={
                "debug_log": [],
                "store_template_id": (
                    store_template.id
                ),
                "store_name": (
                    store_template.name
                ),
                "image_path": receipt_test.image.path,
            }
        )

        messages.success(
            request,
            _('Test started for "{store_name}"').format(store_name=store_template.name)
        )

        return redirect(
            "loading_task_test",
            task_id=task.id
        )

class TestResultsView(LoginRequiredMixin, View):
    """
    Shows the results of a store template configuration test
    with comparison to previous tests.
    """

    def get(self, request, task_id):

        task = get_object_or_404(
            Task.objects.filter(user=request.user),
            id=task_id,
            task_type="STORE_TEMPLATE_TEST"
        )

        receipt_test = get_object_or_404(
            ReceiptTest.objects.filter(user=request.user),
            id=task.receipt_test_id
        )

        test_items = (
            receipt_test.items
            .all()
            .select_related("product", "category")
        )

        store = receipt_test.tested_store

        previous_tests = (
            Task.objects
            .filter(
                user=request.user,
                task_type="STORE_TEMPLATE_TEST",
                status="COMPLETED",
                receipt_test__tested_store=store 
            )
            .exclude(id=task.id)
            .select_related("receipt_test")
            .order_by("-created_at")[:5]
        )

        previous_tests_data = []
        for previous_task in previous_tests:
            data = previous_task.data or {}
            
            riepilogo = data.get("riepilogo", {})
            timing = data.get("timing", {})

            total_timing = sum(
                value for value in timing.values() if isinstance(value, (int, float))
            )

            previous_tests_data.append({
                "id": previous_task.id,
                "created_at": previous_task.created_at,
                "total_ocr": riepilogo.get("totale_ocr", 0),
                "calculated_total": riepilogo.get("totale_calcolato", 0),
                "difference": riepilogo.get("differenza", 0),
                "total_match": riepilogo.get("match_totali", False),
                "item_count": riepilogo.get("numero_articoli", 0),
                "discounted_items": riepilogo.get("articoli_con_sconto", 0),
                "multiple_items": riepilogo.get("articoli_multipli", 0),
                "total_discounts": riepilogo.get("totale_sconti", 0),
                "timing_ocr": timing.get("ocr", 0),
                "timing_normalization": timing.get("normalizzazione", 0), # ✅ Corretto anche qui
                "timing_llm": timing.get("llm", 0),
                "timing_total": total_timing,
            })

        current_data = task.data or {}
        
  
        current_summary = current_data.get("riepilogo", {})
        current_timing = current_data.get("timing", {})
        debug_log = current_data.get("debug_log", [])

        context = {
            "task": task,
            "receipt_test": receipt_test,
            "test_items": test_items,
            "store": store,
            "current_summary": current_summary,
            "current_timing": current_timing,
            "debug_log": debug_log,
            "previous_tests": previous_tests_data,
        }

        return render(
            request,
            "spese/test_results.html",
            context
        )

class TestLoadingView(LoginRequiredMixin, View):

    def get(self, request, task_id):
        task = get_object_or_404(
            Task.objects.filter(
                user=request.user,
                task_type="STORE_TEMPLATE_TEST"
            ),
            id=task_id
        )

        return render(
            request,
            "spese/loading_test.html",
            {
                "task": task
            }
        )
    

@login_required
@require_POST
def test_store_confirm_view(request, task_id):
    """
    Confirms the current test and deletes all previous tests for the same store.
    """

    task = get_object_or_404(
        Task.objects.filter(user=request.user),
        id=task_id,
        task_type='STORE_TEMPLATE_TEST',
        status='COMPLETED'
    )
    
    if hasattr(task, 'confirmed'):
        task.confirmed = True
        task.save()

    receipt_test = task.receipt_test
    if not receipt_test:
        messages.error(request, _("Error: no test receipt associated with this task."))
        return redirect('supermercato_list') 
    
    store = receipt_test.tested_store
    
    old_receipt_tests = ReceiptTest.objects.filter(
        user=request.user,
        tested_store=store
    ).exclude(id=receipt_test.id)
    
    # Count how many tests will be eliminated
    num_test_del = old_receipt_tests.count()
    
    # Delete old ReceiptTest
    if num_test_del > 0:
        old_receipt_tests.delete()
        
   
    if num_test_del > 0:
        messages.success(
            request,
            _(
                'Test confirmed! Configuration for "%(store_name)s" saved. '
                '%(num_deleted)s previous tests deleted.'
            ) % {
                'store_name': store.name,
                'num_deleted': num_test_del
            }
        )
    else:
        messages.success(
            request,
            _(
                'Test confirmed! Configuration for "%(store_name)s" saved.'
            ) % {
                'store_name': store.name
            }
        )
        
    return redirect('supermercato_detail', pk=store.pk)

# ------------------------------------------------------------------
# LOGIN-LOGOUT-HOME
# ------------------------------------------------------------------
def login_view(request):
    """Login page"""
    if request.user.is_authenticated:
        return redirect('report_spese')  
    
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            
            if user is not None:
                login(request, user)
                messages.success(
                    request,
                    _('Welcome back, %(username)s!') % {'username': username}
                )
                next_url = request.GET.get('next', 'report_spese')
                return redirect(next_url)
        else:
            messages.error(request, _('Username or password not valid.'))
    else:
        form = AuthenticationForm()
    
    return render(request, 'registration/login.html', {'form': form})

@login_required
def logout_view(request):
    """Logout"""
    logout(request)
    messages.info(request, _('Successfully disconnected.'))
    return redirect('login')

@login_required
def home_view(request):
    """Dashboard home after login not used the real homepage is ReportSpeseView"""
    context = {
        'num_scontrini': Receipt.objects.filter(user=request.user).count(),
        'num_supermercati': StoreTemplate.objects.filter(user=request.user).count(),
        'num_articoli': Product.objects.filter(user=request.user).count(),
    }
    return render(request, 'spese/home.html', context)


#HOME PAGE
class ReportSpeseView(LoginRequiredMixin, TemplateView):
    template_name = 'spese/report_spese.html'

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)
        
        # 1. Date filter (default: last 30 days)
        end_date_str = self.request.GET.get('end_date')
        start_date_str = self.request.GET.get('start_date')
        
        end_date = timezone.datetime.strptime(end_date_str, '%Y-%m-%d').date() if end_date_str else timezone.now().date()
        start_date = timezone.datetime.strptime(start_date_str, '%Y-%m-%d').date() if start_date_str else (end_date - timedelta(days=30))
        
        context['start_date'] = start_date
        context['end_date'] = end_date

        # 2. Filter confirmed receipts for the period
        qs = Receipt.objects.filter(user=self.request.user, confirmed=True)
        qs = qs.filter(receipt_date__gte=start_date, receipt_date__lte=end_date)

        # 3. KPIs
        total_spent = qs.aggregate(total=Sum('total'))['total'] or 0
        receipts_count = qs.count()
        average_per_receipt = (total_spent / receipts_count) if receipts_count > 0 else 0

        # 4. Top 5 Stores
        top_stores = qs.values('store__name').annotate(
            total=Sum('total')
        ).order_by('-total')[:5]

        # 5. Data for the category chart
        category_data_qs = qs.values('items__product__category__name').annotate(total=Sum('items__price')).order_by('-total')
        category_labels = [item['items__product__category__name'] or 'Senza Categoria' for item in category_data_qs]
        category_data = [float(item['total'] or 0) for item in category_data_qs]
        

        # 6. Context update
        context.update({
            'start_date': start_date,
            'end_date': end_date,
            'total_spent': total_spent,
            'receipts_count': receipts_count,
            'average_per_receipt': average_per_receipt,
            'top_stores': top_stores,
            'category_labels': category_labels,
            'category_data': category_data,
        })
        
        return context


# ------------------------------------------------------------------
# SETUP PAGE (CREATE SUPERUSER)
# ------------------------------------------------------------------
def setup_view(request):
    """
    Initial setup page: create the superuser and show what is already configured.
    """
    
    # If superusers already exist, redirect to the home page
    if User.objects.filter(is_superuser=True).exists():
        return redirect('scontrini_list')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email', '')
        password = request.POST.get('password')
        password_confirm = request.POST.get('password_confirm')
        
        # Validations
        if not username or not password:
            messages.error(request, _('Username and password are required.'))
        elif password != password_confirm:
            messages.error(request, _('The passwords do not match.'))
        elif len(password) < 8:
            messages.error(request, _('The password must be at least 8 characters long.'))
        elif User.objects.filter(username=username).exists():
            messages.error(request, _('This username is already in use.'))
        else:
            # Create superuser
            user = User.objects.create_superuser(
                username=username,
                email=email,
                password=password
            )
            
            # Automatically create the UserAIConfig for this user
            UserAIConfig.objects.get_or_create(user=user)
            
            messages.success(
                request,
                _('Superuser "{username}" successfully created! You can now log in.').format(username=username)
            )
            return redirect('admin:login')
    
    context = {
        'num_categorie': len(CATEGORIE_DEFAULT),
        'num_template': len(SUPERMERCATI_DEFAULT),
    }
    
    return render(request, 'spese/setup.html', context)

# ------------------------------------------------------------------
# AI SETTINGS
# ------------------------------------------------------------------
@login_required
def ai_config_detail(request):

    config, _ = UserAIConfig.objects.get_or_create(user=request.user)

    # ENV as fallback
    default_host = os.getenv('OLLAMA_HOST', 'http://host.docker.internal:11434')
    current_input = {
        "host": (config.ollama_host or "").strip() or default_host,
        "modello_ocr": (config.ocr_model or "").strip() or 'qwen2.5vl:7b',
        "modello_analisi": (config.analysis_model or "").strip() or 'gpt-oss:20b',
        "modello_categorizzazione": (config.categorization_model or "").strip() or 'gpt-oss:20b',
        "modello_chat": (config.chat_model or "").strip() or 'gpt-oss:20b'
    }
    
    # Look for the last check task for this user.
    latest_task = Task.objects.filter(
        user=request.user, 
        task_type='OLLAMA_CHECK'
    ).order_by('-updated_at').first()

    needs_new_check = True
    task_to_display = None
    
    if latest_task and latest_task.status == 'COMPLETED':
        time_diff = (timezone.now() - latest_task.updated_at).total_seconds()
        task_input = latest_task.data.get('input', {}) if isinstance(latest_task.data, dict) else json.loads(latest_task.data).get('input', {})
        
        if time_diff < 600 and task_input == current_input:
            needs_new_check = False
            task_to_display = latest_task
    

    if needs_new_check:
        pending_or_processing_task = Task.objects.filter(
            user=request.user,
            task_type='OLLAMA_CHECK',
            status__in=['PENDING', 'PROCESSING']
        ).order_by('-created_at').first()
        
        if pending_or_processing_task:
            task_input = pending_or_processing_task.data.get('input', {}) if isinstance(pending_or_processing_task.data, dict) else json.loads(pending_or_processing_task.data).get('input', {})
            if task_input == current_input:
                needs_new_check = False
                task_to_display = pending_or_processing_task
    

    if needs_new_check:
        new_task = Task.objects.create(
            user=request.user,
            task_type='OLLAMA_CHECK',
            status='PENDING',
            step='Awaiting processing...',
            data={'input': current_input, 'output': {}}
        )
        task_to_display = new_task

    task_output = {}
    if task_to_display and task_to_display.data:
        try:
            data_dict = json.loads(task_to_display.data) if isinstance(task_to_display.data, str) else task_to_display.data
            task_output = data_dict.get('output', {})
        except (json.JSONDecodeError, AttributeError):
            task_output = {}

    context = {
        'config': config,
        'task': task_to_display,
        'current_input': current_input,
        'task_output': task_output,  
        'needs_new_check': needs_new_check
    }
    
    return render(request, 'spese/ai_config_detail.html', context)

@login_required
def ai_config_update(request):
    config, created = UserAIConfig.objects.get_or_create(user=request.user)
    
    available_models = []
    is_ollama_reachable = False
    
    # Look for the last completed OLLAMA_CHECK task for this user
    latest_check = Task.objects.filter(
        user=request.user,
        task_type='OLLAMA_CHECK',
        status='COMPLETED'
    ).order_by('-updated_at').first()
    
    # If it exists and is recent (less than 10 minutes old)
    if latest_check and latest_check.data:
        time_diff = (timezone.now() - latest_check.updated_at).total_seconds()
        if time_diff < 600: # 600 seconds = 10 min
            try:
                task_data = json.loads(latest_check.data) if isinstance(latest_check.data, str) else latest_check.data
                output = task_data.get('output', {})
                
                available_models = output.get('modelli_disponibili', [])
                is_ollama_reachable = output.get('host_raggiungibile', False)
                
            except (json.JSONDecodeError, AttributeError, TypeError):
                # If there is a parsing error, keep the lists empty
                pass
    
    if request.method == 'POST':
        form = UserAIConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, _('AI configuration successfully saved!'))
            return redirect('ai_config_detail')
        else:
            pass
    else:
        form = UserAIConfigForm(instance=config)
    
    return render(request, 'spese/ai_config_update.html', {
        'form': form,
        'available_models': available_models,
        'is_ollama_reachable': is_ollama_reachable,
    })



# ------------------------------------------------------------------
# CATEGORY
# ------------------------------------------------------------------
class CategoryListView(LoginRequiredMixin, ListView):
    model = Category
    template_name = "categories/category_list.html"
    context_object_name = "categories"

    def get_queryset(self):
        return Category.objects.filter(
            user=self.request.user
        ).order_by("name")

class CategoryCreateView(LoginRequiredMixin, CreateView):
    model = Category
    form_class = CategoryForm
    template_name = "spese/category_form.html"
    success_url = reverse_lazy("category_list")

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

class CategoryUpdateView(LoginRequiredMixin, UpdateView):
    model = Category
    form_class = CategoryForm
    template_name = "spese/category_form.html"
    success_url = reverse_lazy("category_list")

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

class CategoryDeleteView(LoginRequiredMixin, DeleteView):
    model = Category
    template_name = "spese/category_confirm_delete.html"
    success_url = reverse_lazy("category_list")

    def get_queryset(self):
        return Category.objects.filter(user=self.request.user)


# ------------------------------------------------------------------
# CHAT STORE TEMPLATE
# ------------------------------------------------------------------
@login_required
def chat_task(request):
    task = Task.objects.filter(
        user=request.user,
        task_type="CHAT",
        status__in=["PENDING", "PROCESSING"]
    ).first()

    if not task:
        task = Task.objects.create(
            user=request.user,
            task_type="CHAT",
            status="PROCESSING",
            step="In attesa del prossimo messaggio",
            progress=100,
            data={
                "messaggi": []
            }
        )

    return JsonResponse({
        "task_id": task.id,
        "datas": task.data,
        "stato": task.status,
        "step": task.step
    })