from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import customer_required
from accounts.models import Notification
from orders.models import Order, OrderItem, Payment, ProducerOrder, RecurringOrder, RecurringOrderItem
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
        'total_food_miles': cart.get_total_food_miles(),
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

                producer_orders = {}
                for item in cart_items:
                    producer = item.product.producer
                    if producer.pk not in producer_orders:
                        producer_orders[producer.pk] = ProducerOrder.objects.create(
                            order=order,
                            producer=producer,
                            delivery_date=form.cleaned_data['delivery_date'],
                            special_instructions=form.cleaned_data.get('special_instructions', ''),
                            status='pending',
                        )

                for item in cart_items:
                    producer_order = producer_orders[item.product.producer_id]
                    OrderItem.objects.create(
                        order=order,
                        producer_order=producer_order,
                        product=item.product,
                        producer=item.product.producer,
                        product_name=item.product.name,
                        price_at_time=item.product.effective_price,
                        quantity=item.quantity,
                    )
                    item.product.stock_quantity -= item.quantity
                    item.product.save(update_fields=['stock_quantity', 'updated_at'])
                    if item.product.is_low_stock:
                        if not Notification.objects.filter(
                            user=item.product.producer.user,
                            related_product=item.product,
                            category='stock',
                            is_read=False,
                        ).exists():
                            Notification.objects.create(
                                user=item.product.producer.user,
                                related_product=item.product,
                                category='stock',
                                title='Low stock alert',
                                message=(
                                    f'Low Stock Alert: {item.product.name} - '
                                    f'Only {item.product.stock_quantity} {item.product.unit} remaining.'
                                ),
                            )

                Payment.objects.create(
                    order=order,
                    amount=order.total,
                    commission=order.commission_amount,
                    producer_amount=order.producer_payment,
                    payment_method=form.cleaned_data['payment_method'],
                    transaction_id=form.cleaned_data.get('test_payment_reference', ''),
                    status='completed' if form.cleaned_data['payment_method'] == 'mock_card' else 'pending',
                )

                if request.user.role == 'restaurant' and form.cleaned_data.get('make_recurring'):
                    recurring = RecurringOrder.objects.create(
                        customer=request.user,
                        name=f'Weekly order based on {order.order_number}',
                        frequency=form.cleaned_data.get('recurrence_frequency') or 'weekly',
                        delivery_weekday=form.cleaned_data.get('recurring_delivery_weekday') or 2,
                        next_delivery_date=form.cleaned_data['delivery_date'],
                        special_instructions=form.cleaned_data.get('special_instructions', ''),
                    )
                    for item in cart_items:
                        RecurringOrderItem.objects.create(
                            recurring_order=recurring,
                            product=item.product,
                            producer=item.product.producer,
                            quantity=item.quantity,
                        )

                for producer_order in producer_orders.values():
                    Notification.objects.create(
                        user=producer_order.producer.user,
                        title='New order received',
                        message=(
                            f'Order {order.order_number} includes items from your business '
                            f'for delivery on {producer_order.delivery_date}.'
                        ),
                        category='order',
                        related_order=order,
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
        'grouped': cart.get_items_by_producer(),
        'total_food_miles': cart.get_total_food_miles(),
    })


@customer_required
def order_confirmation(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    return render(request, 'cart/order_confirmation.html', {'order': order})


@customer_required
def order_history(request):
    orders = Order.objects.filter(customer=request.user).prefetch_related('items__producer')
    start = request.GET.get('start')
    end = request.GET.get('end')
    producer = request.GET.get('producer', '').strip()
    if start:
        orders = orders.filter(created_at__date__gte=start)
    if end:
        orders = orders.filter(created_at__date__lte=end)
    if producer:
        orders = orders.filter(items__producer__business_name__icontains=producer).distinct()
    paginator = Paginator(orders, 10)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'cart/order_history.html', {
        'page_obj': page,
        'filters': {'start': start or '', 'end': end or '', 'producer': producer},
    })


@customer_required
def order_detail_customer(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items__product__reviews', 'producer_orders__producer'),
        pk=order_id,
        customer=request.user,
    )
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


@customer_required
def order_receipt(request, order_id):
    order = get_object_or_404(Order, pk=order_id, customer=request.user)
    lines = [
        'Bristol Regional Food Network Receipt',
        f'Order: {order.order_number}',
        f'Date: {order.created_at:%d %b %Y}',
        f'Status: {order.get_status_display()}',
        '',
        'Items:',
    ]
    for item in order.items.select_related('producer').all():
        producer = item.producer.business_name if item.producer else 'Unknown producer'
        lines.append(f'- {item.product_name} ({producer}) x{item.quantity}: £{item.line_total}')
    lines.extend([
        '',
        f'Subtotal: £{order.total}',
        f'Network commission included: £{order.commission_amount}',
        f'Producer payment total: £{order.producer_payment}',
    ])
    return HttpResponse('\n'.join(lines), content_type='text/plain')


@customer_required
def recurring_orders(request):
    templates = RecurringOrder.objects.filter(customer=request.user).prefetch_related('items__product')
    return render(request, 'cart/recurring_orders.html', {'templates': templates})


@customer_required
def recurring_order_detail(request, recurring_id):
    template = get_object_or_404(
        RecurringOrder.objects.prefetch_related('items__product'),
        pk=recurring_id,
        customer=request.user,
    )
    if request.method == 'POST':
        template.is_active = request.POST.get('is_active') == 'on'
        template.special_instructions = request.POST.get('special_instructions', '')
        template.save(update_fields=['is_active', 'special_instructions', 'updated_at'])
        for item in template.items.all():
            value = request.POST.get(f'quantity_{item.pk}')
            if value:
                try:
                    item.quantity = max(1, int(value))
                    item.save(update_fields=['quantity'])
                except ValueError:
                    pass
        messages.success(request, 'Recurring order updated.')
        return redirect('cart:recurring_order_detail', recurring_id=template.pk)
    return render(request, 'cart/recurring_order_detail.html', {'template': template})
