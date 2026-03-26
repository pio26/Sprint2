"""
Management command: seed_data
Creates demo data for local development and testing.

Usage:
    python manage.py seed_data            # create data (idempotent)
    python manage.py seed_data --reset    # wipe and recreate everything
"""
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.core.files import File
from django.utils import timezone

import os
from pathlib import Path

from accounts.models import CustomerProfile, ProducerProfile
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem, Payment
from products.models import Category, Product

User = get_user_model()


# ── Colour helpers for terminal output ──────────────────────────────────────
GREEN = '\033[92m'
CYAN  = '\033[96m'
YELLOW = '\033[93m'
RESET = '\033[0m'

def ok(msg):   print(f'  {GREEN}[+]{RESET} {msg}')
def info(msg): print(f'  {CYAN}[>]{RESET} {msg}')
def skip(msg): print(f'  {YELLOW}[~]{RESET} {msg} (already exists)')


class Command(BaseCommand):
    help = 'Seed the database with demo producers, customers, products, and orders.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Delete ALL existing data before seeding.',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('\nResetting database…'))
            Payment.objects.all().delete()
            OrderItem.objects.all().delete()
            Order.objects.all().delete()
            CartItem.objects.all().delete()
            Cart.objects.all().delete()
            Product.objects.all().delete()
            Category.objects.all().delete()
            ProducerProfile.objects.all().delete()
            CustomerProfile.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.WARNING('  Database cleared.\n'))

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Producers ==='))
        producers = self._seed_producers()

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Customers ==='))
        customers = self._seed_customers()

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Categories ==='))
        categories = self._seed_categories()

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Products ==='))
        products = self._seed_products(producers, categories)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Sample Orders ==='))
        self._seed_orders(customers, producers, products)

        self.stdout.write(self.style.SUCCESS('\nSeed complete!\n'))
        self._print_credentials(producers, customers)

    # ── Producers ────────────────────────────────────────────────────────────

    def _seed_producers(self):
        data = [
            dict(
                email='bob@hillsidefarm.test', password='Testpass99!',
                first_name='Bob', last_name='Jones',
                business_name='Hillside Farm',
                business_address='Hillside Lane, Nailsea', postcode='BS48 1AA',
                description='Family-run market garden growing seasonal vegetables since 1987.',
            ),
            dict(
                email='sarah@greenorchard.test', password='Testpass99!',
                first_name='Sarah', last_name='Green',
                business_name='Green Orchard',
                business_address='Orchard Road, Clevedon', postcode='BS21 6BB',
                description='Heritage variety apples, pears and soft fruit from our 12-acre orchard.',
            ),
            dict(
                email='mike@brownsdairy.test', password='Testpass99!',
                first_name='Mike', last_name='Brown',
                business_name="Brown's Dairy",
                business_address='Dairy Farm, Long Ashton', postcode='BS41 9CC',
                description='Award-winning artisan dairy — milk, cream, cheese and eggs.',
            ),
        ]
        profiles = {}
        for d in data:
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults=dict(
                    first_name=d['first_name'], last_name=d['last_name'],
                    role='producer',
                ),
            )
            if created:
                user.set_password(d['password'])
                user.save()
                ok(f"Producer created: {d['email']}")
            else:
                skip(d['email'])

            profile, _ = ProducerProfile.objects.get_or_create(
                user=user,
                defaults=dict(
                    business_name=d['business_name'],
                    business_address=d['business_address'],
                    postcode=d['postcode'],
                    description=d['description'],
                ),
            )
            profiles[d['business_name']] = (user, profile)
        return profiles

    # ── Customers ────────────────────────────────────────────────────────────

    def _seed_customers(self):
        data = [
            dict(
                email='alice@customer.test', password='Testpass99!',
                first_name='Alice', last_name='Smith',
                delivery_address='14 Redcliffe Street\nBristol', postcode='BS1 6NP',
            ),
            dict(
                email='charlie@customer.test', password='Testpass99!',
                first_name='Charlie', last_name='Davis',
                delivery_address='7 Cotham Hill\nBristol', postcode='BS6 6LF',
            ),
        ]
        users = {}
        for d in data:
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults=dict(
                    first_name=d['first_name'], last_name=d['last_name'],
                    role='customer',
                ),
            )
            if created:
                user.set_password(d['password'])
                user.save()
                ok(f"Customer created: {d['email']}")
            else:
                skip(d['email'])

            CustomerProfile.objects.get_or_create(
                user=user,
                defaults=dict(
                    delivery_address=d['delivery_address'],
                    postcode=d['postcode'],
                ),
            )
            users[d['first_name']] = user
        return users

    # ── Categories ───────────────────────────────────────────────────────────

    def _seed_categories(self):
        data = [
            ('Vegetables',    'vegetables'),
            ('Fruit',         'fruit'),
            ('Dairy & Eggs',  'dairy-eggs'),
            ('Bread & Bakery','bread-bakery'),
            ('Meat & Poultry','meat-poultry'),
            ('Honey & Jams',  'honey-jams'),
        ]
        cats = {}
        for name, slug in data:
            cat, created = Category.objects.get_or_create(slug=slug, defaults={'name': name})
            if created:
                ok(f"Category: {name}")
            else:
                skip(name)
            cats[slug] = cat
        return cats

    # ── Products ─────────────────────────────────────────────────────────────

    def _seed_products(self, producers, categories):
        _, bob   = producers['Hillside Farm']
        _, sarah = producers['Green Orchard']
        _, mike  = producers["Brown's Dairy"]

        veg   = categories['vegetables']
        fruit = categories['fruit']
        dairy = categories['dairy-eggs']
        bread = categories['bread-bakery']

        today = date.today()

        # Map product names to pre-made SVG images in media/products/
        image_map = {
            'Heritage Tomatoes': 'heritage-tomatoes.svg',
            'Courgettes':        'courgettes.svg',
            'New Potatoes':      'new-potatoes.svg',
            'Mixed Salad Leaves':'mixed-salad-leaves.svg',
            'Cox Apples':        'cox-apples.svg',
            'Strawberries':      'strawberries.svg',
            'Conference Pears':  'conference-pears.svg',
            'Whole Milk':        'whole-milk.svg',
            'Free-Range Eggs':   'free-range-eggs.svg',
            'Mature Cheddar':    'mature-cheddar.svg',
        }

        raw = [
            # ── Bob – Hillside Farm ──────────────────────────────────────────
            dict(
                producer=bob, category=veg, name='Heritage Tomatoes',
                description='Vine-ripened heritage tomatoes, mixed colours. Grown in our polytunnels.',
                price=Decimal('3.50'), unit='500g punnet', stock_quantity=40,
                availability_status='in_season',
                season_start=date(today.year, 6, 1), season_end=date(today.year, 10, 31),
                allergens=[], is_organic=True,
            ),
            dict(
                producer=bob, category=veg, name='Courgettes',
                description='Fresh green courgettes, hand-picked daily. Perfect for roasting or grilling.',
                price=Decimal('1.80'), unit='each (approx 200g)', stock_quantity=60,
                availability_status='year_round',
                allergens=[], is_organic=False,
            ),
            dict(
                producer=bob, category=veg, name='New Potatoes',
                description='Freshly dug Jersey Royal-style new potatoes, earthy and sweet.',
                price=Decimal('2.20'), unit='1kg bag', stock_quantity=80,
                availability_status='year_round',
                allergens=[], is_organic=False,
            ),
            dict(
                producer=bob, category=veg, name='Mixed Salad Leaves',
                description='Baby salad leaves mix — rocket, spinach, watercress, cut fresh each morning.',
                price=Decimal('2.00'), unit='100g bag', stock_quantity=30,
                availability_status='year_round',
                allergens=[], is_organic=True,
            ),
            # ── Sarah – Green Orchard ────────────────────────────────────────
            dict(
                producer=sarah, category=fruit, name='Cox Apples',
                description="Classic Cox's Orange Pippin, crisp and sweet. Grown without pesticides.",
                price=Decimal('2.50'), unit='4-pack', stock_quantity=50,
                availability_status='in_season',
                season_start=date(today.year, 9, 1), season_end=date(today.year, 12, 31),
                allergens=[], is_organic=True,
            ),
            dict(
                producer=sarah, category=fruit, name='Strawberries',
                description='Sun-ripened strawberries, picked same-day for maximum freshness.',
                price=Decimal('3.00'), unit='400g punnet', stock_quantity=25,
                availability_status='in_season',
                season_start=date(today.year, 5, 1), season_end=date(today.year, 8, 31),
                allergens=[], is_organic=False,
            ),
            dict(
                producer=sarah, category=fruit, name='Conference Pears',
                description='Buttery, juicy Conference pears from our heritage orchard.',
                price=Decimal('2.80'), unit='3-pack', stock_quantity=35,
                availability_status='year_round',
                allergens=[], is_organic=False,
            ),
            # ── Mike – Brown's Dairy ─────────────────────────────────────────
            dict(
                producer=mike, category=dairy, name='Whole Milk',
                description='Full-fat whole milk from our Guernsey herd. Non-homogenised.',
                price=Decimal('1.20'), unit='1 litre', stock_quantity=100,
                availability_status='year_round',
                allergens=['Milk'], is_organic=False,
            ),
            dict(
                producer=mike, category=dairy, name='Free-Range Eggs',
                description='Large free-range eggs from hens with daily outdoor access.',
                price=Decimal('2.80'), unit='6 eggs', stock_quantity=70,
                availability_status='year_round',
                allergens=['Eggs'], is_organic=False,
            ),
            dict(
                producer=mike, category=dairy, name='Mature Cheddar',
                description='18-month aged cheddar, sharp and crumbly. Award-winning recipe.',
                price=Decimal('4.50'), unit='200g block', stock_quantity=45,
                availability_status='year_round',
                allergens=['Milk'], is_organic=False,
            ),
        ]

        media_root = Path(__file__).resolve().parents[3] / 'media' / 'products'

        products = {}
        for kwargs in raw:
            p, created = Product.objects.get_or_create(
                producer=kwargs['producer'],
                name=kwargs['name'],
                defaults={k: v for k, v in kwargs.items() if k not in ('producer', 'name')},
            )
            if created:
                ok(f"Product: {p.name} ({p.producer.business_name})")
            else:
                skip(p.name)

            # Assign image if not already set
            if not p.image:
                filename = image_map.get(p.name)
                if filename:
                    img_path = media_root / filename
                    if img_path.exists():
                        with open(img_path, 'rb') as f:
                            p.image.save(filename, File(f), save=True)
                        ok(f"  Image assigned: {p.name}")

            products[p.name] = p
        return products

    # ── Orders ───────────────────────────────────────────────────────────────

    def _seed_orders(self, customers, producers, products):
        alice   = customers['Alice']
        charlie = customers['Charlie']
        _, bob  = producers['Hillside Farm']
        _, mike = producers["Brown's Dairy"]

        today = date.today()

        # Order 1 — Alice, pending, delivery in 4 days
        o1 = self._make_order(
            customer=alice,
            delivery_address='14 Redcliffe Street\nBristol',
            delivery_date=today + timedelta(days=4),
            status='pending',
            items=[
                (products['Heritage Tomatoes'], bob, 2),
                (products['Whole Milk'],         mike, 3),
            ],
            label='Alice / Pending',
        )

        # Order 2 — Charlie, confirmed, delivery in 3 days
        o2 = self._make_order(
            customer=charlie,
            delivery_address='7 Cotham Hill\nBristol',
            delivery_date=today + timedelta(days=3),
            status='confirmed',
            items=[
                (products['Cox Apples'],    producers['Green Orchard'][1], 1),
                (products['Free-Range Eggs'], mike, 2),
            ],
            label='Charlie / Confirmed',
        )

        # Order 3 — Alice, delivered (with payment completed)
        o3 = self._make_order(
            customer=alice,
            delivery_address='14 Redcliffe Street\nBristol',
            delivery_date=today - timedelta(days=2),
            status='delivered',
            items=[
                (products['New Potatoes'],   bob,  3),
                (products['Mature Cheddar'], mike, 1),
            ],
            label='Alice / Delivered',
            payment_completed=True,
        )

    def _make_order(self, customer, delivery_address, delivery_date,
                    status, items, label, payment_completed=False):
        # Skip if customer already has an order with the same delivery date
        if Order.objects.filter(customer=customer, delivery_date=delivery_date).exists():
            skip(f'Order ({label})')
            return

        order = Order.objects.create(
            customer=customer,
            delivery_address=delivery_address,
            delivery_date=delivery_date,
            status=status,
        )

        total = Decimal('0.00')
        for product, producer_profile, qty in items:
            price = Decimal(str(product.price))
            OrderItem.objects.create(
                order=order,
                product=product,
                producer=producer_profile,
                product_name=product.name,
                price_at_time=price,
                quantity=qty,
            )
            total += price * qty

        commission = (total * Decimal('0.05')).quantize(Decimal('0.01'))
        Payment.objects.create(
            order=order,
            amount=total,
            commission=commission,
            producer_amount=total - commission,
            status='completed' if payment_completed else 'pending',
        )

        ok(f'Order {order.order_number} ({label})')
        return order

    # ── Credentials summary ──────────────────────────────────────────────────

    def _print_credentials(self, producers, customers):
        self.stdout.write(self.style.HTTP_INFO('-' * 50))
        self.stdout.write(self.style.HTTP_INFO('Demo Credentials (password: Testpass99!)'))
        self.stdout.write(self.style.HTTP_INFO('-' * 50))
        self.stdout.write('\nProducers:')
        for name, (user, _) in producers.items():
            print(f'  {user.email}  ({name})')
        self.stdout.write('\nCustomers:')
        for name, user in customers.items():
            print(f'  {user.email}  ({name})')
        self.stdout.write('')
