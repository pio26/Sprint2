import csv
from decimal import Decimal, ROUND_HALF_UP

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.db.models import ExpressionWrapper, F, DecimalField, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import producer_required
from accounts.models import Notification

from .models import Order, OrderItem, OrderStatusHistory, ProducerOrder


@producer_required
def incoming_orders(request):
    producer = request.user.producer_profile
    qs = Order.objects.filter(
        items__producer=producer
    ).distinct().select_related('customer').prefetch_related('items__product')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    qs = qs.order_by('delivery_date', 'created_at')
    for order in qs:
        order.producer_item_count = order.items.filter(producer=producer).count()

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
        .filter(items__producer=producer, status='delivered')
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
def payment_settlements_csv(request):
    producer = request.user.producer_profile
    orders = (
        Order.objects
        .filter(items__producer=producer, status='delivered')
        .distinct()
        .select_related('payment', 'customer')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="producer-settlements.csv"'
    writer = csv.writer(response)
    writer.writerow(['Order', 'Date', 'Customer', 'Subtotal', 'Commission', 'Net payout', 'Payment status'])
    for order in orders:
        producer_items = [i for i in order.items.all() if i.producer_id == producer.pk]
        subtotal = sum((i.line_total for i in producer_items), Decimal('0.00'))
        commission = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        net = subtotal - commission
        try:
            pay_status = order.payment.status
        except Order.payment.RelatedObjectDoesNotExist:
            pay_status = 'pending'
        writer.writerow([order.order_number, order.created_at.date(), order.customer.email, subtotal, commission, net, pay_status])
    return response


@producer_required
def order_detail_producer(request, order_id):
    producer = request.user.producer_profile
    order = get_object_or_404(
        Order,
        pk=order_id,
        items__producer=producer,
    )
    producer_order, _ = ProducerOrder.objects.get_or_create(
        order=order,
        producer=producer,
        defaults={
            'delivery_date': order.delivery_date,
            'status': order.status,
            'special_instructions': order.special_instructions,
        },
    )
    producer_items = order.items.filter(producer=producer).select_related('product')
    subtotal = sum(item.line_total for item in producer_items)
    status_labels = dict(Order.STATUS_CHOICES)
    valid_transitions = [
        (s, status_labels[s]) for s in status_labels
        if producer_order.can_transition_to(s)
    ]
    return render(request, 'orders/order_detail.html', {
        'order': order,
        'producer_order': producer_order,
        'producer_items': producer_items,
        'subtotal': subtotal,
        'valid_transitions': valid_transitions,
        'status_history': producer_order.status_history.select_related('changed_by'),
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
    producer_order, _ = ProducerOrder.objects.get_or_create(
        order=order,
        producer=producer,
        defaults={
            'delivery_date': order.delivery_date,
            'status': order.status,
            'special_instructions': order.special_instructions,
        },
    )

    new_status = request.POST.get('status', '')
    note = request.POST.get('note', '')
    if producer_order.can_transition_to(new_status):
        old_status = producer_order.status
        producer_order.status = new_status
        producer_order.save(update_fields=['status', 'updated_at'])
        order.status = new_status
        order.save(update_fields=['status', 'updated_at'])
        OrderStatusHistory.objects.create(
            order=order,
            producer_order=producer_order,
            changed_by=request.user,
            from_status=old_status,
            to_status=new_status,
            note=note,
        )
        Notification.objects.create(
            user=order.customer,
            title='Order status updated',
            message=(
                f'{producer.business_name} updated order {order.order_number} '
                f'to {dict(Order.STATUS_CHOICES)[new_status]}.'
            ),
            category='order',
            related_order=order,
        )
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


@login_required
def notifications(request):
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        return redirect('orders:notifications')
    notices = request.user.notifications.all()
    return render(request, 'orders/notifications.html', {'notifications': notices})


@staff_member_required
def commission_report(request):
    orders = _commission_orders(request)
    rows, totals = _commission_rows(orders)
    return render(request, 'orders/commission_report.html', {
        'rows': rows,
        'totals': totals,
        'filters': {
            'start': request.GET.get('start', ''),
            'end': request.GET.get('end', ''),
            'producer': request.GET.get('producer', ''),
            'status': request.GET.get('status', ''),
        },
    })


@staff_member_required
def commission_report_csv(request):
    orders = _commission_orders(request)
    rows, totals = _commission_rows(orders)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="commission-report.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Order',
        'Date',
        'Producer',
        'Order total',
        'Producer subtotal',
        'Commission',
        'Producer payment',
        'Payment status',
    ])
    for row in rows:
        writer.writerow([
            row['order'].order_number,
            row['order'].created_at.date().isoformat(),
            row['producer'],
            row['order_total'],
            row['subtotal'],
            row['commission'],
            row['producer_payment'],
            row['payment_status'],
        ])
    writer.writerow([])
    writer.writerow([
        'Totals',
        '',
        '',
        totals['order_total'],
        totals['subtotal'],
        totals['commission'],
        totals['producer_payment'],
        '',
    ])
    return response


def _commission_orders(request):
    orders = Order.objects.all().select_related('payment').prefetch_related('items__producer')
    start = request.GET.get('start')
    end = request.GET.get('end')
    producer = request.GET.get('producer', '').strip()
    status = request.GET.get('status', '').strip()
    if start:
        orders = orders.filter(created_at__date__gte=start)
    if end:
        orders = orders.filter(created_at__date__lte=end)
    if producer:
        orders = orders.filter(items__producer__business_name__icontains=producer).distinct()
    if status:
        orders = orders.filter(status=status)
    return orders.order_by('-created_at')


def _commission_rows(orders):
    rows = []
    totals = {
        'order_total': Decimal('0.00'),
        'subtotal': Decimal('0.00'),
        'commission': Decimal('0.00'),
        'producer_payment': Decimal('0.00'),
        'orders': 0,
    }
    seen_orders = set()
    for order in orders:
        if order.pk not in seen_orders:
            totals['orders'] += 1
            totals['order_total'] += order.total
            seen_orders.add(order.pk)
        producers = {}
        for item in order.items.all():
            if item.producer_id is None:
                continue
            producers.setdefault(item.producer, Decimal('0.00'))
            producers[item.producer] += item.line_total
        for producer, subtotal in producers.items():
            commission = (subtotal * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            producer_payment = subtotal - commission
            try:
                payment_status = order.payment.status
            except Order.payment.RelatedObjectDoesNotExist:
                payment_status = 'pending'
            rows.append({
                'order': order,
                'producer': producer.business_name,
                'order_total': order.total,
                'subtotal': subtotal,
                'commission': commission,
                'producer_payment': producer_payment,
                'payment_status': payment_status,
            })
            totals['subtotal'] += subtotal
            totals['commission'] += commission
            totals['producer_payment'] += producer_payment
    return rows, totals
