# store/models.py

from django.db import models
from django.utils import timezone

class Product(models.Model):
    name = models.CharField(max_length=200)
    brand = models.CharField(max_length=100, blank=True)
    part_number = models.CharField(max_length=100, blank=True)
    motorcycle_model = models.CharField(max_length=200, blank=True)
    quantity = models.PositiveIntegerField(default=0)
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    selling_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
    def get_profit_margin(self):
        """Calculate profit margin per unit"""
        return self.selling_price - self.cost_price
    
    def get_profit_percentage(self):
        """Calculate profit percentage"""
        if self.cost_price > 0:
            profit_margin = self.get_profit_margin()
            return round((profit_margin / self.cost_price) * 100, 1)
        return 0
    
    def is_low_stock(self):
        return self.quantity <= 5

class Sale(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # 💰 new field
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # Calculate total = (price * qty) - discount
        gross_total = self.quantity * self.product.selling_price
        if self.discount > gross_total:
            raise ValueError("Discount cannot exceed total amount")
        self.total_price = gross_total - self.discount

        # Stock reduction logic (only when creating new sale)
        if self.pk is None:
            if self.quantity > self.product.quantity:
                raise ValueError("Insufficient stock")
            self.product.quantity -= self.quantity
            self.product.save()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} pcs"

    def profit(self):
        """Calculate profit: (selling price after discount) - cost price"""
        if self.product.cost_price:
            total_cost = self.product.cost_price * self.quantity
            return self.total_price - total_cost
        return 0