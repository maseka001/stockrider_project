# store/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from .models import Product, Sale
from django.contrib import messages
from django.db import models
from django.db.models import Sum, Q
from datetime import datetime, timedelta, date
from .forms import ProductForm, SaleForm, CustomReportForm
from django.utils import timezone
from django.http import HttpResponse
from io import BytesIO
from reportlab.lib.pagesizes import letter, A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle
from reportlab.lib.utils import ImageReader

@login_required
def dashboard(request):
    total_products = Product.objects.count()
    total_sales_today = Sale.objects.filter(created_at__date=datetime.today()).aggregate(total=Sum('total_price'))['total'] or 0
    low_stock = Product.objects.filter(quantity__lte=5).count()
    top_products = Sale.objects.values('product__name').annotate(total_qty=Sum('quantity')).order_by('-total_qty')[:5]
    return render(request, 'store/dashboard.html', locals())

# Product Views
@login_required
def product_list(request):
    query = request.GET.get('q', '').strip()
    products = Product.objects.all()

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(brand__icontains=query) |
            Q(part_number__icontains=query) |
            Q(motorcycle_model__icontains=query)
        )

    return render(request, 'store/product_list.html', {
        'products': products,
    })

@login_required
def product_create(request):
    if request.method == "POST":
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Product created successfully!")
            return redirect('product_list')
    else:
        form = ProductForm()
    return render(request, 'store/product_form.html', {'form': form})

@login_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        form = ProductForm(request.POST, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, "Product updated successfully!")
            return redirect('product_list')
    else:
        form = ProductForm(instance=product)
    return render(request, 'store/product_form.html', {'form': form})

@login_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        product.delete()
        messages.success(request, "Product deleted successfully!")
        return redirect('product_list')
    return render(request, 'store/product_confirm_delete.html', {'product': product})

@login_required
def product_restock(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == "POST":
        qty = int(request.POST.get('quantity', 0))
        product.quantity += qty
        product.save()
        messages.success(request, f"Restocked {qty} units!")
        return redirect('product_list')
    return render(request, 'store/product_form.html', {'product': product, 'restock': True})

# Sales Views
@login_required
def sale_list(request):
    today = timezone.localdate()
    sales = Sale.objects.filter(created_at__date=today).order_by('-created_at')
    return render(request, 'store/sale_list.html', {'sales': sales, 'today': today})

@login_required
def sale_create(request):
    if request.method == "POST":
        form = SaleForm(request.POST)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, "Sale recorded successfully!")
                return redirect('sale_list')
            except ValueError as e:
                messages.error(request, str(e))
    else:
        form = SaleForm()
    return render(request, 'store/sale_form.html', {'form': form})


#Expense Views
@login_required
def expense_list(request):
    return render(request, 'store/expenses.html')

# Reports View
@login_required
def reports(request):
    last_30_days = timezone.now() - timedelta(days=30)

    # Daily summary (last 30 days)
    daily_sales = (
        Sale.objects.filter(created_at__gte=last_30_days)
        .values(date=models.F('created_at__date'))
        .annotate(total_sales=Sum('total_price'), total_quantity=Sum('quantity'))
        .order_by('-date')
    )

    # Today's individual sales
    today = timezone.localdate()
    day_sales = Sale.objects.filter(created_at__date=today).order_by('-created_at')

    # Top products
    top_products = (
        Sale.objects.values('product__name', 'product__brand')
        .annotate(total_sold=Sum('quantity'), total_revenue=Sum('total_price'))
        .order_by('-total_sold')[:5]
    )

    # Low stock products
    low_stock = Product.objects.filter(quantity__lte=5)

    # Monthly summary
    monthly_sales = (
        Sale.objects.filter(created_at__year=today.year)
        .values(month=models.functions.ExtractMonth('created_at'))
        .annotate(total_sales=Sum('total_price'), total_quantity=Sum('quantity'))
        .order_by('month')
    )

    # Custom Report Form
    form = CustomReportForm(request.GET or None)
    sales = Sale.objects.none()
    total_sales_custom = 0
    total_profit = 0

    if form.is_valid():
        sales = Sale.objects.all().select_related('product')
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        product = form.cleaned_data.get('product')

        if start_date:
            sales = sales.filter(created_at__date__gte=start_date)
        if end_date:
            sales = sales.filter(created_at__date__lte=end_date)
        if product:
            sales = sales.filter(product=product)

        total_sales_custom = sales.aggregate(total=Sum('total_price'))['total'] or 0
        
        # Calculate total profit
        total_profit = 0
        for sale in sales:
            if sale.product.cost_price:
                cost_total = sale.product.cost_price * sale.quantity
                total_profit += (sale.total_price - cost_total)

    return render(request, 'store/report.html', {
        'daily_sales': daily_sales,
        'day_sales': day_sales,
        'monthly_sales': monthly_sales,
        'top_products': top_products,
        'low_stock': low_stock,
        'form': form,
        'sales': sales,
        'total_sales': total_sales_custom,
        'total_profit': total_profit,
    })

