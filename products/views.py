from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import customer_required, producer_required
from accounts.models import Notification, User
from .forms import (
    FarmStoryForm,
    ProductForm,
    ProductReviewForm,
    RecipeForm,
    StockUpdateForm,
    SurplusForm,
    UK_ALLERGENS,
)
from .models import FarmStory, Product, ProductReview, Recipe, Category


def _available_products():
    return Product.objects.filter(
        stock_quantity__gt=0
    ).exclude(
        availability_status='out_of_season'
    ).select_related('producer', 'category')


def _customer_postcode(request):
    if request.user.is_authenticated and hasattr(request.user, 'customer_profile'):
        return request.user.customer_profile.postcode
    return None


def _attach_food_miles(products, postcode):
    if not postcode:
        return products
    for product in products:
        product.food_miles = product.food_miles_from(postcode)
    return products


def product_list(request):
    products = _available_products()

    categories = Category.objects.all()
    selected_category = None
    category_slug = request.GET.get('category', '')

    if category_slug:
        selected_category = get_object_or_404(Category, slug=category_slug)
        products = products.filter(category=selected_category)

    in_season_only = request.GET.get('in_season') == '1'
    if in_season_only:
        products = products.filter(availability_status='in_season')

    organic_only = request.GET.get('organic') == '1'
    if organic_only:
        products = products.filter(is_organic=True)

    paginator = Paginator(products, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    _attach_food_miles(page_obj.object_list, _customer_postcode(request))

    return render(request, 'products/product_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'selected_category': selected_category,
        'in_season_only': in_season_only,
        'organic_only': organic_only,
    })


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    food_miles = product.food_miles_from(_customer_postcode(request))
    reviews = product.reviews.select_related('customer').all()
    recipes = product.recipes.filter(is_published=True).select_related('producer')
    review_order_item = None
    if (
        request.user.is_authenticated
        and request.user.role in ('customer', 'community', 'restaurant')
        and not ProductReview.objects.filter(customer=request.user, product=product).exists()
    ):
        from orders.models import OrderItem

        review_order_item = (
            OrderItem.objects
            .filter(order__customer=request.user, order__status='delivered', product=product)
            .order_by('-order__created_at')
            .first()
        )
    return render(request, 'products/product_detail.html', {
        'product': product,
        'uk_allergens': UK_ALLERGENS,
        'food_miles': food_miles,
        'reviews': reviews,
        'average_rating': product.average_rating,
        'recipes': recipes,
        'review_order_item': review_order_item,
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
    products = _available_products().filter(category=category)
    _attach_food_miles(products, _customer_postcode(request))

    return render(request, 'products/product_list.html', {
        'page_obj': products,
        'categories': Category.objects.all(),
        'selected_category': category,
        'in_season_only': False,
        'organic_only': False,
    })


def product_search(request):
    query = request.GET.get('q', '').strip()
    allergen_excludes = request.GET.getlist('allergen_exclude')

    products = _available_products()

    if query:
        products = products.filter(
            Q(name__icontains=query) |
            Q(description__icontains=query) |
            Q(producer__business_name__icontains=query)
        )

    products = list(products)
    if allergen_excludes:
        products = [
            product for product in products
            if all(allergen not in (product.allergens or []) for allergen in allergen_excludes)
        ]
    _attach_food_miles(products, _customer_postcode(request))

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
            'low_stock_threshold': product.low_stock_threshold,
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
            if not product.is_low_stock:
                Notification.objects.filter(
                    user=request.user,
                    related_product=product,
                    category='stock',
                    is_read=False,
                ).update(is_read=True)
            messages.success(request, f'Stock for "{product.name}" updated to {product.stock_quantity}.')
            return redirect('products:producer_dashboard')
    else:
        form = StockUpdateForm(initial={'stock_quantity': product.stock_quantity})

    return render(request, 'products/stock_update.html', {'form': form, 'product': product})


def surplus_deals(request):
    products = [
        product for product in _available_products().filter(is_surplus=True)
        if product.is_surplus_active
    ]
    _attach_food_miles(products, _customer_postcode(request))
    return render(request, 'products/surplus_deals.html', {'products': products})


@producer_required
def mark_surplus(request, pk):
    product = get_object_or_404(Product, pk=pk, producer=request.user.producer_profile)
    if request.method == 'POST':
        form = SurplusForm(request.POST)
        if form.is_valid():
            product.is_surplus = True
            product.surplus_discount_percent = form.cleaned_data['discount_percent']
            product.surplus_expires_at = form.cleaned_data['expires_at']
            product.surplus_note = form.cleaned_data.get('note', '')
            product.save()

            for user in User.objects.filter(role__in=['customer', 'community', 'restaurant']):
                Notification.objects.create(
                    user=user,
                    title='Surplus deal available',
                    message=f'{product.name} is now {product.surplus_discount_percent}% off from {product.producer.business_name}.',
                    category='surplus',
                    related_product=product,
                )
            messages.success(request, f'"{product.name}" is now listed as a surplus deal.')
            return redirect('products:surplus_deals')
    else:
        form = SurplusForm()
    return render(request, 'products/surplus_form.html', {'form': form, 'product': product})


@producer_required
def recipe_create(request):
    producer = request.user.producer_profile
    if request.method == 'POST':
        form = RecipeForm(request.POST, request.FILES, producer=producer)
        if form.is_valid():
            recipe = form.save(commit=False)
            recipe.producer = producer
            recipe.save()
            form.save_m2m()
            messages.success(request, f'Recipe "{recipe.title}" published.')
            return redirect('products:producer_profile', producer_id=producer.pk)
    else:
        form = RecipeForm(producer=producer)
    return render(request, 'products/content_form.html', {
        'form': form,
        'title': 'Add Recipe',
        'submit_label': 'Publish Recipe',
    })


@producer_required
def story_create(request):
    producer = request.user.producer_profile
    if request.method == 'POST':
        form = FarmStoryForm(request.POST, request.FILES)
        if form.is_valid():
            story = form.save(commit=False)
            story.producer = producer
            story.save()
            messages.success(request, f'Farm story "{story.title}" published.')
            return redirect('products:producer_profile', producer_id=producer.pk)
    else:
        form = FarmStoryForm()
    return render(request, 'products/content_form.html', {
        'form': form,
        'title': 'Add Farm Story',
        'submit_label': 'Publish Story',
    })


def producer_profile(request, producer_id):
    from accounts.models import ProducerProfile

    producer = get_object_or_404(ProducerProfile, pk=producer_id)
    products = _available_products().filter(producer=producer)
    recipes = Recipe.objects.filter(producer=producer, is_published=True)
    stories = FarmStory.objects.filter(producer=producer, is_published=True)
    return render(request, 'products/producer_profile.html', {
        'producer': producer,
        'products': products,
        'recipes': recipes,
        'stories': stories,
    })


@customer_required
def write_review(request, order_item_id):
    from orders.models import OrderItem

    order_item = get_object_or_404(
        OrderItem.objects.select_related('order', 'product'),
        pk=order_item_id,
        order__customer=request.user,
    )
    if order_item.order.status != 'delivered':
        messages.error(request, 'You can review products only after the order has been delivered.')
        return redirect('cart:order_detail', order_id=order_item.order_id)
    if ProductReview.objects.filter(customer=request.user, product=order_item.product).exists():
        messages.error(request, 'You have already reviewed this product.')
        return redirect('products:product_detail', pk=order_item.product_id)

    if request.method == 'POST':
        form = ProductReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.customer = request.user
            review.product = order_item.product
            review.order_item = order_item
            review.verified_purchase = True
            review.save()
            messages.success(request, 'Thanks, your review has been published.')
            return redirect('products:product_detail', pk=order_item.product_id)
    else:
        form = ProductReviewForm()

    return render(request, 'products/review_form.html', {
        'form': form,
        'order_item': order_item,
    })
