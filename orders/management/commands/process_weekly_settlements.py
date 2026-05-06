from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from orders.models import Order, Payment


class Command(BaseCommand):
    help = (
        'Process weekly payment settlements: mark completed delivered orders as '
        'settled and print a summary. Run every Monday via Docker cron.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print summary without updating payment statuses.',
        )
        parser.add_argument(
            '--week-offset',
            type=int,
            default=0,
            help='Process N weeks ago instead of the current week (0 = this week).',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        offset = options['week_offset']

        today = timezone.now().date()
        # ISO week: Monday = start, Sunday = end
        week_start = today - timedelta(days=today.weekday()) - timedelta(weeks=offset)
        week_end = week_start + timedelta(days=6)

        self.stdout.write(
            f'Settlement period: {week_start} to {week_end}'
            + (' [DRY RUN]' if dry_run else '')
        )

        # Delivered orders with pending payment in the settlement window
        orders = Order.objects.filter(
            status='delivered',
            delivery_date__range=(week_start, week_end),
            payment__status='pending',
        ).select_related('payment', 'customer')

        if not orders.exists():
            self.stdout.write('No pending settlements found for this period.')
            return

        total_orders = orders.count()
        total_value = orders.aggregate(s=Sum('payment__amount'))['s'] or 0
        total_commission = orders.aggregate(s=Sum('payment__commission'))['s'] or 0
        total_producer = orders.aggregate(s=Sum('payment__producer_amount'))['s'] or 0

        self.stdout.write(f'Orders to settle : {total_orders}')
        self.stdout.write(f'Total order value: £{total_value:.2f}')
        self.stdout.write(f'Network commission (5%): £{total_commission:.2f}')
        self.stdout.write(f'Producer payments (95%): £{total_producer:.2f}')

        if not dry_run:
            updated = Payment.objects.filter(
                order__in=orders,
                status='pending',
            ).update(status='completed')
            self.stdout.write(
                self.style.SUCCESS(f'Settled {updated} payment(s) for week {week_start}.')
            )
        else:
            self.stdout.write('[dry-run] No records updated.')
