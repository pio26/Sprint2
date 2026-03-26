from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import customer_required
from orders.models import Order, OrderItem, Payment
from products.models import Product

from .forms import CheckoutForm
from .models import Cart, CartItem


@login_required
def cart_detail(request):
    if request.user.role != 'customer':
        return HttpResponseForbidden("Only customers have a cart.")
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    return render(request, 'cart/cart_detail.html', {
        'cart': cart,
        'grouped': cart.get_items_by_producer(),
        'total': cart.get_total(),
    })


@customer_required
def add_to_cart(request, product_id):
    if request.method != 'POST':
        return redirect('products:product_detail', pk=product_id)

    product = get_object_or_404(Product, pk=product_id)

    if not product.is_available:
        messages.error(request, f'"{product.name}" is not currently available.')
        return redirect('products:product_detail', pk=product_id)

    try:
        qty = max(1, int(request.POST.get('quantity', 1)))
    except (ValueError, TypeError):
        qty = 1

    if qty > product.stock_quantity:
        messages.error(request, f'Only {product.stock_quantity} units available.')
        return redirect('products:product_detail', pk=product_id)

    cart, _ = Cart.objects.get_or_create(customer=request.user)
    item, created = CartItem.objects.get_or_create(cart=cart, product=product)
    if not created:
        item.quantity = min(item.quantity + qty, product.stock_quantity)
    else:
        item.quantity = qty
    item.save()

    messages.success(request, f'"{product.name}" added to your cart.')
    return redirect('products:product_detail', pk=product_id)


@customer_required
def update_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart:cart_detail')

    item = get_object_or_404(CartItem, pk=item_id, cart__customer=request.user)

    try:
        qty = int(request.POST.get('quantity', 1))
    except (ValueError, TypeError):
        qty = 1

    if qty <= 0:
        item.delete()
        messages.info(request, 'Item removed from cart.')
    else:
        item.quantity = min(qty, item.product.stock_quantity)
        item.save()

    return redirect('cart:cart_detail')


@customer_required
def remove_from_cart(request, item_id):
    if request.method != 'POST':
        return redirect('cart:cart_detail')

    item = get_object_or_404(CartItem, pk=item_id, cart__customer=request.user)
    product_name = item.product.name
    item.delete()
    messages.info(request, f'"{product_name}" removed from cart.')
    return redirect('cart:cart_detail')


@customer_required
def checkout(request):
    cart, _ = Cart.objects.get_or_create(customer=request.user)
    cart_items = list(cart.items.select_related('product__producer').all())

    if not cart_items:
        messages.warning(request, 'Your cart is empty.')
        return redirect('cart:cart_detail')

    initial = {}
    try:
        initial['delivery_address'] = request.user.customer_profile.delivery_address
    except Exception:
        pass

    if request.method == 'POST':
        form = CheckoutForm(request.POST)
        if form.is_valid():
            out_of_stock = [
                item for item in cart_items
                if not item.product.is_available or item.quantity > item.product.stock_quantity
            ]
            if out_of_stock:
                names = ', '.join(i.product.name for i in out_of_stock)
                messages.error(
                    request,
                    f'The following items are no longer available: {names}. '
                    'Please update your cart.'
                )
                return redirect('cart:cart_detail')

            with transaction.atomic():
                order = Order.objects.create(
                    customer=request.user,
                    delivery_address=form.cleaned_data['delivery_address'],
                    delivery_date=form.cleaned_data['delivery_date'],
                    special_instructions=form.cleaned_data.get('special_instructions', ''),
                    status='pending',
                )

                for item in cart_items:
                    OrderItem.objects.create(
                        order=order,
                        product=item.product,
                        producer=item.product.producer,
                        product_name=item.product.name,
                        price_at_time=item.product.price,
                        quantity=item.quantity,
                    )

                Payment.objects.create(
                    order=order,
                    amount=order.total,
                    commission=order.commission_amount,
                    producer_amount=order.producer_payment,
                )

                cart.items.all().delete()

            return redirect('cart:order_confirmation', order_id=order.pk)
    else:
        form = CheckoutForm(initial=initial)

    return render(request, 'cart/checkout.html', {
        'form': form,
        'cart': cart,
        'cart_items': cart_items,
        'total': cart.get_total(),
    })


@customer_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    return render(request, 'cart/order_confirmation.html', {'order': order})


@customer_required
def order_history(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related('items')
    paginator = Paginator(orders, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'cart/order_history.html', {'page_obj': page})


@customer_required
def order_detail_customer(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    return render(request, 'cart/order_detail.html', {'order': order})


@customer_required
def reorder(request, order_id):
    if request.method != 'POST':
        return redirect('cart:order_history')

    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    cart, _ = Cart.objects.get_or_create(customer=request.user)

    added = 0
    skipped = 0
    for order_item in order.items.select_related('product').all():
        product = order_item.product
        if product is None or not product.is_available:
            skipped += 1
            continue
        qty = min(order_item.quantity, product.stock_quantity)
        cart_item, created = CartItem.objects.get_or_create(cart=cart, product=product)
        if created:
            cart_item.quantity = qty
        else:
            cart_item.quantity = min(cart_item.quantity + qty, product.stock_quantity)
        cart_item.save()
        added += 1

    if added:
        messages.success(request, f'Added {added} item(s) to your cart.')
    if skipped:
        messages.warning(request, f'{skipped} item(s) were skipped (no longer available).')

    return redirect('cart:cart_detail')
