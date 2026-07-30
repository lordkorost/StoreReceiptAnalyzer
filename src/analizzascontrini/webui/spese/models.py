from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _


class Category(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="categories"
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name")
    )

    description = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Description"),
        help_text=_(
            "Optional description explaining what belongs to this category"
        )
    )

    class Meta:
        verbose_name = _("Category")
        verbose_name_plural = _("Categories")

        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_category"
            )
        ]

    def __str__(self):
        return self.name

class StoreTemplate(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="store_templates"
    )

    name = models.CharField(
        max_length=100,
        verbose_name=_("Name")
    )

    keyword = models.CharField(
        max_length=100,
        verbose_name=_("Keyword"),
        help_text=_(
            "Keyword used to identify the store from OCR "
            "(e.g. 'DUEPI', 'CONAD', 'COOP')"
        )
    )

    # ============================================
    # LLM PROMPT
    # ============================================

    prompt_instruction = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Prompt instructions"),
        help_text=_(
            "Specific rules for extracting receipt items "
            "for this store"
        )
    )

    # ============================================
    # RECEIPT NORMALIZATION REGEX
    # ============================================

    quantity_regex = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Quantity regex")
    )

    ignored_lines = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Ignored lines")
    )

    discount_regex = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        verbose_name=_("Discount regex"),
        help_text=_(
            "Regex used to identify discount lines "
            "(e.g. 'Taglio Prezzo|SCONTO OFFERTA')"
        )
    )

    remove_vat_pattern = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("VAT removal pattern"),
        help_text=_(
            "Regex used to remove VAT markers "
            "(e.g. '\\s+VI\\*' or '\\s+\\d+%')"
        )
    )

    store_keywords = models.JSONField(
        default=list,
        blank=True,
        verbose_name=_("Store keywords"),
        help_text=_(
            "List of keywords used to identify the store name "
            "(e.g. ['duepi', 'ipercoop'])"
        )
    )

    # ============================================
    # FLAGS
    # ============================================

    repeated_items = models.BooleanField(
        default=False,
        verbose_name=_("Repeated items"),
        help_text=_(
            "If enabled, the store may have the same item multiple "
            "times (e.g. deli counter items)"
        )
    )

    class Meta:
        verbose_name = _("Store template")
        verbose_name_plural = _("Store templates")
        
        # ✅ AGGIUNGI QUESTO VINCOLO COMPOSTO
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'name'],
                name='unique_user_store_name'
            )
        ]

class Product(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="products"
    )

    name = models.CharField(
        max_length=255,
        verbose_name=_("Name")
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Category")
    )

    brand = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Brand")
    )

    class Meta:
        verbose_name = _("Product")
        verbose_name_plural = _("Products")

        constraints = [
            models.UniqueConstraint(
                fields=["user", "name"],
                name="unique_user_product_name"
            )
        ]

    def __str__(self):
        return self.name

class ProductDictionary(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="product_dictionaries"
    )

    store = models.ForeignKey(
        StoreTemplate,
        on_delete=models.CASCADE,
        related_name="product_dictionary",
        verbose_name=_("Store")
    )

    receipt_text = models.CharField(
        max_length=255,
        verbose_name=_("Receipt text")
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        verbose_name=_("Product")
    )

    class Meta:
        verbose_name = _("Product dictionary entry")
        verbose_name_plural = _("Product dictionary entries")

        constraints = [
            models.UniqueConstraint(
                fields=["user", "store", "receipt_text"],
                name="unique_user_store_receipt_text"
            )
        ]

    def __str__(self):
        return f"{self.receipt_text} → {self.product}"

class Receipt(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="receipts"
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at")
    )

    receipt_date = models.DateField(
        blank=True,
        null=True,
        verbose_name=_("Receipt date")
    )

    ocr_store_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        verbose_name=_("Store name from OCR")
    )

    store = models.ForeignKey(
        StoreTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Store")
    )

    image = models.ImageField(
        upload_to="receipts/",
        verbose_name=_("Image")
    )

    total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Total")
    )

    confirmed = models.BooleanField(
        default=False,
        verbose_name=_("Confirmed")
    )

    class Meta:
        verbose_name = _("Receipt")
        verbose_name_plural = _("Receipts")

    def __str__(self):
        store_name = (
            self.ocr_store_name
            or (self.store.name if self.store else _("Unknown"))
        )

        date = (
            self.receipt_date.strftime("%d/%m/%Y")
            if self.receipt_date
            else _("Date not specified")
        )

        return (
            f"Receipt #{self.pk} - "
            f"{store_name} ({date}) - "
            f"${self.total}"
        )

class ReceiptItem(models.Model):
    receipt = models.ForeignKey(
        Receipt,
        on_delete=models.CASCADE,
        related_name="items"
    )

    original_text = models.CharField(
        max_length=255,
        verbose_name=_("Original receipt text")
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Product")
    )

    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1,
        verbose_name=_("Quantity")
    )

    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name=_("Unit price")
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name=_("Price")
    )

    discount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00,
        verbose_name=_("Discount")
    )

    class Meta:
        verbose_name = _("Receipt item")
        verbose_name_plural = _("Receipt items")

    def __str__(self):
        return self.original_text

