from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import producer_required
from .forms import ProductForm, StockUpdateForm, UK_ALLERGENS
from .models import Category, Product


def product_list(request):
    products = Product.objects.filter(
        stock_quantity__gt=0
    ).exclude(
        availability_status='out_of_season'
    ).select_related('producer', 'category')

    categories = Category.objects.all()
    selected_category = None
    category_slug = request.GET.get('category', '')

    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=selected_category)

    in_season_only = request.GET.get('in_season') == '1'
    if in_season_only:
        products = products.filter(availability_status='in_season')

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'products/product_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': selected_category,
        'in_season_only': in_season_only,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    return render(request, 'products/product_detail.html', {
        'product': product,
        'uk_allergens': UK_ALLERGENS,
    })


def category_list(request):
    categories = Category.objects.annotate(
        product_count=Count('products', filter=Q(
            products__stock_quantity__gt=0
        ) & ~Q(products__availability_status='out_of_season'))
    )
    return render(request, 'products/category_list.html', {'categories': categories})


def products_by_category(request, slug):
    category = get_object_or_404(Category, slug=slug)
    products = Product.objects.filter(
        category=category,
        stock_quantity__gt=0
    ).exclude(
        availability_status='out_of_season'
    ).select_related('producer')

    return render(request, 'products/product_list.html', {
        'page_obj': products,
        'categories': Category.objects.all(),
        'selected_category': category,
        'in_season_only': False,
    })


def product_search(request):
    query = request.GET.get('q', '').strip()
    allergen_excludes = request.GET.getlist('allergen_exclude')

    products = Product.objects.filter(
        stock_quantity__gt=0
    ).exclude(
        availability_status='out_of_season'
    ).select_related('producer', 'category')

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(producer__business_name__icontains=query)
        )

    # TC-015: exclude products containing selected allergens
    for allergen in allergen_excludes:
        products = products.exclude(allergens__contains=allergen)

    return render(request, 'products/search_results.html', {
        'products': products,
        'query': query,
        'uk_allergens': UK_ALLERGENS,
        'allergen_excludes': allergen_excludes,
    })


@producer_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.save(request.user.producer_profile)
            messages.success(request, f'"{product.name}" has been added successfully.')
            return redirect('products:product_detail', pk=product.pk)
    else:
        form = ProductForm()

    return render(request, 'products/product_form.html', {'form': form, 'object': None})


@producer_required
def product_edit(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save(request.user.producer_profile, instance=product)
            messages.success(request, f'"{product.name}" has been updated.')
            return redirect('products:product_detail', pk=product.pk)
    else:
        form = ProductForm(initial={
            'name': product.name,
            'description': product.description,
            'category': product.category,
            'price': product.price,
            'unit': product.unit,
            'stock_quantity': product.stock_quantity,
            'availability_status': product.availability_status,
            'season_start': product.season_start,
            'season_end': product.season_end,
            'allergens': product.allergens,
            'is_organic': product.is_organic,
            'harvest_date': product.harvest_date,
            'best_before': product.best_before,
        })

    return render(request, 'products/product_form.html', {'form': form, 'object': product})


@producer_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    if request.method == 'POST':
        name = product.name
        product.delete()
        messages.success(request, f'"{name}" has been deleted.')
        return redirect('products:producer_dashboard')

    return render(request, 'products/product_confirm_delete.html', {'product': product})


@producer_required
def producer_dashboard(request):
    products = Product.objects.filter(
        producer=request.user.producer_profile
    ).select_related('category').order_by('stock_quantity', 'name')

    total = products.count()
    in_stock = products.filter(stock_quantity__gt=0).count()
    out_of_stock = products.filter(stock_quantity=0).count()

    return render(request, 'products/producer_dashboard.html', {
        'products': products,
        'total': total,
        'in_stock': in_stock,
        'out_of_stock': out_of_stock,
    })


@producer_required
def stock_update(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)

    if request.method == 'POST':
        form = StockUpdateForm(request.POST)
        if form.is_valid():
            product.stock_quantity = form.cleaned_data['stock_quantity']
            product.save()
            messages.success(request, f'Stock for "{product.name}" updated to {product.stock_quantity}.')
            return redirect('products:producer_dashboard')
    else:
        form = StockUpdateForm(initial={'stock_quantity': product.stock_quantity})

    return render(request, 'products/stock_update.html', {'form': form, 'product': product})