@login_required
def download_day_sales_pdf(request):
    today = timezone.localdate()
    sales = Sale.objects.filter(created_at__date=today).order_by('created_at')

    # PDF setup
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ===== HEADER =====
    logo_path = "/home/maseka/Documents/stockrider_project/logo.jpg"
    try:
        logo = ImageReader(logo_path)
        p.drawImage(logo, 50, height - 80, width=100, height=85, mask='auto')
    except:
        pass

    # Business name and report title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "HAKEEM SPARE PARTS")
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 75, "Today's Sales Report")

    # Thin line separator
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.5)
    p.line(40, height - 90, width - 40, height - 90)

    # Report meta information
    p.setFont("Helvetica", 11)
    y = height - 110
    p.drawString(50, y, f"Date: {today.strftime('%Y-%m-%d')}")
    y -= 30

    # ===== TABLE DATA =====
    data = [["S/N", "Time", "Product", "Qty", "Unit Price", "Discount", "Total", "Profit"]]
    total_amount = 0
    total_profit = 0

    for i, sale in enumerate(sales, start=1):
        total_amount += sale.total_price
        
        # Calculate profit
        profit = 0
        if sale.product.cost_price:
            cost_total = sale.product.cost_price * sale.quantity
            profit = sale.total_price - cost_total
            total_profit += profit

        data.append([
            i,
            sale.created_at.strftime("%H:%M"),
            sale.product.name[:25],
            sale.quantity,
            f"{sale.product.selling_price:,.0f}",
            f"{sale.discount or 0:,.0f}",
            f"{sale.total_price:,.0f}",
            f"{profit:,.0f}"
        ])

    # Grand Total row
    data.append(["", "", "", "", "", "Grand Total:", f"{total_amount:,.0f}", f"{total_profit:,.0f}"])

    # ===== STYLED TABLE =====
    table = Table(data, colWidths=[30, 50, 120, 40, 60, 60, 70, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0077b6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -2), colors.whitesmoke),
        ("BACKGROUND", (-3, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (-3, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
    ]))

    # Draw table
    w, h = table.wrapOn(p, width, height)
    table.drawOn(p, 30, y - h)

    # Finalize PDF
    p.showPage()
    p.save()
    buffer.seek(0)

    # Force download
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Day_Sales_{today}.pdf"'
    return response

