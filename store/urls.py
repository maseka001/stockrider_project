# store/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Products
    path('products/', views.product_list, name='product_list'),
    path('products/new/', views.product_create, name='product_create'),
    path('products/<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('products/<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('products/<int:pk>/restock/', views.product_restock, name='product_restock'),

    # Sales
    path('sales/', views.sale_list, name='sale_list'),
    path('sales/new/', views.sale_create, name='sale_create'),

    #Expenses
    path('expenses/', views.expense_list, name='expense_list'),

    # Reports
    path('reports/', views.reports, name='reports'),
    path('reports/pdf/day/', views.download_day_sales_pdf, name='download_day_sales_pdf'),
    path('download-daily-sales-pdf/', views.download_daily_sales_pdf, name='download_daily_sales_pdf'),
    path('download-monthly-sales-pdf/', views.download_monthly_sales_pdf, name='download_monthly_sales_pdf'),
    path('download/custom-report/', views.download_custom_report_pdf, name='download_custom_report_pdf'),
    
    path('custom-report/', views.custom_report, name='custom_report'),

]
