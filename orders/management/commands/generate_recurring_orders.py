from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Notification
from cart.payments import process_payment
from orders.models import Order, OrderItem, Payment, ProducerOrder, RecurringOrder, RecurringOrderItem


class Command(BaseCommand):
    help = 'Generate orders from active recurring order templates whose next_delivery_date is today or overdue.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Preview which templates would fire without creating orders.',
        )

    def handle(self, *args, **options):
        today = timezone.now().date()
        dry_run = options['dry_run']
        templates = RecurringOrder.objects.filter(
            is_active=True,
            next_delivery_date__lte=today,
        ).select_related('customer').prefetch_related('items__product__producer')

        if not templates.exists():
            self.stdout.write('No recurring orders due today.')
            return

        created = 0
        skipped = 0
        for template in templates:
            if dry_run:
                self.stdout.write(f'[dry-run] Would generate order for {template.customer.email} ({template.name})')
                continue
            try:
                order = self._create_order(template, today)
                self._advance_next_date(template)
                self.stdout.write(self.style.SUCCESS(
                    f'Created {order.order_number} for {template.customer.email}'
                ))
                created += 1
            except Exception as exc:
                self.stderr.write(f'Failed for template {template.pk} ({template.customer.email}): {exc}')
                skipped += 1

        if not dry_run:
            self.stdout.write(f'Done — {created} order(s) created, {skipped} skipped.')

    def _create_order(self, template, today):
        delivery_date = template.next_delivery_date
        # Delivery must be at least 48 h away; push forward if needed
        min_delivery = (timezone.now() + timedelta(hours=48)).date()
        if delivery_date < min_delivery:
            delivery_date = min_delivery

        with transaction.atomic():
            order = Order.objects.create(
                customer=template.customer,
                delivery_address=template.customer.customer_profile.delivery_address,
                delivery_date=delivery_date,
                special_instructions=template.special_instructions,
                status='pending',
            )

            producer_orders = {}
            valid_items = []
            for item in template.items.all():
                product = item.product
                if not product.is_available or product.stock_quantity < item.quantity:
                    Notification.objects.create(
                        user=template.customer,
                        title='Recurring order item unavailable',
                        message=(
                            f'"{product.name}" could not be included in your recurring order '
                            f'({template.name}) because it is out of stock or unavailable.'
                        ),
                        category='order',
                    )
                    continue

                producer = product.producer
                if producer.pk not in producer_orders:
                    producer_orders[producer.pk] = ProducerOrder.objects.create(
                        order=order,
                        producer=producer,
                        delivery_date=delivery_date,
                        special_instructions=template.special_instructions,
                        status='pending',
                    )
                OrderItem.objects.create(
                    order=order,
                    producer_order=producer_orders[producer.pk],
                    product=product,
                    producer=producer,
                    product_name=product.name,
                    price_at_time=product.effective_price,
                    quantity=item.quantity,
                )
                product.stock_quantity -= item.quantity
                product.save(update_fields=['stock_quantity', 'updated_at'])
                valid_items.append(item)

            if not valid_items:
                order.delete()
                raise ValueError('All items in this recurring template are unavailable.')

            transaction_id, payment_status = process_payment(
                order.total,
                f'RECUR-{template.pk}',
                'mock_card',
            )
            Payment.objects.create(
                order=order,
                amount=order.total,
                commission=order.commission_amount,
                producer_amount=order.producer_payment,
                payment_method='mock_card',
                transaction_id=transaction_id,
                status=payment_status,
            )

            for po in producer_orders.values():
                Notification.objects.create(
                    user=po.producer.user,
                    title='New recurring order received',
                    message=(
                        f'Recurring order {order.order_number} from {template.customer.email} '
                        f'for delivery on {delivery_date}.'
                    ),
                    category='order',
                    related_order=order,
                )

            Notification.objects.create(
                user=template.customer,
                title='Recurring order placed',
                message=f'Your recurring order "{template.name}" has been placed as {order.order_number}.',
                category='order',
                related_order=order,
            )

        return order

    def _advance_next_date(self, template):
        if template.frequency == 'weekly':
            template.next_delivery_date += timedelta(weeks=1)
        else:
            template.next_delivery_date += timedelta(weeks=2)
        template.save(update_fields=['next_delivery_date', 'updated_at'])
