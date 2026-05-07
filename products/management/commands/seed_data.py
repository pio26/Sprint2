"""
Management command: seed_data
Creates comprehensive demo data for local development and testing.

Usage:
    python manage.py seed_data            # create data (idempotent)
    python manage.py seed_data --reset    # wipe and recreate everything
"""
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import CustomerProfile, ProducerProfile
from cart.models import Cart, CartItem
from orders.models import (
    Order, OrderItem, Payment, ProducerOrder, OrderStatusHistory,
    RecurringOrder, RecurringOrderItem,
)
from products.models import Category, Product, Recipe, FarmStory, ProductReview

User = get_user_model()

GREEN  = '\033[92m'
CYAN   = '\033[96m'
YELLOW = '\033[93m'
RESET  = '\033[0m'


def ok(msg):   print(f'  {GREEN}[+]{RESET} {msg}')
def info(msg): print(f'  {CYAN}[>]{RESET} {msg}')
def skip(msg): print(f'  {YELLOW}[~]{RESET} {msg} (already exists)')


class Command(BaseCommand):
    help = 'Seed the database with 6 producers, 4 customers, 30 products, 12 orders, reviews, recipes, stories, surplus and recurring orders.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true',
                            help='Delete ALL existing data before seeding.')

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write(self.style.WARNING('\nResetting database…'))
            RecurringOrderItem.objects.all().delete()
            RecurringOrder.objects.all().delete()
            ProductReview.objects.all().delete()
            FarmStory.objects.all().delete()
            Recipe.objects.all().delete()
            OrderStatusHistory.objects.all().delete()
            Payment.objects.all().delete()
            OrderItem.objects.all().delete()
            ProducerOrder.objects.all().delete()
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

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Products (30) ==='))
        products = self._seed_products(producers, categories)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Farm Stories ==='))
        self._seed_farm_stories(producers)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Recipes ==='))
        self._seed_recipes(producers, products)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Orders (12) ==='))
        delivered_items = self._seed_orders(customers, producers, products)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Reviews ==='))
        self._seed_reviews(customers, products, delivered_items)

        self.stdout.write(self.style.HTTP_INFO('\n=== Seeding: Recurring Orders ==='))
        self._seed_recurring_orders(customers, producers, products)

        self.stdout.write(self.style.SUCCESS('\nSeed complete!\n'))
        self._print_credentials(producers, customers)

    # ── Producers ─────────────────────────────────────────────────────────────

    def _seed_producers(self):
        data = [
            dict(
                email='bob@hillsidefarm.test', password='Testpass99!',
                first_name='Bob', last_name='Jones',
                business_name='Hillside Farm',
                business_address='Hillside Lane, Nailsea, Bristol',
                postcode='BS7 8JN',
                description=(
                    'Family-run market garden growing seasonal vegetables since 1987. '
                    'We specialise in heritage varieties and sustainable growing without '
                    'synthetic pesticides or fertilisers.'
                ),
            ),
            dict(
                email='sarah@greenorchard.test', password='Testpass99!',
                first_name='Sarah', last_name='Green',
                business_name='Green Orchard',
                business_address='Orchard Road, Clevedon, Bristol',
                postcode='BS9 1LQ',
                description=(
                    'Heritage variety apples, pears and soft fruit from our 12-acre orchard. '
                    'Certified organic since 2009 — we press our own juice and sell direct '
                    'to Bristol families and restaurants.'
                ),
            ),
            dict(
                email='mike@brownsdairy.test', password='Testpass99!',
                first_name='Mike', last_name='Brown',
                business_name="Brown's Dairy",
                business_address='Dairy Farm, Long Ashton, Bristol',
                postcode='BS13 7AB',
                description=(
                    'Award-winning artisan dairy — milk, cream, cheese and eggs from our '
                    'Guernsey and Jersey herd. Non-homogenised, low-intervention, delivered '
                    'fresh within 24 hours of milking.'
                ),
            ),
            dict(
                email='emma@whitesbakery.test', password='Testpass99!',
                first_name='Emma', last_name='White',
                business_name="White's Artisan Bakery",
                business_address='14 Baker Street, Clifton, Bristol',
                postcode='BS6 5LA',
                description=(
                    'Slow-fermented sourdough and traditional bakes using stoneground '
                    'local flour. Baked fresh every morning — no preservatives, no shortcuts.'
                ),
            ),
            dict(
                email='tom@blacksfarm.test', password='Testpass99!',
                first_name='Tom', last_name='Black',
                business_name="Black's Farm Meats",
                business_address='Black Farm, Frenchay, Bristol',
                postcode='BS16 1PQ',
                description=(
                    'Free-range and pasture-raised pork, lamb, beef and poultry reared on '
                    'our 180-acre family farm. Slaughtered locally and hung for optimal '
                    'flavour.'
                ),
            ),
            dict(
                email='lucy@wildhoney.test', password='Testpass99!',
                first_name='Lucy', last_name='Wild',
                business_name='Wild Honey Apiaries',
                business_address='22 Meadow Lane, Brislington, Bristol',
                postcode='BS15 3RG',
                description=(
                    'Raw honey and artisan preserves from our Bristol city apiaries and '
                    'surrounding wildflower meadows. Single-origin, unfiltered, seasonally '
                    'harvested.'
                ),
            ),
        ]
        profiles = {}
        for d in data:
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults=dict(first_name=d['first_name'], last_name=d['last_name'], role='producer'),
            )
            if created:
                user.set_password(d['password'])
                user.save()
                ok(f"Producer: {d['email']}")
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

    # ── Customers ─────────────────────────────────────────────────────────────

    def _seed_customers(self):
        data = [
            dict(
                email='alice@customer.test', password='Testpass99!',
                first_name='Alice', last_name='Smith',
                role='customer', account_type='individual',
                organization_name='',
                delivery_address='14 Redcliffe Street\nBristol', postcode='BS1 6NP',
                key='Alice',
            ),
            dict(
                email='charlie@customer.test', password='Testpass99!',
                first_name='Charlie', last_name='Davis',
                role='customer', account_type='individual',
                organization_name='',
                delivery_address='7 Cotham Hill\nBristol', postcode='BS6 6LF',
                key='Charlie',
            ),
            dict(
                email='info@bristolcommunitykitchen.test', password='Testpass99!',
                first_name='Sarah', last_name='Okonkwo',
                role='community', account_type='community_group',
                organization_name='Bristol Community Kitchen',
                delivery_address='Bristol Community Centre\n5 Station Road\nBristol',
                postcode='BS5 0LE',
                key='Community Kitchen',
            ),
            dict(
                email='orders@harboursidekitchen.test', password='Testpass99!',
                first_name='Marco', last_name='Ferretti',
                role='restaurant', account_type='restaurant',
                organization_name='The Harbourside Kitchen',
                delivery_address='The Harbourside Kitchen\n12 Wapping Wharf\nBristol',
                postcode='BS2 0BH',
                key='Harbourside Kitchen',
            ),
        ]
        users = {}
        for d in data:
            key = d.pop('key')
            user, created = User.objects.get_or_create(
                email=d['email'],
                defaults=dict(first_name=d['first_name'], last_name=d['last_name'], role=d['role']),
            )
            if created:
                user.set_password(d['password'])
                user.save()
                ok(f"Customer: {d['email']} ({d['role']})")
            else:
                skip(d['email'])
            CustomerProfile.objects.get_or_create(
                user=user,
                defaults=dict(
                    account_type=d['account_type'],
                    organization_name=d['organization_name'],
                    delivery_address=d['delivery_address'],
                    postcode=d['postcode'],
                ),
            )
            users[key] = user
        return users

    # ── Categories ────────────────────────────────────────────────────────────

    def _seed_categories(self):
        data = [
            ('Vegetables',     'vegetables',   'Fresh seasonal and year-round vegetables.'),
            ('Fruit',          'fruit',        'Orchard and soft fruits.'),
            ('Dairy & Eggs',   'dairy-eggs',   'Milk, cheese, yogurt, cream and eggs.'),
            ('Bread & Bakery', 'bread-bakery', 'Sourdough, rolls, pastries and baked goods.'),
            ('Meat & Poultry', 'meat-poultry', 'Free-range and pasture-raised meat.'),
            ('Honey & Jams',   'honey-jams',   'Raw honey, jams, marmalades and preserves.'),
        ]
        cats = {}
        for name, slug, desc in data:
            cat, created = Category.objects.get_or_create(
                slug=slug, defaults={'name': name, 'description': desc},
            )
            if created:
                ok(f"Category: {name}")
            else:
                skip(name)
            cats[slug] = cat
        return cats

    # ── Products ──────────────────────────────────────────────────────────────

    def _seed_products(self, producers, categories):
        _, bob   = producers['Hillside Farm']
        _, sarah = producers['Green Orchard']
        _, mike  = producers["Brown's Dairy"]
        _, emma  = producers["White's Artisan Bakery"]
        _, tom   = producers["Black's Farm Meats"]
        _, lucy  = producers['Wild Honey Apiaries']

        veg   = categories['vegetables']
        fruit = categories['fruit']
        dairy = categories['dairy-eggs']
        bread = categories['bread-bakery']
        meat  = categories['meat-poultry']
        honey = categories['honey-jams']

        today = date.today()
        now   = timezone.now()

        raw = [
            # ── Bob – Hillside Farm (5) ───────────────────────────────────────
            dict(
                producer=bob, category=veg, name='Heritage Tomatoes',
                description='Vine-ripened heritage tomatoes in mixed colours — red, yellow, and striped. Grown in our polytunnels without synthetic pesticides.',
                price=Decimal('3.50'), unit='500g punnet', stock_quantity=40,
                availability_status='in_season',
                season_start=date(today.year, 6, 1), season_end=date(today.year, 10, 31),
                allergens=[], allergens_declared=True, is_organic=True,
            ),
            dict(
                producer=bob, category=veg, name='Courgettes',
                description='Fresh green courgettes, hand-picked daily. Perfect for roasting, grilling, or spiralising.',
                price=Decimal('1.80'), unit='each (approx 200g)', stock_quantity=60,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=bob, category=veg, name='New Potatoes',
                description='Freshly dug Jersey Royal-style new potatoes, earthy and sweet. Needs nothing but butter and mint.',
                price=Decimal('2.20'), unit='1kg bag', stock_quantity=80,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=bob, category=veg, name='Mixed Salad Leaves',
                description="Baby salad leaves — rocket, spinach, watercress, and lamb's lettuce. Cut fresh each morning.",
                price=Decimal('2.00'), unit='100g bag', stock_quantity=30,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=True,
            ),
            dict(
                producer=bob, category=veg, name='Kale & Rainbow Chard',
                description='A colourful mix of curly kale and rainbow chard stems. Nutritious, tender, and versatile.',
                price=Decimal('2.50'), unit='250g bunch', stock_quantity=45,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=True,
            ),
            # ── Sarah – Green Orchard (5) ─────────────────────────────────────
            dict(
                producer=sarah, category=fruit, name='Cox Apples',
                description="Classic Cox's Orange Pippin — crisp, aromatic, sweet-sharp. Grown without synthetic pesticides.",
                price=Decimal('2.50'), unit='4-pack', stock_quantity=50,
                availability_status='in_season',
                season_start=date(today.year, 9, 1), season_end=date(today.year, 12, 31),
                allergens=[], allergens_declared=True, is_organic=True,
            ),
            dict(
                producer=sarah, category=fruit, name='Strawberries',
                description='Sun-ripened strawberries, picked same-day for peak flavour. Small batches — first come, first served.',
                price=Decimal('3.00'), unit='400g punnet', stock_quantity=25,
                availability_status='in_season',
                season_start=date(today.year, 5, 1), season_end=date(today.year, 8, 31),
                allergens=[], allergens_declared=True, is_organic=False,
                is_surplus=True, surplus_discount_percent=30,
                surplus_expires_at=now + timedelta(days=3),
                surplus_note='End-of-week surplus pick — grab them before they go to compost!',
            ),
            dict(
                producer=sarah, category=fruit, name='Conference Pears',
                description='Buttery, juicy Conference pears from our 60-year-old trees. Great for eating or poaching.',
                price=Decimal('2.80'), unit='3-pack', stock_quantity=35,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=sarah, category=fruit, name='Rhubarb',
                description='Tender forced rhubarb, deeply pink with a gentle tartness. Brilliant for crumbles, fools, and compotes.',
                price=Decimal('1.80'), unit='400g bundle', stock_quantity=20,
                availability_status='in_season',
                season_start=date(today.year, 3, 1), season_end=date(today.year, 6, 30),
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=sarah, category=fruit, name='Blackberries',
                description='Wild-gathered and orchard-grown blackberries. Deep purple, intensely flavoured.',
                price=Decimal('2.20'), unit='250g punnet', stock_quantity=15,
                availability_status='in_season',
                season_start=date(today.year, 7, 1), season_end=date(today.year, 10, 31),
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            # ── Mike – Brown's Dairy (5) ──────────────────────────────────────
            dict(
                producer=mike, category=dairy, name='Whole Milk',
                description="Full-fat whole milk from our Guernsey herd. Non-homogenised, with the cream on top.",
                price=Decimal('1.20'), unit='1 litre', stock_quantity=100,
                availability_status='year_round',
                allergens=['Milk'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=mike, category=dairy, name='Free-Range Eggs',
                description='Large free-range eggs from hens with year-round outdoor access to our paddocks.',
                price=Decimal('2.80'), unit='6 eggs', stock_quantity=70,
                availability_status='year_round',
                allergens=['Eggs'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=mike, category=dairy, name='Mature Cheddar',
                description='18-month aged cheddar, sharp and crumbly. Three-times winner at the Bristol Cheese Show.',
                price=Decimal('4.50'), unit='200g block', stock_quantity=45,
                availability_status='year_round',
                allergens=['Milk'], allergens_declared=True, is_organic=False,
                is_surplus=True, surplus_discount_percent=20,
                surplus_expires_at=now + timedelta(days=2),
                surplus_note='Short-dated stock — best before in 4 days, perfect for cooking.',
            ),
            dict(
                producer=mike, category=dairy, name='Natural Yogurt',
                description='Thick, creamy natural yogurt made with whole milk from our herd. No additives, no thickeners.',
                price=Decimal('1.80'), unit='500g pot', stock_quantity=55,
                availability_status='year_round',
                allergens=['Milk'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=mike, category=dairy, name='Double Cream',
                description='Rich double cream, poured straight from our separator. Perfect for whipping or pouring.',
                price=Decimal('1.60'), unit='250ml', stock_quantity=40,
                availability_status='year_round',
                allergens=['Milk'], allergens_declared=True, is_organic=False,
            ),
            # ── Emma – White's Artisan Bakery (5) ────────────────────────────
            dict(
                producer=emma, category=bread, name='Sourdough Loaf',
                description='48-hour slow-fermented white sourdough. Crisp crust, open crumb, complex flavour. Baked at 5am daily.',
                price=Decimal('3.80'), unit='800g loaf', stock_quantity=20,
                availability_status='year_round',
                allergens=['Gluten'], allergens_declared=True, is_organic=False,
                is_surplus=True, surplus_discount_percent=25,
                surplus_expires_at=now + timedelta(hours=18),
                surplus_note="Yesterday's bake — still excellent toasted, reduced to clear.",
            ),
            dict(
                producer=emma, category=bread, name='Wholemeal Rolls',
                description='Soft wholemeal dinner rolls made with stoneground flour from Shipton Mill. Pack of 4.',
                price=Decimal('2.50'), unit='4 rolls', stock_quantity=30,
                availability_status='year_round',
                allergens=['Gluten'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=emma, category=bread, name='Seeded Rye Loaf',
                description='Dense, slightly sour rye loaf studded with sunflower and pumpkin seeds. Keeps for up to a week.',
                price=Decimal('4.20'), unit='750g loaf', stock_quantity=15,
                availability_status='year_round',
                allergens=['Gluten'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=emma, category=bread, name='Almond Croissants',
                description='Flaky butter croissants filled with almond frangipane and topped with toasted flaked almonds.',
                price=Decimal('1.80'), unit='each', stock_quantity=25,
                availability_status='year_round',
                allergens=['Gluten', 'Milk', 'Eggs', 'Nuts'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=emma, category=bread, name='Spelt & Honey Scones',
                description='Light, crumbly scones made with wholegrain spelt flour and local honey. Pack of 4.',
                price=Decimal('2.80'), unit='4 scones', stock_quantity=18,
                availability_status='year_round',
                allergens=['Gluten', 'Milk', 'Eggs'], allergens_declared=True, is_organic=False,
            ),
            # ── Tom – Black's Farm Meats (5) ──────────────────────────────────
            dict(
                producer=tom, category=meat, name='Pork Sausages',
                description='Traditional British pork sausages, 80% meat content. Seasoned with sage, black pepper, and nutmeg.',
                price=Decimal('4.50'), unit='6 sausages (450g)', stock_quantity=35,
                availability_status='year_round',
                allergens=['Gluten'], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=tom, category=meat, name='Free-Range Chicken',
                description='Whole free-range chicken, raised outdoors for 81 days. Hung for 5 days for depth of flavour.',
                price=Decimal('9.50'), unit='whole bird (approx 1.6kg)', stock_quantity=12,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=tom, category=meat, name='Lamb Shoulder',
                description='Bone-in lamb shoulder from our Exmoor-cross flock. Slow-roast to fall-apart tenderness.',
                price=Decimal('13.00'), unit='approx 1.2kg', stock_quantity=8,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=tom, category=meat, name='Beef Mince',
                description='Lean beef mince from our native-breed Aberdeen Angus cattle, 80/20 lean-to-fat ratio.',
                price=Decimal('5.50'), unit='500g', stock_quantity=30,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=tom, category=meat, name='Dry-Cured Bacon',
                description='Traditional dry-cured back bacon, salt-cured for 10 days. Firm texture, deep flavour.',
                price=Decimal('3.80'), unit='200g pack', stock_quantity=28,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
                is_surplus=True, surplus_discount_percent=15,
                surplus_expires_at=now + timedelta(days=4),
                surplus_note='Overstock from this week — great price on premium bacon.',
            ),
            # ── Lucy – Wild Honey Apiaries (5) ────────────────────────────────
            dict(
                producer=lucy, category=honey, name='Wildflower Honey',
                description='Raw, unfiltered wildflower honey from our Bristol city apiaries. Light amber, floral and complex.',
                price=Decimal('5.50'), unit='340g jar', stock_quantity=50,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=lucy, category=honey, name='Strawberry Jam',
                description='Whole-fruit strawberry jam made with local strawberries and minimal sugar. No pectin, no additives.',
                price=Decimal('3.20'), unit='200g jar', stock_quantity=22,
                availability_status='in_season',
                season_start=date(today.year, 5, 1), season_end=date(today.year, 9, 30),
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=lucy, category=honey, name='Seville Orange Marmalade',
                description='Classic Seville orange marmalade with a slightly bitter finish. Made to a Victorian recipe.',
                price=Decimal('3.80'), unit='200g jar', stock_quantity=35,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
            dict(
                producer=lucy, category=honey, name='Blackcurrant Jam',
                description='Intensely fruity blackcurrant jam, vibrant deep purple. High in natural vitamin C.',
                price=Decimal('3.50'), unit='200g jar', stock_quantity=18,
                availability_status='in_season',
                season_start=date(today.year, 6, 1), season_end=date(today.year, 9, 30),
                allergens=[], allergens_declared=True, is_organic=False,
                is_surplus=True, surplus_discount_percent=10,
                surplus_expires_at=now + timedelta(days=7),
                surplus_note='Last cases from last season — excellent quality, clearing space.',
            ),
            dict(
                producer=lucy, category=honey, name='Honeycomb',
                description='Pure cut honeycomb, still in the wax cells. Exceptional depth of flavour. Serve with cheese or on toast.',
                price=Decimal('6.50'), unit='250g slab', stock_quantity=14,
                availability_status='year_round',
                allergens=[], allergens_declared=True, is_organic=False,
            ),
        ]

        image_map = {
            'Heritage Tomatoes':        'heritage-tomatoes.svg',
            'Courgettes':               'courgettes.svg',
            'New Potatoes':             'new-potatoes.svg',
            'Mixed Salad Leaves':       'mixed-salad-leaves.svg',
            'Kale & Rainbow Chard':     'kale-rainbow-chard.svg',
            'Cox Apples':               'cox-apples.svg',
            'Strawberries':             'strawberries.svg',
            'Conference Pears':         'conference-pears.svg',
            'Rhubarb':                  'rhubarb.svg',
            'Blackberries':             'blackberries.svg',
            'Whole Milk':               'whole-milk.svg',
            'Free-Range Eggs':          'free-range-eggs.svg',
            'Mature Cheddar':           'mature-cheddar.svg',
            'Natural Yogurt':           'natural-yogurt.svg',
            'Double Cream':             'double-cream.svg',
            'Sourdough Loaf':           'sourdough-loaf.svg',
            'Wholemeal Rolls':          'wholemeal-rolls.svg',
            'Seeded Rye Loaf':          'seeded-rye-loaf.svg',
            'Almond Croissants':        'almond-croissants.svg',
            'Spelt & Honey Scones':     'spelt-honey-scones.svg',
            'Pork Sausages':            'pork-sausages.svg',
            'Free-Range Chicken':       'free-range-chicken.svg',
            'Lamb Shoulder':            'lamb-shoulder.svg',
            'Beef Mince':               'beef-mince.svg',
            'Dry-Cured Bacon':          'dry-cured-bacon.svg',
            'Wildflower Honey':         'wildflower-honey.svg',
            'Strawberry Jam':           'strawberry-jam.svg',
            'Seville Orange Marmalade': 'seville-orange-marmalade.svg',
            'Blackcurrant Jam':         'blackcurrant-jam.svg',
            'Honeycomb':                'honeycomb.svg',
        }
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
            if not p.image:
                fn = image_map.get(p.name)
                if fn and (media_root / fn).exists():
                    # Point at the canonical file directly — avoids Django's
                    # hash-suffix collision handling when media/ is the same
                    # source and destination.
                    p.image.name = f'products/{fn}'
                    p.save(update_fields=['image'])
            products[p.name] = p
        return products

    # ── Farm Stories ──────────────────────────────────────────────────────────

    def _seed_farm_stories(self, producers):
        _, bob   = producers['Hillside Farm']
        _, sarah = producers['Green Orchard']
        _, mike  = producers["Brown's Dairy"]
        _, emma  = producers["White's Artisan Bakery"]
        _, tom   = producers["Black's Farm Meats"]
        _, lucy  = producers['Wild Honey Apiaries']

        stories = [
            dict(
                producer=bob,
                title='A Season of Heritage Tomatoes',
                seasonal_tag='Summer',
                body=(
                    'Growing heritage tomatoes is an act of faith. Unlike supermarket varieties '
                    'bred for shelf-life and uniformity, our heirlooms — Tigerella, Black Krim, '
                    'Yellow Pear — prioritise flavour above all else.\n\n'
                    'We start seeds in January under grow-lights, prick them out in March, and '
                    'plant into the polytunnels in May. By June the plants are flowering; by July '
                    'the first fruits arrive — sweet, complex, nothing like the January imports '
                    "you'll find elsewhere.\n\n"
                    'We pick every day through October, and every punnet goes out within 24 hours '
                    "of harvest. That's what local food means to us."
                ),
            ),
            dict(
                producer=sarah,
                title='Apple Harvest 2024 — Our Best Yet',
                seasonal_tag='Autumn',
                body=(
                    "This year's apple harvest exceeded every expectation. A warm, dry August "
                    'followed by cool September nights produced fruit with exceptional sugar-acid '
                    "balance — the best we've seen in fifteen years.\n\n"
                    "We harvest by hand, working through the orchard variety by variety as each "
                    "one reaches peak ripeness. The Cox trees — some planted by Sarah's grandfather "
                    "— came into their own this season, producing dense, aromatic fruit that "
                    "practically falls off the branch.\n\n"
                    "Every apple is hand-graded. Anything not quite perfect goes to the press for "
                    "juice. Nothing is wasted."
                ),
            ),
            dict(
                producer=mike,
                title='Meet Our Guernsey Herd',
                seasonal_tag='Year round',
                body=(
                    'Our herd of 48 Guernsey cows produces milk with naturally higher beta-carotene '
                    "and A2 protein than standard dairy breeds. That's why our milk has that "
                    "distinctive golden cream-line at the top of the bottle.\n\n"
                    'We made the decision not to homogenise in 2018, after tasting the difference. '
                    'Homogenisation forces the fat globules through tiny holes under pressure, '
                    "changing the structure of the milk permanently. We didn't think that was what "
                    "our customers wanted — and the response proved us right.\n\n"
                    'The cows graze from April through October on unimproved permanent pasture, '
                    "supplemented with our own hay over winter. What they eat directly affects "
                    "how the milk tastes — and you can tell the difference."
                ),
            ),
            dict(
                producer=emma,
                title='The Art of Slow Fermentation',
                seasonal_tag='Year round',
                body=(
                    "Real sourdough cannot be hurried. Our starter — named Dolly, 8 years old and "
                    "going strong — is fed twice daily with organic white flour and water. Each "
                    "evening we mix the dough. Each morning we shape it. The loaves proof overnight "
                    "in the fridge, slow and cold, developing the complex flavour that a fast "
                    "commercial loaf can never match.\n\n"
                    "The long fermentation also breaks down the phytic acid in wheat, making the "
                    "bread easier to digest and its minerals more bioavailable. Several customers "
                    "who thought they had a wheat intolerance have found they can eat our bread "
                    "without trouble.\n\n"
                    "We're in the bakery by 3am, seven days a week. The oven goes on at 4. "
                    "First loaves are ready by 6:30."
                ),
            ),
            dict(
                producer=tom,
                title='Why We Choose Pasture-Raised',
                seasonal_tag='Year round',
                body=(
                    "Animals on our farm have one job: to live well. Our pigs root in woodland "
                    "paddocks, our chickens range across 3 acres of grass, and our cattle and sheep "
                    "graze permanent pasture that hasn't seen a plough in over 40 years.\n\n"
                    "Pasture-raising is slower and more expensive than intensive production. "
                    "A free-range chicken takes 81 days to reach weight; a commercial broiler takes "
                    "35. That extra time means more muscle development, more marbling, more flavour "
                    "— and a life worth living for the bird.\n\n"
                    "We slaughter at a small family abattoir 12 miles away, avoiding the stress of "
                    "long journeys. The carcasses are hung at the right temperature for the right "
                    "amount of time. There are no shortcuts in this kitchen."
                ),
            ),
            dict(
                producer=lucy,
                title='A Year in the Life of Our Bristol Bees',
                seasonal_tag='Summer',
                body=(
                    "People are often surprised to learn that bees do brilliantly in cities. "
                    "Bristol's parks, gardens, allotments, and river corridors offer far greater "
                    "diversity of forage than intensive farmland.\n\n"
                    "Our hives sit on rooftops and in community gardens across the city. Each "
                    "location produces subtly different honey — the hives near the botanical "
                    "gardens give a lighter, more floral honey; those near the allotments on the "
                    "Downs produce something darker and more earthy.\n\n"
                    "We harvest once a year, in late August. We never take more than a third of "
                    "each colony's stores, ensuring the bees have plenty to see them through winter "
                    "without supplementary feeding. Slow, careful, sustainable — the only way to "
                    "keep bees in a city."
                ),
            ),
        ]

        for d in stories:
            if FarmStory.objects.filter(producer=d['producer'], title=d['title']).exists():
                skip(f"Story: {d['title'][:45]}")
                continue
            FarmStory.objects.create(**d)
            ok(f"Story: {d['title'][:55]}")

    # ── Recipes ───────────────────────────────────────────────────────────────

    def _seed_recipes(self, producers, products):
        _, bob   = producers['Hillside Farm']
        _, sarah = producers['Green Orchard']
        _, mike  = producers["Brown's Dairy"]
        _, emma  = producers["White's Artisan Bakery"]
        _, tom   = producers["Black's Farm Meats"]
        _, lucy  = producers['Wild Honey Apiaries']

        recipes = [
            dict(
                producer=bob,
                title='Roasted Heritage Tomato Pasta',
                seasonal_tag='Summer',
                description='A simple, stunning summer pasta that lets the tomatoes do all the work.',
                ingredients=(
                    '500g Heritage Tomatoes (halved)\n'
                    '400g pasta of your choice\n'
                    '4 cloves garlic (sliced)\n'
                    '4 tbsp extra virgin olive oil\n'
                    'Handful fresh basil\n'
                    'Parmesan to serve\n'
                    'Salt and black pepper'
                ),
                instructions=(
                    '1. Preheat oven to 200°C. Place tomatoes cut-side up on a baking tray, '
                    'scatter over garlic, drizzle with olive oil, season generously.\n'
                    '2. Roast for 25–30 minutes until caramelised and jammy at the edges.\n'
                    '3. Meanwhile, cook pasta in well-salted boiling water until al dente.\n'
                    '4. Tip the roasted tomatoes and all their juices into the drained pasta. '
                    'Toss together, adding a splash of pasta water to loosen.\n'
                    '5. Tear over basil, grate over Parmesan, serve immediately.'
                ),
                product_names=['Heritage Tomatoes'],
            ),
            dict(
                producer=sarah,
                title='Apple & Conference Pear Crumble',
                seasonal_tag='Autumn',
                description='The definitive British crumble — deeply fruity, warmly spiced, with a shatteringly crisp topping.',
                ingredients=(
                    '3 Cox Apples (peeled, cored, sliced)\n'
                    '3 Conference Pears (peeled, cored, sliced)\n'
                    '2 tbsp golden caster sugar\n'
                    '1 tsp cinnamon\n'
                    'Crumble: 200g plain flour, 100g cold butter (cubed), 100g demerara sugar, 50g rolled oats'
                ),
                instructions=(
                    '1. Preheat oven to 180°C. Toss fruit with sugar and cinnamon in a baking dish.\n'
                    "2. Rub butter into flour until it resembles breadcrumbs. Stir in sugar and oats.\n"
                    "3. Scatter crumble over fruit in an even layer — don't press it down.\n"
                    '4. Bake for 35–40 minutes until golden on top and bubbling at the edges.\n'
                    '5. Rest for 10 minutes before serving with cream, custard, or yogurt.'
                ),
                product_names=['Cox Apples', 'Conference Pears'],
            ),
            dict(
                producer=mike,
                title='Simple Cheese & Herb Omelette',
                seasonal_tag='Year round',
                description='The perfect two-minute supper. Good eggs and good cheese are all you need.',
                ingredients=(
                    '3 Free-Range Eggs\n'
                    '50g Mature Cheddar (grated)\n'
                    '15g butter\n'
                    'Fresh chives or parsley (chopped)\n'
                    'Salt and white pepper'
                ),
                instructions=(
                    '1. Beat eggs with a pinch of salt and white pepper until just combined.\n'
                    '2. Melt butter in a non-stick pan over medium-high heat until foaming.\n'
                    '3. Pour in eggs. As the edges set, draw them gently towards the centre '
                    'with a spatula, letting liquid egg flow to the sides.\n'
                    '4. When just set but still slightly glossy, scatter cheese and herbs over one half.\n'
                    '5. Fold the other half over, slide onto a warm plate, serve immediately.'
                ),
                product_names=['Free-Range Eggs', 'Mature Cheddar'],
            ),
            dict(
                producer=emma,
                title='Sourdough Toast with Honey & Ricotta',
                seasonal_tag='Year round',
                description='The simplest thing you can do with good bread. An ideal breakfast or snack.',
                ingredients=(
                    '2 thick slices Sourdough Loaf\n'
                    '4 tbsp ricotta\n'
                    '2 tbsp Wildflower Honey\n'
                    'Flaked sea salt\n'
                    'Fresh thyme (optional)'
                ),
                instructions=(
                    '1. Toast sourdough slices until deep golden and crisp.\n'
                    '2. Spread generously with ricotta while the bread is still warm.\n'
                    '3. Drizzle with honey, letting it pool into the ricotta.\n'
                    '4. Finish with a pinch of flaked sea salt and fresh thyme if using.\n'
                    '5. Eat immediately.'
                ),
                product_names=['Sourdough Loaf'],
            ),
            dict(
                producer=tom,
                title='Sausage, Kale & White Bean Casserole',
                seasonal_tag='Winter',
                description='A hearty one-pot that gets better the next day. A proper winter warmer.',
                ingredients=(
                    '6 Pork Sausages\n'
                    '200g Kale & Rainbow Chard (roughly chopped)\n'
                    '2 x 400g tins white beans (drained)\n'
                    '1 tin chopped tomatoes\n'
                    '1 onion (diced)\n'
                    '4 cloves garlic (sliced)\n'
                    '500ml chicken stock\n'
                    'Olive oil, salt, pepper, smoked paprika'
                ),
                instructions=(
                    '1. Brown sausages in olive oil in a large casserole until golden all over. '
                    'Remove and set aside.\n'
                    '2. Soften onion in the same pan for 8 minutes. Add garlic and paprika, '
                    'cook 1 minute more.\n'
                    '3. Add tomatoes and stock. Simmer 5 minutes, then return sausages to the pan.\n'
                    '4. Add beans and kale, push everything under the liquid.\n'
                    '5. Simmer covered for 20 minutes, then uncovered for 10 to thicken. '
                    'Adjust seasoning and serve with crusty bread.'
                ),
                product_names=['Pork Sausages', 'Kale & Rainbow Chard'],
            ),
            dict(
                producer=lucy,
                title='Honey & Yogurt Parfait with Blackberries',
                seasonal_tag='Summer',
                description='A layered breakfast parfait that takes 5 minutes and tastes like something from a café.',
                ingredients=(
                    '200g Natural Yogurt\n'
                    '2 tbsp Wildflower Honey\n'
                    '125g Blackberries\n'
                    '50g granola\n'
                    'Pinch of cinnamon'
                ),
                instructions=(
                    '1. Lightly crush half the blackberries with a fork to release their juice.\n'
                    '2. In a serving glass, layer granola, yogurt, crushed blackberries, '
                    'and whole blackberries.\n'
                    '3. Drizzle honey over the top.\n'
                    '4. Finish with a pinch of cinnamon and serve immediately, or chill '
                    'for up to 2 hours.'
                ),
                product_names=['Wildflower Honey', 'Blackberries'],
            ),
        ]

        for d in recipes:
            product_names = d.pop('product_names')
            if Recipe.objects.filter(producer=d['producer'], title=d['title']).exists():
                skip(f"Recipe: {d['title'][:45]}")
                continue
            r = Recipe.objects.create(**d)
            r.products.set([products[n] for n in product_names if n in products])
            ok(f"Recipe: {r.title[:55]}")

    # ── Orders ────────────────────────────────────────────────────────────────

    def _seed_orders(self, customers, producers, products):
        alice      = customers['Alice']
        charlie    = customers['Charlie']
        community  = customers['Community Kitchen']
        restaurant = customers['Harbourside Kitchen']

        _, bob   = producers['Hillside Farm']
        _, sarah = producers['Green Orchard']
        _, mike  = producers["Brown's Dairy"]
        _, emma  = producers["White's Artisan Bakery"]
        _, tom   = producers["Black's Farm Meats"]
        _, lucy  = producers['Wild Honey Apiaries']

        today = date.today()
        delivered_items = {}  # (customer_email, product_name) -> OrderItem

        def collect(result, customer):
            order, items = result
            if order and order.status == 'delivered':
                for oi in items:
                    delivered_items[(customer.email, oi.product_name)] = oi

        addr = lambda u: u.customer_profile.delivery_address

        # ── Alice (5 orders) ──────────────────────────────────────────────────
        self._make_order(
            customer=alice, delivery_address=addr(alice),
            delivery_date=today + timedelta(days=4), status='pending',
            items=[(products['Heritage Tomatoes'], bob, 2), (products['Whole Milk'], mike, 3)],
            label='Alice / Pending',
        )
        self._make_order(
            customer=alice, delivery_address=addr(alice),
            delivery_date=today + timedelta(days=7), status='confirmed',
            items=[
                (products['Kale & Rainbow Chard'], bob, 1),
                (products['Free-Range Eggs'], mike, 2),
                (products['Sourdough Loaf'], emma, 1),
            ],
            label='Alice / Confirmed',
        )
        self._make_order(
            customer=alice, delivery_address=addr(alice),
            delivery_date=today + timedelta(days=12), status='pending',
            items=[(products['Cox Apples'], sarah, 3), (products['Wildflower Honey'], lucy, 1)],
            label='Alice / Pending 2',
        )
        collect(
            self._make_order(
                customer=alice, delivery_address=addr(alice),
                delivery_date=today - timedelta(days=2), status='delivered',
                items=[(products['New Potatoes'], bob, 3), (products['Mature Cheddar'], mike, 1)],
                label='Alice / Delivered', payment_completed=True,
            ),
            alice,
        )
        collect(
            self._make_order(
                customer=alice, delivery_address=addr(alice),
                delivery_date=today - timedelta(days=5), status='delivered',
                items=[(products['Pork Sausages'], tom, 2), (products['Mixed Salad Leaves'], bob, 2)],
                label='Alice / Delivered 2', payment_completed=True,
            ),
            alice,
        )

        # ── Charlie (3 orders) ────────────────────────────────────────────────
        self._make_order(
            customer=charlie, delivery_address=addr(charlie),
            delivery_date=today + timedelta(days=3), status='confirmed',
            items=[(products['Conference Pears'], sarah, 2), (products['Free-Range Eggs'], mike, 1)],
            label='Charlie / Confirmed',
        )
        self._make_order(
            customer=charlie, delivery_address=addr(charlie),
            delivery_date=today + timedelta(days=8), status='pending',
            items=[
                (products['Courgettes'], bob, 3),
                (products['Natural Yogurt'], mike, 2),
                (products['Wholemeal Rolls'], emma, 2),
            ],
            label='Charlie / Pending',
        )
        collect(
            self._make_order(
                customer=charlie, delivery_address=addr(charlie),
                delivery_date=today - timedelta(days=3), status='delivered',
                items=[
                    (products['Cox Apples'], sarah, 2),
                    (products['Sourdough Loaf'], emma, 1),
                    (products['Mature Cheddar'], mike, 1),
                ],
                label='Charlie / Delivered', payment_completed=True,
            ),
            charlie,
        )

        # ── Community Kitchen (2 orders) ──────────────────────────────────────
        self._make_order(
            customer=community, delivery_address=addr(community),
            delivery_date=today + timedelta(days=5), status='confirmed',
            items=[
                (products['Heritage Tomatoes'], bob, 5),
                (products['Kale & Rainbow Chard'], bob, 3),
                (products['Whole Milk'], mike, 6),
                (products['Free-Range Eggs'], mike, 4),
            ],
            label='Community Kitchen / Confirmed',
            special_instructions='Please pack in separate boxes by producer.',
        )
        self._make_order(
            customer=community, delivery_address=addr(community),
            delivery_date=today + timedelta(days=10), status='pending',
            items=[
                (products['New Potatoes'], bob, 8),
                (products['Mixed Salad Leaves'], bob, 4),
                (products['Natural Yogurt'], mike, 3),
            ],
            label='Community Kitchen / Pending',
        )

        # ── Harbourside Kitchen (2 orders) ────────────────────────────────────
        self._make_order(
            customer=restaurant, delivery_address=addr(restaurant),
            delivery_date=today + timedelta(days=4), status='confirmed',
            items=[
                (products['Pork Sausages'], tom, 4),
                (products['Free-Range Chicken'], tom, 2),
                (products['Lamb Shoulder'], tom, 1),
                (products['Beef Mince'], tom, 2),
            ],
            label='Harbourside Kitchen / Confirmed',
            special_instructions='Delivery before 8am. Ring kitchen bell on side entrance.',
        )
        self._make_order(
            customer=restaurant, delivery_address=addr(restaurant),
            delivery_date=today + timedelta(days=6), status='pending',
            items=[
                (products['Sourdough Loaf'], emma, 3),
                (products['Double Cream'], mike, 4),
                (products['Wildflower Honey'], lucy, 2),
                (products['Blackberries'], sarah, 3),
            ],
            label='Harbourside Kitchen / Pending 2',
            special_instructions='Side entrance on Wapping Wharf.',
        )

        return delivered_items

    def _make_order(self, customer, delivery_address, delivery_date,
                    status, items, label, payment_completed=False,
                    special_instructions=''):
        if Order.objects.filter(customer=customer, delivery_date=delivery_date).exists():
            skip(f'Order ({label})')
            return None, []

        order = Order.objects.create(
            customer=customer,
            delivery_address=delivery_address,
            delivery_date=delivery_date,
            status=status,
            special_instructions=special_instructions,
        )

        # Group items by producer → one ProducerOrder per producer
        by_producer = {}
        for product, producer_profile, qty in items:
            pid = producer_profile.id
            if pid not in by_producer:
                by_producer[pid] = {'producer': producer_profile, 'items': []}
            by_producer[pid]['items'].append((product, qty))

        created_items = []
        for group in by_producer.values():
            pp = group['producer']
            prod_order = ProducerOrder.objects.create(
                order=order,
                producer=pp,
                delivery_date=delivery_date,
                status=status,
                special_instructions=special_instructions,
            )
            for product, qty in group['items']:
                oi = OrderItem.objects.create(
                    order=order,
                    producer_order=prod_order,
                    product=product,
                    producer=pp,
                    product_name=product.name,
                    price_at_time=product.effective_price,
                    quantity=qty,
                )
                created_items.append(oi)

        total = sum(oi.line_total for oi in created_items)
        commission = (total * Decimal('0.05')).quantize(Decimal('0.01'))
        Payment.objects.create(
            order=order,
            amount=total,
            commission=commission,
            producer_amount=total - commission,
            status='completed' if payment_completed else 'pending',
        )

        # Audit trail for advanced statuses
        trail = {
            'confirmed': [('pending', 'confirmed')],
            'ready':     [('pending', 'confirmed'), ('confirmed', 'ready')],
            'delivered': [('pending', 'confirmed'), ('confirmed', 'ready'), ('ready', 'delivered')],
            'cancelled': [('pending', 'cancelled')],
        }
        for from_s, to_s in trail.get(status, []):
            OrderStatusHistory.objects.create(order=order, from_status=from_s, to_status=to_s)

        ok(f'Order {order.order_number} ({label})')
        return order, created_items

    # ── Reviews ───────────────────────────────────────────────────────────────

    def _seed_reviews(self, customers, products, delivered_items):
        alice   = customers['Alice']
        charlie = customers['Charlie']

        reviews = [
            dict(
                customer=alice, product_name='New Potatoes', rating=5,
                title="Best potatoes I've ever bought",
                text=(
                    'These were absolutely outstanding. Freshly dug, earthy, sweet — just '
                    'boiled with a sprig of mint and served with butter. My kids who never '
                    'eat vegetables had three helpings. Will be ordering every week.'
                ),
            ),
            dict(
                customer=alice, product_name='Mature Cheddar', rating=5,
                title='Award-winning cheese lives up to the name',
                text=(
                    'Sharp, crumbly, and complex — this is exactly what cheddar is supposed '
                    'to taste like. Used it in a pasta bake and the whole house smelled incredible. '
                    'Worth every penny.'
                ),
                producer_response=(
                    'Thank you Alice! The 18-month ageing really does make all the difference. '
                    'Hope to see you at our farm open day next month. — Mike'
                ),
            ),
            dict(
                customer=alice, product_name='Pork Sausages', rating=4,
                title='Excellent sausages, great for a proper fry-up',
                text=(
                    'High meat content, great seasoning — not too much filler like the supermarket '
                    "ones. Cooked them on a Sunday with proper scrambled eggs. Knocked a star off "
                    "only because I'd have liked a slightly smoother skin, but these are very good."
                ),
            ),
            dict(
                customer=alice, product_name='Mixed Salad Leaves', rating=5,
                title='So fresh it barely needs dressing',
                text=(
                    "I've been buying salad bags from the supermarket for years and this is "
                    "genuinely a different product. Cut fresh, vibrant, no limp edges or brown bits. "
                    "A good olive oil and lemon juice is all it needs."
                ),
            ),
            dict(
                customer=charlie, product_name='Cox Apples', rating=5,
                title='Flavour you simply cannot find in shops',
                text=(
                    "I grew up eating Cox apples from my gran's garden and had forgotten how good "
                    "they can be. These taste exactly like I remembered — aromatic, slightly tart, "
                    "with that distinctive honeyed finish. Brilliant."
                ),
            ),
            dict(
                customer=charlie, product_name='Sourdough Loaf', rating=5,
                title="The real deal — proper sourdough",
                text=(
                    "I've tried every 'sourdough' in Bristol and most are just white bread with a "
                    "slight tang. This one is the genuine article — open crumb, complex sour flavour, "
                    "crust that shatters. I've ordered twice more since."
                ),
                producer_response=(
                    "That means everything to us, Charlie. Dolly the starter would be pleased! — Emma"
                ),
            ),
            dict(
                customer=charlie, product_name='Mature Cheddar', rating=4,
                title='Excellent quality, good value for artisan cheese',
                text=(
                    'Really nice cheddar with proper depth — great for a cheeseboard or cooking. '
                    'Used it in a quiche and it held its flavour well even after baking. Only '
                    'wish the block were a bit bigger for the price!'
                ),
            ),
        ]

        for r in reviews:
            customer = r['customer']
            product  = products.get(r['product_name'])
            if not product:
                continue
            key = (customer.email, r['product_name'])
            oi  = delivered_items.get(key)
            if not oi:
                skip(f"Review for {r['product_name']} (no delivered order item)")
                continue
            if ProductReview.objects.filter(customer=customer, product=product).exists():
                skip(f"Review: {r['product_name']} by {customer.first_name}")
                continue
            review = ProductReview.objects.create(
                customer=customer,
                product=product,
                order_item=oi,
                rating=r['rating'],
                title=r['title'],
                text=r['text'],
                verified_purchase=True,
            )
            pr = r.get('producer_response')
            if pr:
                review.producer_response = pr
                review.producer_response_at = timezone.now()
                review.save()
            ok(f"Review: {r['product_name']} by {customer.first_name} ({r['rating']}/5)")

    # ── Recurring Orders ──────────────────────────────────────────────────────

    def _seed_recurring_orders(self, customers, producers, products):
        restaurant = customers['Harbourside Kitchen']
        community  = customers['Community Kitchen']

        _, bob  = producers['Hillside Farm']
        _, mike = producers["Brown's Dairy"]
        _, emma = producers["White's Artisan Bakery"]
        _, tom  = producers["Black's Farm Meats"]

        today = date.today()
        days_to_wed = (2 - today.weekday()) % 7 or 7
        days_to_mon = (0 - today.weekday()) % 7 or 7
        next_wed = today + timedelta(days=days_to_wed)
        next_mon = today + timedelta(days=days_to_mon)

        recurring_data = [
            dict(
                customer=restaurant,
                name='Weekly Meat & Bread Box',
                frequency='weekly',
                delivery_weekday=2,
                next_delivery_date=next_wed,
                special_instructions='Deliver to kitchen side entrance before 8am.',
                is_active=True,
                items=[
                    (products['Pork Sausages'],    tom,  4),
                    (products['Free-Range Chicken'], tom, 2),
                    (products['Sourdough Loaf'],   emma, 3),
                    (products['Wholemeal Rolls'],  emma, 2),
                ],
            ),
            dict(
                customer=community,
                name='Fortnightly Community Veg & Dairy',
                frequency='fortnightly',
                delivery_weekday=0,
                next_delivery_date=next_mon,
                special_instructions='Leave in the community centre lobby if no one answers.',
                is_active=True,
                items=[
                    (products['Kale & Rainbow Chard'], bob,  4),
                    (products['New Potatoes'],          bob,  6),
                    (products['Whole Milk'],            mike, 8),
                    (products['Free-Range Eggs'],       mike, 6),
                    (products['Natural Yogurt'],        mike, 4),
                ],
            ),
        ]

        for d in recurring_data:
            items = d.pop('items')
            if RecurringOrder.objects.filter(customer=d['customer'], name=d['name']).exists():
                skip(f"Recurring: {d['name']}")
                continue
            ro = RecurringOrder.objects.create(**d)
            for product, producer, qty in items:
                RecurringOrderItem.objects.create(
                    recurring_order=ro, product=product, producer=producer, quantity=qty,
                )
            ok(f"Recurring order: {ro.name} ({ro.frequency}) for {ro.customer.email}")

    # ── Credentials summary ───────────────────────────────────────────────────

    def _print_credentials(self, producers, customers):
        self.stdout.write(self.style.HTTP_INFO('-' * 60))
        self.stdout.write(self.style.HTTP_INFO('Demo Credentials  (password: Testpass99!)'))
        self.stdout.write(self.style.HTTP_INFO('-' * 60))
        self.stdout.write('\nProducers:')
        for name, (user, _) in producers.items():
            print(f'  {user.email:<42}  {name}')
        self.stdout.write('\nCustomers:')
        role_labels = {'customer': 'individual', 'community': 'community group', 'restaurant': 'restaurant'}
        for name, user in customers.items():
            label = role_labels.get(user.role, user.role)
            print(f'  {user.email:<42}  {name}  ({label})')
        self.stdout.write('\nAdmin:')
        print('  python manage.py createsuperuser')
        self.stdout.write('')