@login_required
def download_daily_sales_pdf(request):
    today = timezone.localdate()
    last_30_days = timezone.now() - timedelta(days=30)

    # Aggregate daily totals with profit calculation
    daily_sales = (
        Sale.objects.filter(created_at__gte=last_30_days)
        .values('created_at__date')
        .annotate(
            total_sales=Sum('total_price'),
            total_quantity=Sum('quantity'),
            total_profit=Sum(
                models.F('total_price') - 
                (models.F('product__cost_price') * models.F('quantity'))
            )
        )
        .order_by('-created_at__date')
    )

    # PDF setup
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ===== HEADER =====
    logo_path = "/home/maseka/Documents/stockrider_project/logo.jpg"
    try:
        logo = ImageReader(logo_path)
        p.drawImage(logo, 50, height - 80, width=100, height=85, mask='auto')
    except:
        pass

    # Business name and report title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "HAKEEM SPARE PARTS")
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 75, "Daily Sales Summary (Last 30 Days)")

    # Thin line separator
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.5)
    p.line(40, height - 90, width - 40, height - 90)

    # Report meta info
    p.setFont("Helvetica", 11)
    y = height - 110
    p.drawString(50, y, f"Generated on: {today.strftime('%Y-%m-%d')}")
    y -= 30

    # ===== TABLE DATA =====
    data = [["S/N", "Date", "Total Quantity", "Total Sales (Tsh)", "Total Profit (Tsh)"]]
    total_amount = 0
    total_qty = 0
    total_profit = 0

    for i, day in enumerate(daily_sales, start=1):
        total_sales = day['total_sales'] or 0
        total_quantity = day['total_quantity'] or 0
        day_profit = day['total_profit'] or 0
        
        total_amount += total_sales
        total_qty += total_quantity
        total_profit += day_profit

        data.append([
            i,
            day['created_at__date'].strftime("%Y-%m-%d") if isinstance(day['created_at__date'], date) else day['created_at__date'],
            f"{total_quantity:,}",
            f"{total_sales:,.0f}",
            f"{day_profit:,.0f}"
        ])

    # Add Grand Total row
    data.append(["", "Grand Total", f"{total_qty:,}", f"{total_amount:,.0f}", f"{total_profit:,.0f}"])

    # ===== STYLED TABLE =====
    table = Table(data, colWidths=[40, 100, 80, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0077b6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -2), colors.whitesmoke),
        ("BACKGROUND", (-3, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (-3, -1), (-1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (-1, -1), colors.black),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
    ]))

    # Draw table
    w, h = table.wrapOn(p, width, height)
    table.drawOn(p, 45, y - h)

    # Finalize PDF
    p.showPage()
    p.save()
    buffer.seek(0)

    # Force download
    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Daily_Sales_Summary_{today}.pdf"'
    return response

@login_required
def download_monthly_sales_pdf(request):
    today = timezone.localdate()
    current_year = today.year

    # Query monthly aggregated sales with profit
    monthly_summary = (
        Sale.objects.filter(created_at__year=current_year)
        .values("created_at__month")
        .annotate(
            total_sales=Sum("total_price"),
            total_quantity=Sum("quantity"),
            total_profit=Sum(
                models.F('total_price') - 
                (models.F('product__cost_price') * models.F('quantity'))
            )
        )
        .order_by("created_at__month")
    )

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ===== HEADER =====
    logo_path = "/home/maseka/Documents/stockrider_project/logo.jpg"
    try:
        logo = ImageReader(logo_path)
        p.drawImage(logo, 50, height - 80, width=100, height=85, mask='auto')
    except:
        pass

    # Business name and report title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "HAKEEM SPARE PARTS")
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 75, f"Monthly Sales Report - {current_year}")

    # Separator line
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.5)
    p.line(40, height - 90, width - 40, height - 90)

    # Meta info
    p.setFont("Helvetica", 11)
    y = height - 110
    p.drawString(50, y, f"Generated on: {today.strftime('%Y-%m-%d')}")
    y -= 30

    # Table data
    data = [["S/N", "Month", "Total Quantity", "Total Sales (Tsh)", "Total Profit (Tsh)"]]
    total_amount = 0
    total_qty = 0
    total_profit = 0

    for i, month_data in enumerate(monthly_summary, start=1):
        month_num = month_data["created_at__month"]
        total_sales = month_data["total_sales"] or 0
        total_quantity = month_data["total_quantity"] or 0
        month_profit = month_data["total_profit"] or 0
        
        total_amount += total_sales
        total_qty += total_quantity
        total_profit += month_profit
        
        month_name = date(1900, month_num, 1).strftime("%B")

        data.append([i, month_name, f"{total_quantity:,}", f"{total_sales:,.0f}", f"{month_profit:,.0f}"])

    data.append(["", "Grand Total", f"{total_qty:,}", f"{total_amount:,.0f}", f"{total_profit:,.0f}"])

    # Styled table
    table = Table(data, colWidths=[40, 100, 80, 100, 100])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0077b6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -2), colors.whitesmoke),
        ("BACKGROUND", (-3, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (-3, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
    ]))

    w, h = table.wrapOn(p, width, height)
    table.drawOn(p, 45, y - h)

    # Finalize PDF
    p.showPage()
    p.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="Monthly_Sales_{current_year}.pdf"'
    return response

