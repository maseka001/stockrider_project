# store/forms.py
from django import forms
from .models import Product, Sale
from django.utils import timezone

class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'

class SaleForm(forms.ModelForm):
    class Meta:
        model = Sale
        fields = ['product', 'quantity', 'discount']
        widgets = {
            'discount': forms.NumberInput(attrs={
                'placeholder': 'Enter discount amount in TSh',
                'min': '0',
                'step': 'any',
                'class': 'form-control'
            })
        }

class CustomReportForm(forms.Form):
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    product = forms.ModelChoiceField(
        required=False,
        queryset=Product.objects.all(),
        empty_label="All Products",  # ✅ This adds the "All Products" option
        widget=forms.Select(attrs={'class': 'form-select'})
    )