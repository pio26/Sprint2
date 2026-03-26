from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.db.models import ExpressionWrapper, F, DecimalField, Sum
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import producer_required

from .models import Order, OrderItem


@producer_required
def incoming_orders(request):
    producer = request.user.producer_profile
    qs = Order.objects.filter(
        items__producer=producer
    ).distinct().select_related('customer').prefetch_related('items__product')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    return render(request, 'orders/incoming_orders.html', {
        'orders': qs,
        'status_choices': Order.STATUS_CHOICES,
        'current_status': status_filter,
    })


@producer_required
def producer_dashboard(request):
    producer = request.user.producer_profile
    orders_qs = Order.objects.filter(items__producer=producer).distinct()

    stats = {
        'pending':   orders_qs.filter(status='pending').count(),
        'confirmed': orders_qs.filter(status='confirmed').count(),
        'ready':     orders_qs.filter(status='ready').count(),
        'delivered': orders_qs.filter(status='delivered').count(),
        'total':     orders_qs.count(),
    }

    revenue = (
        OrderItem.objects
        .filter(producer=producer, order__status='delivered')
        .annotate(
            line=ExpressionWrapper(
                F('price_at_time') * F('quantity'),
                output_field=DecimalField(max_digits=10, decimal_places=2),
            )
        )
        .aggregate(total=Sum('line'))['total']
    ) or Decimal('0.00')

    revenue = revenue.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    commission = (revenue * Decimal('0.05')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_UP
    )

    recent_orders = orders_qs.select_related('customer').order_by('-created_at')[:10]

    return render(request, 'orders/producer_dashboard.html', {
        'stats': stats,
        'revenue': revenue,
        'commission': commission,
        'net_payout': revenue - commission,
        'recent_orders': recent_orders,
    })


@producer_required
def payment_settlements(request):
    producer = request.user.producer_profile
    orders = (
        Order.objects
        .filter(items__producer=producer)
        .distinct()
        .select_related('payment', 'customer')
        .prefetch_related('items')
        .order_by('-created_at')
    )

    settlements = []
    total_subtotal = Decimal('0.00')
    total_commission = Decimal('0.00')
    total_net = Decimal('0.00')

    for order in orders:
        producer_items = [i for i in order.items.all() if i.producer_id == producer.pk]
        subtotal = sum((i.line_total for i in producer_items), Decimal('0.00'))
        commission = (subtotal * Decimal('0.05')).quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
        net = subtotal - commission
        try:
            pay_status = order.payment.status
        except Order.payment.RelatedObjectDoesNotExist:
            pay_status = 'pending'

        settlements.append({
            'order': order,
            'subtotal': subtotal,
            'commission': commission,
            'net': net,
            'payment_status': pay_status,
        })
        total_subtotal += subtotal
        total_commission += commission
        total_net += net

    return render(request, 'orders/payment_settlements.html', {
        'settlements': settlements,
        'total_subtotal': total_subtotal,
        'total_commission': total_commission,
        'total_net': total_net,
    })


@producer_required
def order_detail_producer(request, order_id):
    producer = request.user.producer_profile
    order = get_object_or_404(
        Order,
        pk=order_id,
        items__producer=producer,
    )
    producer_items = order.items.filter(producer=producer).select_related('product')
    subtotal = sum(item.line_total for item in producer_items)
    status_labels = dict(Order.STATUS_CHOICES)
    valid_transitions = [
        (s, status_labels[s]) for s in status_labels
        if order.can_transition_to(s)
    ]
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'producer_items': producer_items,
        'subtotal': subtotal,
        'valid_transitions': valid_transitions,
    })


@producer_required
def update_order_status(request, order_id):
    if request.method != 'POST':
        return redirect('orders:incoming_orders')

    producer = request.user.producer_profile
    order = get_object_or_404(
        Order,
        pk=order_id,
        items__producer=producer,
    )

    new_status = request.POST.get('status', '')
    if order.can_transition_to(new_status):
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        messages.success(
            request,
            f'Order {order.order_number} updated to '
            f'"{dict(Order.STATUS_CHOICES)[new_status]}".'
        )
    else:
        messages.error(
            request,
            f'Cannot change order from "{order.get_status_display()}" to '
            f'"{dict(Order.STATUS_CHOICES).get(new_status, new_status)}".'
        )

    return redirect('orders:order_detail', order_id=order.pk)
