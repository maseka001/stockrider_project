# store/admin.py
from django.contrib import admin
from .models import Product, Sale

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'brand', 'part_number', 'motorcycle_model', 'quantity', 'selling_price')
    search_fields = ('name', 'part_number', 'brand', 'motorcycle_model')
    list_filter = ('brand', 'motorcycle_model')

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ('product', 'quantity', 'total_price', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('product__name',)
