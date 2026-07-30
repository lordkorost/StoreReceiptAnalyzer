from django import forms
from django.forms import JSONField
from django.utils.translation import gettext_lazy as _
from .models import StoreTemplate,UserAIConfig,Category
import json


class JSONTextarea(forms.Textarea):
    """Custom widget for JSON fields that correctly formats the value."""
    
    def format_value(self, value):
        if value is None:
            return '[]'
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (json.JSONDecodeError, ValueError):
                return value
        return json.dumps(value, ensure_ascii=False, indent=2)

class StoreTemplateForm(forms.ModelForm):
    ignored_lines = JSONField(
        widget=JSONTextarea(attrs={'rows': 3, 'class': 'form-control font-monospace'}),
        required=False,
        help_text=_('JSON list of patterns to skip during parsing.')
    )
    store_keywords = JSONField(
        widget=JSONTextarea(attrs={'rows': 3, 'class': 'form-control font-monospace'}),
        required=False,
        help_text=_('JSON list of keywords to identify the store name.')
    )
    
    class Meta:
        model = StoreTemplate
        fields = [
            'name', 'keyword', 'repeated_items', 'prompt_instruction',
            'quantity_regex', 'discount_regex', 'remove_vat_pattern',
            'ignored_lines', 'store_keywords'
        ]

class UserAIConfigForm(forms.ModelForm):
    class Meta:
        model = UserAIConfig
        fields = [
            'ollama_host', 
            'ocr_model', 
            'analysis_model', 
            'categorization_model', 
            'chat_model',
            'ocr_prompt', 
            'analysis_prompt', 
            'categorization_prompt'
        ]
        widgets = {
            'ollama_host': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'http://192.168.1.45:11434'
            }),
            'ocr_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'qwen2.5vl:7b'}),
            'analysis_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'gpt-oss:20b'}),
            'categorization_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'gpt-oss:20b'}),
            'chat_model': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'gpt-oss:20b'}),
            'ocr_prompt': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 6}),
            'analysis_prompt': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 6}),
            'categorization_prompt': forms.Textarea(attrs={'class': 'form-control font-monospace', 'rows': 6}),
        }

class CategoryForm(forms.ModelForm):

    class Meta:
        model = Category
        fields = ["name", "description"]

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()

        qs = Category.objects.filter(
            user=self.user,
            name__iexact=name,
        )

        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise forms.ValidationError(
                "A category with this name already exists."
            )

        return name