# ============================================
# TEST MODELS
# ============================================
class ReceiptTest(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="receipt_tests"
    )

    tested_store = models.ForeignKey(
        StoreTemplate,
        on_delete=models.CASCADE,
        related_name="tests"
    )

    image = models.ImageField(
        upload_to="tests/"
    )

    ocr_store_name = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    receipt_date = models.DateField(
        blank=True,
        null=True
    )

    total = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00
    )

    task = models.ForeignKey(
        "Task",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="receipt_tests"
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    class Meta:
        verbose_name = "Receipt test"
        verbose_name_plural = "Receipt tests"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Test {self.tested_store.name} - {self.created_at}"

class ReceiptTestItem(models.Model):
    receipt_test = models.ForeignKey(
        ReceiptTest,
        on_delete=models.CASCADE,
        related_name="items"
    )

    original_text = models.CharField(
        max_length=255
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_receipt_items"
    )

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="test_receipt_items"
    )

    quantity = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=1
    )

    unit_price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True
    )

    price = models.DecimalField(
        max_digits=8,
        decimal_places=2
    )

    discount = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=0.00
    )

    class Meta:
        verbose_name = "Receipt test item"
        verbose_name_plural = "Receipt test items"

    def __str__(self):
        return self.original_text


class UserAIConfig(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="ai_config"
    )

    # ============================================
    # OLLAMA
    # ============================================

    ollama_host = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text=_(
            "Ollama URL (e.g. http://192.168.1.45:11434). "
            "Leave empty to use the system default."
        )
    )

    # ============================================
    # MODELS
    # ============================================

    ocr_model = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    analysis_model = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    categorization_model = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    chat_model = models.CharField(
        max_length=100,
        blank=True,
        default=""
    )

    # ============================================
    # PROMPTS
    # ============================================

    ocr_prompt = models.TextField(
        blank=True,
        default=""
    )

    analysis_prompt = models.TextField(
        blank=True,
        default=""
    )

    categorization_prompt = models.TextField(
        blank=True,
        default=""
    )

    class Meta:
        verbose_name = _("User AI configuration")
        verbose_name_plural = _("User AI configurations")

    def __str__(self):
        return f"AI config for {self.user.username}"
    
# ============================================
# TASKS
# ============================================
class Task(models.Model):
    TASK_STATES = [
        ("PENDING", _("Pending")),
        ("PROCESSING", _("Processing")),
        ("COMPLETED", _("Completed")),
        ("FAILED", _("Failed")),
    ]

    TASK_TYPES = [
        ("OCR_EXTRACTION", _("OCR and raw text extraction")),
        ("CATEGORIZATION", _("LLM category assignment")),
        ("STORE_TEMPLATE_TEST", _("Store template test")),
        ("OLLAMA_CHECK", _("Ollama connection and model check")),
        ("CHAT", _("Assistant chat")),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="tasks"
    )

    receipt = models.ForeignKey(
        "Receipt",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tasks"
    )

    receipt_test = models.ForeignKey(
        "ReceiptTest",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="tasks"
    )

    task_type = models.CharField(
        max_length=50,
        choices=TASK_TYPES,
        verbose_name=_("Task type")
    )

    status = models.CharField(
        max_length=100,
        choices=TASK_STATES,
        default="PENDING",
        verbose_name=_("Status")
    )

    step = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name=_("Current step")
    )

    error = models.TextField(
        blank=True,
        null=True,
        verbose_name=_("Error")
    )

    progress = models.IntegerField(
        default=0,
        verbose_name=_("Progress")
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("Data"),
        help_text=_(
            "Debug logs, results and other task-related data"
        )
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Created at")
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at")
    )

    confirmed = models.BooleanField(
        default=False,
        verbose_name=_("Confirmed"),
        help_text=_(
            "True if the task result has been confirmed by the user"
        )
    )

    class Meta:
        verbose_name = _("Task")
        verbose_name_plural = _("Tasks")

    def __str__(self):
        return (
            f"[{self.get_task_type_display()}] - "
            f"{self.user.username} "
            f"({self.get_status_display()})"
        )

class VersionCheck(models.Model):
    latest_version = models.CharField(
        max_length=50,
        blank=True,
        null=True
    )

    last_check = models.DateTimeField(
        blank=True,
        null=True
    )

    update_url = models.URLField(
        blank=True,
        null=True
    )

    created_at = models.DateTimeField(
            auto_now_add=True,
            verbose_name=_("Created at")
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("Updated at")
    )
    
    class Meta:
        verbose_name = "Version Check"
        verbose_name_plural = "Version Checks"

    
    def __str__(self):
        return f"Ultima versione: {self.latest_version or 'None'}"