@login_required
def download_custom_report_pdf(request):
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    product_id = request.GET.get('product')

    sales = Sale.objects.all().select_related('product')
    if start_date:
        sales = sales.filter(created_at__date__gte=start_date)
    if end_date:
        sales = sales.filter(created_at__date__lte=end_date)
    if product_id:
        sales = sales.filter(product_id=product_id)

    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter

    # ===== HEADER =====
    logo_path = "/home/maseka/Documents/stockrider_project/logo.jpg"
    try:
        logo = ImageReader(logo_path)
        p.drawImage(logo, 50, height - 80, width=100, height=85, mask='auto')
    except:
        pass

    # Business name and report title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, "HAKEEM SPARE PARTS")
    p.setFont("Helvetica-Bold", 14)
    p.drawCentredString(width / 2, height - 75, "Custom Sales Report")

    # Separator line
    p.setStrokeColor(colors.grey)
    p.setLineWidth(0.5)
    p.line(40, height - 90, width - 40, height - 90)

    # Meta info
    p.setFont("Helvetica", 11)
    y = height - 110
    today = timezone.now().strftime("%Y-%m-%d %H:%M")
    p.drawString(50, y, f"Generated on: {today}")
    y -= 20
    if start_date or end_date:
        p.drawString(50, y, f"Period: {start_date or '---'} to {end_date or '---'}")
        y -= 20
    if product_id:
        product = Product.objects.get(id=product_id)
        p.drawString(50, y, f"Product: {product.name}")
        y -= 30
    else:
        p.drawString(50, y, "Product: All")
        y -= 30

    # Table data
    data = [["S/N", "Date", "Product", "Qty", "Unit Price", "Discount", "Total", "Profit"]]
    total_amount = 0
    total_profit = 0
    
    for i, sale in enumerate(sales, start=1):
        total_amount += sale.total_price
        
        # Calculate profit
        profit = 0
        if sale.product.cost_price:
            cost_total = sale.product.cost_price * sale.quantity
            profit = sale.total_price - cost_total
            total_profit += profit

        data.append([
            i,
            sale.created_at.strftime("%Y-%m-%d"),
            sale.product.name[:20],
            sale.quantity,
            f"{sale.product.selling_price:,.0f}",
            f"{sale.discount or 0:,.0f}",
            f"{sale.total_price:,.0f}",
            f"{profit:,.0f}"
        ])
    
    data.append(["", "", "", "", "", "Grand Total:", f"{total_amount:,.0f}", f"{total_profit:,.0f}"])

    # Styled table
    table = Table(data, colWidths=[30, 70, 110, 40, 60, 60, 70, 60])
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0077b6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 10),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND", (0, 1), (-1, -2), colors.whitesmoke),
        ("BACKGROUND", (-3, -1), (-1, -1), colors.lightgrey),
        ("FONTNAME", (-3, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 1), (-1, -1), 7),
    ]))

    w, h = table.wrapOn(p, width, height)
    table.drawOn(p, 30, y - h)

    p.showPage()
    p.save()
    buffer.seek(0)

    response = HttpResponse(buffer, content_type="application/pdf")
    response['Content-Disposition'] = 'attachment; filename="Custom_Report.pdf"'
    return response

@login_required
def custom_report(request):
    form = CustomReportForm(request.GET or None)
    sales = Sale.objects.none()

    if form.is_valid():
        sales = Sale.objects.all()
        start_date = form.cleaned_data.get('start_date')
        end_date = form.cleaned_data.get('end_date')
        month = form.cleaned_data.get('month')
        year = form.cleaned_data.get('year')
        product = form.cleaned_data.get('product')

        if start_date:
            sales = sales.filter(created_at__date__gte=start_date)
        if end_date:
            sales = sales.filter(created_at__date__lte=end_date)
        if month:
            sales = sales.filter(created_at__month=month)
        if year:
            sales = sales.filter(created_at__year=year)
        if product:
            sales = sales.filter(product=product)

    total_sales = sales.aggregate(total=Sum('total_price'))['total'] or 0
    total_quantity = sales.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0

    return render(request, 'store/custom_report_tab.html', {
        'form': form,
        'sales': sales,
        'total_sales': total_sales,
        'total_quantity': total_quantity,
    })