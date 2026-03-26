from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomerProfile, ProducerProfile, User
from .models import Category, Product


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
