from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, ProducerProfile, User
from orders.models import Order, OrderItem, Payment, ProducerOrder
from .models import Category, Product, ProductReview


# --- Helpers ---

def make_producer(email='producer@test.com', password='Testpass99!'):
    user = User.objects.create_user(
        email=email, password=password,
        first_name='Bob', last_name='Jones', role='producer'
    )
    profile = ProducerProfile.objects.create(
        user=user, business_name='Test Farm',
        business_address='Farm Lane', postcode='BS2 2BB'
    )
    return user, profile


def make_producer2(email='producer2@test.com', password='Testpass99!'):
    user = User.objects.create_user(
        email=email, password=password,
        first_name='Jane', last_name='Doe', role='producer'
    )
    profile = ProducerProfile.objects.create(
        user=user, business_name='Jane\'s Farm',
        business_address='Other Lane', postcode='BS3 3CC'
    )
    return user, profile


def make_customer(email='customer@test.com', password='Testpass99!'):
    user = User.objects.create_user(
        email=email, password=password,
        first_name='Alice', last_name='Smith', role='customer'
    )
    CustomerProfile.objects.create(user=user, delivery_address='1 Test St', postcode='BS1 1AA')
    return user


def make_category(name='Vegetables', slug='vegetables'):
    return Category.objects.create(name=name, slug=slug)


def make_product(producer_profile, category=None, name='Tomatoes',
                 stock=10, availability='year_round', allergens=None,
                 description=None):
    return Product.objects.create(
        producer=producer_profile,
        category=category,
        name=name,
        description=description or f'Description for {name}',
        price='2.50',
        unit='per kg',
        stock_quantity=stock,
        availability_status=availability,
        allergens=allergens or [],
    )


# --- TC-003: Product Listing ---

class ProductListTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.category = make_category()

    def test_product_list_shows_available_products(self):
        """TC-003: Available products appear on the list page."""
        make_product(self.producer, self.category, name='Tomatoes', stock=10)
        response = self.client.get(reverse('products:product_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Tomatoes')

    def test_product_list_hides_zero_stock(self):
        """TC-003: Out-of-stock products are not shown."""
        make_product(self.producer, self.category, name='Empty Product', stock=0)
        response = self.client.get(reverse('products:product_list'))
        self.assertNotContains(response, 'Empty Product')

    def test_product_list_hides_out_of_season(self):
        """TC-003 / TC-016: Out-of-season products are not shown."""
        make_product(self.producer, self.category, name='Summer Fruit', stock=5, availability='out_of_season')
        response = self.client.get(reverse('products:product_list'))
        self.assertNotContains(response, 'Summer Fruit')

    def test_product_list_shows_in_stock_in_season(self):
        """TC-003: In-stock, in-season product is visible."""
        make_product(self.producer, self.category, name='Strawberries', stock=20, availability='in_season')
        response = self.client.get(reverse('products:product_list'))
        self.assertContains(response, 'Strawberries')


# --- TC-004: Browse by Category ---

class CategoryTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.veg = make_category('Vegetables', 'vegetables')
        self.dairy = make_category('Dairy', 'dairy')
        make_product(self.producer, self.veg, name='Carrots', stock=5)
        make_product(self.producer, self.dairy, name='Milk', stock=3)

    def test_category_list_page_loads(self):
        """TC-004: Category list page returns 200."""
        response = self.client.get(reverse('products:category_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Vegetables')
        self.assertContains(response, 'Dairy')

    def test_products_by_category_filters_correctly(self):
        """TC-004: Browsing a category shows only that category's products."""
        response = self.client.get(reverse('products:products_by_category', args=['vegetables']))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Carrots')
        self.assertNotContains(response, 'Milk')

    def test_category_filter_on_product_list(self):
        """TC-004: ?category= GET param filters product list."""
        response = self.client.get(reverse('products:product_list') + '?category=dairy')
        self.assertContains(response, 'Milk')
        self.assertNotContains(response, 'Carrots')


# --- TC-005: Product Search ---

class ProductSearchTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        cat = make_category()
        make_product(self.producer, cat, name='Organic Tomatoes', stock=10)
        make_product(self.producer, cat, name='Fresh Lettuce', stock=5)

    def test_search_by_name(self):
        """TC-005: Search matches product name."""
        response = self.client.get(reverse('products:product_search') + '?q=tomato')
        self.assertContains(response, 'Organic Tomatoes')
        self.assertNotContains(response, 'Fresh Lettuce')

    def test_search_case_insensitive(self):
        """TC-005: Search is case-insensitive."""
        response = self.client.get(reverse('products:product_search') + '?q=TOMATO')
        self.assertContains(response, 'Organic Tomatoes')

    def test_search_by_description(self):
        """TC-005: Search matches product description."""
        Product.objects.filter(name='Fresh Lettuce').update(description='crispy green salad leaves')
        response = self.client.get(reverse('products:product_search') + '?q=crispy')
        self.assertContains(response, 'Fresh Lettuce')

    def test_search_by_producer_name(self):
        """TC-005: Search matches producer business name."""
        response = self.client.get(reverse('products:product_search') + '?q=Test Farm')
        self.assertContains(response, 'Organic Tomatoes')

    def test_search_empty_query_returns_all(self):
        """TC-005: Empty search returns all available products."""
        response = self.client.get(reverse('products:product_search') + '?q=')
        self.assertContains(response, 'Organic Tomatoes')
        self.assertContains(response, 'Fresh Lettuce')

    def test_search_hides_out_of_stock(self):
        """TC-005: Search does not return out-of-stock products."""
        cat = make_category('Other', 'other')
        _, p2 = make_producer('p2@test.com')
        make_product(p2, cat, name='Empty Beans', stock=0)
        response = self.client.get(reverse('products:product_search') + '?q=empty')
        self.assertNotContains(response, 'Empty Beans')


# --- TC-011: Inventory Management ---

class InventoryManagementTests(TestCase):

    def setUp(self):
        self.user, self.producer = make_producer()
        _, self.other_producer = make_producer2()
        cat = make_category()
        self.product = make_product(self.producer, cat, name='Test Veg', stock=20)

    def test_stock_update_succeeds_for_owner(self):
        """TC-011: Producer can update stock for their own product."""
        self.client.login(username='producer@test.com', password='Testpass99!')
        response = self.client.post(
            reverse('products:stock_update', args=[self.product.pk]),
            {'stock_quantity': 50}
        )
        self.assertRedirects(response, reverse('products:producer_dashboard'))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 50)

    def test_stock_update_blocked_for_non_owner(self):
        """TC-011: Producer cannot update stock for another producer's product."""
        self.client.login(username='producer2@test.com', password='Testpass99!')
        response = self.client.post(
            reverse('products:stock_update', args=[self.product.pk]),
            {'stock_quantity': 999}
        )
        self.assertEqual(response.status_code, 404)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_stock_update_rejects_negative(self):
        """TC-011: Negative stock quantity is rejected."""
        self.client.login(username='producer@test.com', password='Testpass99!')
        response = self.client.post(
            reverse('products:stock_update', args=[self.product.pk]),
            {'stock_quantity': -1}
        )
        self.assertEqual(response.status_code, 200)  # re-renders form with errors
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 20)

    def test_stock_update_blocked_for_customer(self):
        """TC-011: Customer cannot access stock update page."""
        make_customer()
        self.client.login(username='customer@test.com', password='Testpass99!')
        response = self.client.post(
            reverse('products:stock_update', args=[self.product.pk]),
            {'stock_quantity': 99}
        )
        self.assertEqual(response.status_code, 403)

    def test_producer_dashboard_shows_all_own_products(self):
        """TC-011: Dashboard shows all products belonging to this producer."""
        self.client.login(username='producer@test.com', password='Testpass99!')
        cat = make_category('Extra', 'extra')
        make_product(self.producer, cat, name='Second Product', stock=5)
        response = self.client.get(reverse('products:producer_dashboard'))
        self.assertContains(response, 'Test Veg')
        self.assertContains(response, 'Second Product')


# --- TC-016: Seasonal Availability ---

class SeasonalAvailabilityTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_in_season_badge_shown_on_detail(self):
        """TC-016: In-season badge appears on product detail page."""
        product = make_product(self.producer, self.cat, name='Strawberries', stock=10, availability='in_season')
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'In Season')

    def test_out_of_season_hidden_from_list(self):
        """TC-016: Out-of-season products do not appear in product list."""
        make_product(self.producer, self.cat, name='Winter Squash', stock=5, availability='out_of_season')
        response = self.client.get(reverse('products:product_list'))
        self.assertNotContains(response, 'Winter Squash')

    def test_year_round_product_always_visible(self):
        """TC-016: Year-round product appears in list."""
        make_product(self.producer, self.cat, name='Year Round Eggs', stock=10, availability='year_round')
        response = self.client.get(reverse('products:product_list'))
        self.assertContains(response, 'Year Round Eggs')


# --- TC-003 extras: product detail content and access control ---

class ProductDetailContentTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_product_detail_shows_producer_name(self):
        """TC-003: Product detail page shows the producer's business name."""
        product = make_product(self.producer, self.cat, name='Crunchy Carrots', stock=5)
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Test Farm')

    def test_product_detail_shows_price(self):
        """TC-003: Product detail page shows the price."""
        product = make_product(self.producer, self.cat, name='Priced Carrots', stock=5)
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, '2.50')

    def test_product_detail_shows_availability_status(self):
        """TC-003/TC-016: In-season product shows 'In Season' badge on detail page."""
        product = make_product(self.producer, self.cat, name='Summer Berries', stock=5, availability='in_season')
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'In Season')


class ProductAccessControlTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_customer_cannot_access_product_create(self):
        """TC-003/TC-022: Customer is denied access to the product creation page."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('products:product_create'))
        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_cannot_access_product_create(self):
        """TC-003/TC-022: Unauthenticated user is redirected when accessing product creation."""
        response = self.client.get(reverse('products:product_create'))
        self.assertEqual(response.status_code, 302)

    def test_producer_cannot_edit_other_producers_product(self):
        """TC-003/TC-011: Producer gets 404 attempting to edit another producer's product."""
        _, other_producer = make_producer2()
        other_product = make_product(other_producer, self.cat, name='Other Veg', stock=5)
        self.client.login(username='producer@test.com', password='Testpass99!')
        response = self.client.post(
            reverse('products:product_edit', args=[other_product.pk]),
            {'name': 'Hacked', 'price': '1.00'},
        )
        self.assertEqual(response.status_code, 404)


# --- TC-014 extras: organic badge on product detail ---

class OrganicCertificationTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_organic_badge_on_product_detail(self):
        """TC-014: Organic badge appears on product detail page for certified products."""
        product = make_product(self.producer, self.cat, name='Organic Kale', stock=5)
        Product.objects.filter(pk=product.pk).update(is_organic=True)
        product.refresh_from_db()
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Organic')

    def test_non_organic_not_shown_in_organic_filter(self):
        """TC-014: Non-organic product absent when organic filter active."""
        make_product(self.producer, self.cat, name='Standard Carrot', stock=5)
        response = self.client.get(reverse('products:product_list') + '?organic=1')
        self.assertNotContains(response, 'Standard Carrot')

    def test_organic_filter_and_category_combine(self):
        """TC-014: Organic filter works across all categories."""
        cat2 = make_category('Dairy', 'dairy')
        p = make_product(self.producer, cat2, name='Organic Milk', stock=5)
        Product.objects.filter(pk=p.pk).update(is_organic=True)
        response = self.client.get(reverse('products:product_list') + '?organic=1')
        self.assertContains(response, 'Organic Milk')


# --- TC-015 extras: allergen display ---

class AllergenDisplayTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_allergen_free_product_shows_no_allergens_message(self):
        """TC-015: Allergen-free product shows a 'no allergens' indicator."""
        product = make_product(self.producer, self.cat, name='Fresh Apples', allergens=[])
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'No common allergen')

    def test_multiple_allergens_all_listed(self):
        """TC-015: Product with multiple allergens lists each one."""
        product = make_product(self.producer, self.cat, name='Walnut Bread',
                               allergens=['Gluten', 'Nuts'])
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Gluten')
        self.assertContains(response, 'Nuts')

    def test_allergen_exclusion_search_hides_matching(self):
        """TC-015: ?allergen_exclude= hides products containing that allergen."""
        make_product(self.producer, self.cat, name='Hazelnut Cake', allergens=['Nuts'], stock=5)
        make_product(self.producer, self.cat, name='Plain Bread', allergens=[], stock=5)
        response = self.client.get(reverse('products:product_search') + '?allergen_exclude=Nuts')
        self.assertNotContains(response, 'Hazelnut Cake')
        self.assertContains(response, 'Plain Bread')


# --- TC-016 extras: seasonal dates and year-round no restriction ---

class SeasonalDatesTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def test_seasonal_dates_shown_on_product_detail(self):
        """TC-016: Season start/end months are displayed on product detail."""
        from datetime import date
        product = Product.objects.create(
            producer=self.producer,
            category=self.cat,
            name='Strawberries',
            description='Sweet strawberries',
            price='3.00',
            unit='punnet',
            stock_quantity=10,
            availability_status='in_season',
            season_start=date(2025, 6, 1),
            season_end=date(2025, 8, 31),
        )
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Available:')

    def test_year_round_product_no_season_restriction_shown(self):
        """TC-016: Year-round products do not show seasonal date restrictions."""
        product = make_product(self.producer, self.cat, name='Year Veg', stock=5, availability='year_round')
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertNotContains(response, 'Out of Season')


# --- TC-019 extras: surplus deals page ---

class SurplusDealsPageTests(TestCase):

    def setUp(self):
        self.user, self.producer = make_producer()
        self.cat = make_category()

    def test_surplus_deals_page_loads(self):
        """TC-019: Surplus deals page returns 200."""
        response = self.client.get(reverse('products:surplus_deals'))
        self.assertEqual(response.status_code, 200)

    def test_surplus_deals_page_shows_discounted_product(self):
        """TC-019: Active surplus product appears on surplus deals page with discount badge."""
        product = make_product(self.producer, self.cat, name='Surplus Lettuce', stock=20)
        self.client.force_login(self.user)
        self.client.post(reverse('products:mark_surplus', args=[product.pk]), {
            'discount_percent': 25,
            'expires_at': (timezone.now() + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M'),
            'note': 'Must go today',
        })
        response = self.client.get(reverse('products:surplus_deals'))
        self.assertContains(response, 'Surplus Lettuce')
        self.assertContains(response, '25')

    def test_surplus_deals_shows_original_and_discounted_price(self):
        """TC-019: Surplus page displays both the original and discounted price."""
        product = make_product(self.producer, self.cat, name='Cheap Tomatoes', stock=30)
        self.client.force_login(self.user)
        self.client.post(reverse('products:mark_surplus', args=[product.pk]), {
            'discount_percent': 30,
            'expires_at': (timezone.now() + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M'),
            'note': '',
        })
        response = self.client.get(reverse('products:surplus_deals'))
        self.assertContains(response, '2.50')   # original price
        self.assertContains(response, '1.75')   # discounted price (2.50 * 0.70)


# --- TC-024 extras: review access and average rating ---

class ProductReviewExtrasTests(TestCase):

    def setUp(self):
        _, self.producer = make_producer()
        self.cat = make_category()

    def _make_delivered_order(self, customer, product):
        order = Order.objects.create(
            customer=customer,
            delivery_address='1 Test St',
            delivery_date=(timezone.now() + timedelta(days=3)).date(),
            status='delivered',
        )
        po = ProducerOrder.objects.create(
            order=order, producer=self.producer,
            delivery_date=order.delivery_date, status='delivered',
        )
        price = Decimal(str(product.price))
        item = OrderItem.objects.create(
            order=order, producer_order=po, product=product,
            producer=self.producer, product_name=product.name,
            price_at_time=price, quantity=1,
        )
        Payment.objects.create(
            order=order, amount=price,
            commission=(price * Decimal('0.05')).quantize(Decimal('0.01')),
            producer_amount=(price * Decimal('0.95')).quantize(Decimal('0.01')),
        )
        return order, item

    def test_average_rating_shown_on_product_detail(self):
        """TC-024: Average rating appears on product detail after a review is submitted."""
        customer = make_customer()
        product = make_product(self.producer, self.cat, name='Reviewed Veg', stock=10)
        _, item = self._make_delivered_order(customer, product)
        ProductReview.objects.create(
            product=product, customer=customer,
            order_item=item, rating=4,
            title='Good', text='Really good.',
        )
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'average rating')

    def test_non_purchaser_cannot_write_review(self):
        """TC-024: Customer who has not purchased the product cannot access the review form."""
        customer = make_customer()
        other_customer = make_customer(email='other@test.com')
        product = make_product(self.producer, self.cat, name='Exclusive Veg', stock=10)
        _, item = self._make_delivered_order(customer, product)
        self.client.force_login(other_customer)
        response = self.client.get(reverse('products:write_review', args=[item.pk]))
        self.assertIn(response.status_code, [302, 403, 404])

    def test_review_blocked_for_pending_order(self):
        """TC-024: Review page redirects when order is not yet delivered."""
        customer = make_customer()
        product = make_product(self.producer, self.cat, name='Pending Veg', stock=10)
        order = Order.objects.create(
            customer=customer,
            delivery_address='1 Test St',
            delivery_date=(timezone.now() + timedelta(days=3)).date(),
            status='pending',
        )
        po = ProducerOrder.objects.create(
            order=order, producer=self.producer,
            delivery_date=order.delivery_date, status='pending',
        )
        item = OrderItem.objects.create(
            order=order, producer_order=po, product=product,
            producer=self.producer, product_name=product.name,
            price_at_time=product.price, quantity=1,
        )
        self.client.force_login(customer)
        response = self.client.get(reverse('products:write_review', args=[item.pk]))
        self.assertEqual(response.status_code, 302)
