from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, LoginAttempt, Notification, ProducerProfile, User
from cart.models import Cart, CartItem
from orders.models import Order, OrderItem, OrderStatusHistory, Payment, ProducerOrder, RecurringOrder
from products.models import Category, FarmStory, Product, ProductReview, Recipe


def future_date(days=3):
    return (timezone.now() + timedelta(days=days)).date()


def make_customer(email='customer@test.com', role='customer', account_type='individual', postcode='BS1 5JG'):
    user = User.objects.create_user(
        email=email,
        password='Testpass99!',
        first_name='Alice',
        last_name='Smith',
        role=role,
    )
    CustomerProfile.objects.create(
        user=user,
        account_type=account_type,
        organization_name='St Marys School' if role == 'community' else '',
        organization_type='Education' if role == 'community' else '',
        delivery_address='1 Test St, Bristol',
        postcode=postcode,
    )
    return user


def make_producer(email='producer@test.com', business='Test Farm', postcode='BS2 2BB'):
    user = User.objects.create_user(
        email=email,
        password='Testpass99!',
        first_name='Bob',
        last_name='Jones',
        role='producer',
        phone='01179 123456',
    )
    profile = ProducerProfile.objects.create(
        user=user,
        business_name=business,
        business_address='Farm Lane',
        postcode=postcode,
    )
    return user, profile


def make_product(producer, name='Carrots', price='4.00', stock=20, **kwargs):
    category = kwargs.pop('category', None)
    if category is None:
        category, _ = Category.objects.get_or_create(name='Vegetables', slug='vegetables')
    description = kwargs.pop('description', f'Fresh {name}')
    return Product.objects.create(
        producer=producer,
        category=category,
        name=name,
        description=description,
        price=price,
        unit='kg',
        stock_quantity=stock,
        availability_status=kwargs.pop('availability_status', 'year_round'),
        allergens=kwargs.pop('allergens', []),
        is_organic=kwargs.pop('is_organic', False),
        low_stock_threshold=kwargs.pop('low_stock_threshold', 5),
        **kwargs,
    )


def make_order(customer, product, qty=2, status='pending'):
    order = Order.objects.create(
        customer=customer,
        delivery_address='1 Test St, Bristol',
        delivery_date=future_date(),
        status=status,
    )
    producer_order = ProducerOrder.objects.create(
        order=order,
        producer=product.producer,
        delivery_date=order.delivery_date,
        status=status,
    )
    item = OrderItem.objects.create(
        order=order,
        producer_order=producer_order,
        product=product,
        producer=product.producer,
        product_name=product.name,
        price_at_time=product.price,
        quantity=qty,
    )
    Payment.objects.create(
        order=order,
        amount=order.total,
        commission=order.commission_amount,
        producer_amount=order.producer_payment,
        status='completed',
    )
    return order, producer_order, item


class AssessmentTestCaseCoverage(TestCase):
    def test_tc001_producer_registration_complete(self):
        """TC-001: producer registration stores secure account, business profile and permissions."""
        response = self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@farm.com',
            'phone': '01179 123456',
            'password1': 'Farmpass99!',
            'password2': 'Farmpass99!',
            'business_name': 'Bristol Valley Farm',
            'business_address': 'Farm Lane, Bristol',
            'postcode': 'BS1 4DJ',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='jane@farm.com')
        self.assertEqual(user.role, 'producer')
        self.assertTrue(user.check_password('Farmpass99!'))
        self.assertNotEqual(user.password, 'Farmpass99!')
        self.assertEqual(user.producer_profile.business_name, 'Bristol Valley Farm')

    def test_tc002_customer_registration_complete(self):
        """TC-002: customer registration stores personal and delivery details."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Robert',
            'last_name': 'Johnson',
            'email': 'robert@example.com',
            'phone': '07700 900123',
            'password1': 'Customer99!',
            'password2': 'Customer99!',
            'delivery_address': '45 Park Street, Bristol',
            'postcode': 'BS1 5JG',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='robert@example.com')
        self.assertEqual(user.role, 'customer')
        self.assertEqual(user.customer_profile.postcode, 'BS1 5JG')

    def test_tc003_product_listing_complete(self):
        """TC-003: producer can list a product with category, stock, season, allergens and organic data."""
        user, producer = make_producer()
        category = Category.objects.create(name='Dairy & Eggs', slug='dairy-eggs')
        self.client.force_login(user)
        response = self.client.post(reverse('products:product_create'), {
            'name': 'Organic Free Range Eggs',
            'category': category.pk,
            'description': 'Fresh organic eggs from free-range hens, collected daily',
            'price': '3.50',
            'unit': 'Dozen',
            'availability_status': 'in_season',
            'stock_quantity': 50,
            'low_stock_threshold': 10,
            'allergens': ['Eggs'],
            'is_organic': 'on',
            'harvest_date': future_date(0).isoformat(),
            'allergens_declared': 'on',
        })
        product = Product.objects.get(name='Organic Free Range Eggs')
        self.assertRedirects(response, reverse('products:product_detail', args=[product.pk]))
        self.assertEqual(product.producer, producer)
        self.assertIn('Eggs', product.allergens)
        self.assertTrue(product.is_organic)

    def test_tc004_category_browsing_complete(self):
        """TC-004: category browsing shows only available products in that category."""
        _, producer = make_producer()
        veg = Category.objects.create(name='Vegetables', slug='veg')
        dairy = Category.objects.create(name='Dairy', slug='dairy')
        make_product(producer, name='Carrots', category=veg)
        make_product(producer, name='Milk', category=dairy)
        response = self.client.get(reverse('products:products_by_category', args=['veg']))
        self.assertContains(response, 'Carrots')
        self.assertNotContains(response, 'Milk')

    def test_tc005_search_complete(self):
        """TC-005: search matches name, description and handles empty results."""
        _, producer = make_producer(business='Hillside Dairy')
        make_product(producer, name='Organic Tomatoes', description='Red salad tomatoes')
        make_product(producer, name='Fresh Milk', description='Whole dairy milk')
        response = self.client.get(reverse('products:product_search') + '?q=tomato')
        self.assertContains(response, 'Organic Tomatoes')
        self.assertNotContains(response, 'Fresh Milk')
        response = self.client.get(reverse('products:product_search') + '?q=zzzzzz')
        self.assertContains(response, 'No products found')

    def test_tc006_cart_complete(self):
        """TC-006: cart adds multiple products, updates quantity, removes items and recalculates totals."""
        customer = make_customer()
        _, producer = make_producer()
        carrots = make_product(producer, name='Organic Carrots', price='2.00')
        milk = make_product(producer, name='Fresh Milk', price='1.50')
        self.client.force_login(customer)
        self.client.post(reverse('cart:add_to_cart', args=[carrots.pk]), {'quantity': 2})
        self.client.post(reverse('cart:add_to_cart', args=[milk.pk]), {'quantity': 3})
        cart = customer.cart
        item = cart.items.get(product=carrots)
        self.client.post(reverse('cart:update_cart', args=[item.pk]), {'quantity': 3})
        self.assertEqual(cart.get_total(), Decimal('10.50'))
        self.client.post(reverse('cart:remove_from_cart', args=[cart.items.get(product=milk).pk]))
        self.assertEqual(cart.items.count(), 1)

    def test_tc007_single_producer_checkout_complete(self):
        """TC-007: single-producer checkout records order, payment, commission and producer notification."""
        customer = make_customer()
        _, producer = make_producer()
        product = make_product(producer, price='10.00')
        cart = Cart.objects.create(customer=customer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        self.client.force_login(customer)
        response = self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': future_date().isoformat(),
            'payment_method': 'mock_card',
            'test_payment_reference': 'TEST-123',
            'allergen_acknowledged': 'on',
        })
        self.assertEqual(response.status_code, 302)
        order = Order.objects.get(customer=customer)
        self.assertEqual(order.status, 'pending')
        self.assertEqual(order.producer_orders.count(), 1)
        self.assertEqual(order.payment.commission, Decimal('1.00'))
        self.assertTrue(Notification.objects.filter(user=producer.user, category='order').exists())

    def test_tc008_multi_vendor_checkout_complete(self):
        """TC-008: multi-vendor checkout creates one customer order with per-producer sub-orders and split payouts."""
        customer = make_customer()
        _, p1 = make_producer(email='p1@test.com', business='Bristol Valley Farm')
        _, p2 = make_producer(email='p2@test.com', business='Hillside Dairy')
        product1 = make_product(p1, name='Carrots', price='80.00')
        product2 = make_product(p2, name='Milk', price='70.00')
        cart = Cart.objects.create(customer=customer)
        CartItem.objects.create(cart=cart, product=product1, quantity=1)
        CartItem.objects.create(cart=cart, product=product2, quantity=1)
        self.client.force_login(customer)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': future_date().isoformat(),
            'payment_method': 'mock_card',
            'allergen_acknowledged': 'on',
        })
        order = Order.objects.get(customer=customer)
        self.assertEqual(order.producer_orders.count(), 2)
        self.assertEqual(order.payment.commission, Decimal('7.50'))
        self.assertEqual(order.producer_orders.get(producer=p1).producer_payment, Decimal('76.00'))
        self.assertEqual(order.producer_orders.get(producer=p2).producer_payment, Decimal('66.50'))

    def test_tc009_producer_incoming_orders_complete(self):
        """TC-009: producer sees only own incoming orders with customer and delivery details."""
        customer = make_customer()
        producer_user, producer = make_producer()
        _, other = make_producer(email='other@test.com', business='Other Farm')
        own_order, _, _ = make_order(customer, make_product(producer, name='Mine'))
        other_order, _, _ = make_order(customer, make_product(other, name='Other'))
        self.client.force_login(producer_user)
        response = self.client.get(reverse('orders:incoming_orders'))
        self.assertContains(response, own_order.order_number)
        self.assertNotContains(response, other_order.order_number)
        response = self.client.get(reverse('orders:order_detail', args=[own_order.pk]))
        self.assertContains(response, '1 Test St')

    def test_tc010_order_status_updates_complete(self):
        """TC-010: status updates follow transitions, store audit history and notify customer."""
        customer = make_customer()
        producer_user, producer = make_producer()
        order, producer_order, _ = make_order(customer, make_product(producer), status='pending')
        self.client.force_login(producer_user)
        self.client.post(reverse('orders:update_status', args=[order.pk]), {
            'status': 'confirmed',
            'note': 'Products will be prepared by delivery date',
        })
        producer_order.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(producer_order.status, 'confirmed')
        self.assertEqual(order.status, 'confirmed')
        self.assertTrue(OrderStatusHistory.objects.filter(order=order, note__icontains='prepared').exists())
        self.assertTrue(Notification.objects.filter(user=customer, category='order').exists())

    def test_tc011_inventory_updates_complete(self):
        """TC-011: producers update only their stock and availability changes customer visibility."""
        producer_user, producer = make_producer()
        product = make_product(producer, stock=20)
        self.client.force_login(producer_user)
        self.client.post(reverse('products:stock_update', args=[product.pk]), {'stock_quantity': 0})
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
        response = self.client.get(reverse('products:product_list'))
        self.assertFalse(any(row.pk == product.pk for row in response.context['page_obj'].object_list))

    def test_tc012_payment_settlements_complete(self):
        """TC-012: delivered orders appear in producer settlement summaries and CSV exports."""
        customer = make_customer()
        producer_user, producer = make_producer()
        order, _, _ = make_order(customer, make_product(producer, price='20.00'), qty=1, status='delivered')
        self.client.force_login(producer_user)
        response = self.client.get(reverse('orders:settlements'))
        self.assertContains(response, order.order_number)
        self.assertContains(response, '19.00')
        response = self.client.get(reverse('orders:settlements_csv'))
        self.assertContains(response, order.order_number)

    def test_tc013_food_miles_complete(self):
        """TC-013: product and cart views display postcode-based food miles."""
        customer = make_customer(postcode='BS1 5JG')
        _, producer = make_producer(postcode='BS2 2BB')
        product = make_product(producer)
        self.client.force_login(customer)
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'food miles')
        Cart.objects.create(customer=customer)
        self.client.post(reverse('cart:add_to_cart', args=[product.pk]), {'quantity': 2})
        response = self.client.get(reverse('cart:cart_detail'))
        self.assertContains(response, 'Food miles')

    def test_tc014_organic_filter_complete(self):
        """TC-014: organic filter shows certified products and excludes non-certified products."""
        _, producer = make_producer()
        make_product(producer, name='Organic Apples', is_organic=True)
        make_product(producer, name='Standard Apples', is_organic=False)
        response = self.client.get(reverse('products:product_list') + '?organic=1')
        self.assertContains(response, 'Organic Apples')
        self.assertNotContains(response, 'Standard Apples')

    def test_tc015_allergen_warnings_complete(self):
        """TC-015: allergen information displays clearly and allergen exclusion filters work."""
        _, producer = make_producer()
        cheese = make_product(producer, name='Cheddar Cheese', allergens=['Milk'])
        make_product(producer, name='Fresh Apples', allergens=[])
        response = self.client.get(reverse('products:product_detail', args=[cheese.pk]))
        self.assertContains(response, 'Milk')
        response = self.client.get(reverse('products:product_search') + '?allergen_exclude=Milk')
        self.assertNotContains(response, 'Cheddar Cheese')
        self.assertContains(response, 'Fresh Apples')

    def test_tc016_seasonal_availability_complete(self):
        """TC-016: seasonal settings show badges, dates and block out-of-season and not-yet-in-season products."""
        _, producer = make_producer()
        # Season already started (past) and ends in the future — available now
        strawberries = make_product(
            producer,
            name='Strawberries',
            availability_status='in_season',
            season_start=future_date(-30),
            season_end=future_date(60),
        )
        # Season hasn't started yet — should be unavailable
        early_crop = make_product(
            producer,
            name='Early Crop',
            availability_status='in_season',
            season_start=future_date(30),
            season_end=future_date(90),
        )
        make_product(producer, name='Out Fruit', availability_status='out_of_season')
        response = self.client.get(reverse('products:product_detail', args=[strawberries.pk]))
        self.assertContains(response, 'In Season')
        response = self.client.get(reverse('products:product_list'))
        self.assertContains(response, 'Strawberries')
        self.assertNotContains(response, 'Out Fruit')
        self.assertNotContains(response, 'Early Crop')

    def test_tc017_community_bulk_order_complete(self):
        """TC-017: community groups register distinctly and can place large multi-producer orders."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Sam',
            'last_name': 'Caterer',
            'email': 'catering@stmarys-school.org.uk',
            'password1': 'Schoolpass99!',
            'password2': 'Schoolpass99!',
            'account_type': 'community_group',
            'organization_name': 'St Marys School',
            'organization_type': 'Education',
            'delivery_address': 'School Kitchen, Bristol',
            'postcode': 'BS3 3CC',
        })
        self.assertRedirects(response, reverse('home'))
        community = User.objects.get(email='catering@stmarys-school.org.uk')
        self.assertEqual(community.role, 'community')
        _, p1 = make_producer(email='farm1@test.com')
        _, p2 = make_producer(email='farm2@test.com')
        potato = make_product(p1, name='Potatoes', stock=100)
        milk = make_product(p2, name='Milk', stock=100)
        cart = Cart.objects.create(customer=community)
        CartItem.objects.create(cart=cart, product=potato, quantity=50)
        CartItem.objects.create(cart=cart, product=milk, quantity=30)
        self.client.force_login(community)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': 'School Kitchen, Bristol',
            'delivery_date': future_date().isoformat(),
            'special_instructions': 'Deliver to kitchen entrance',
            'allergen_acknowledged': 'on',
        })
        order = Order.objects.get(customer=community)
        self.assertEqual(order.producer_orders.count(), 2)
        self.assertIn('kitchen entrance', order.special_instructions)

    def test_tc018_restaurant_recurring_orders_complete(self):
        """TC-018: restaurant checkout can save and manage a recurring order template."""
        restaurant = make_customer(role='restaurant', account_type='restaurant', email='chef@clifton.test')
        _, producer = make_producer()
        product = make_product(producer, stock=30)
        cart = Cart.objects.create(customer=restaurant)
        CartItem.objects.create(cart=cart, product=product, quantity=4)
        self.client.force_login(restaurant)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': 'Restaurant Kitchen',
            'delivery_date': future_date().isoformat(),
            'make_recurring': 'on',
            'recurrence_frequency': 'weekly',
            'recurring_delivery_weekday': 2,
            'allergen_acknowledged': 'on',
        })
        recurring = RecurringOrder.objects.get(customer=restaurant)
        self.assertEqual(recurring.items.get(product=product).quantity, 4)
        self.client.post(reverse('cart:recurring_order_detail', args=[recurring.pk]), {
            'is_active': 'on',
            f'quantity_{recurring.items.get().pk}': 6,
        })
        self.assertEqual(recurring.items.get().quantity, 6)

    def test_tc019_surplus_deals_complete(self):
        """TC-019: producers publish surplus discounts and checkout uses the discounted price."""
        producer_user, producer = make_producer()
        customer = make_customer()
        product = make_product(producer, name='Lettuce', price='10.00')
        self.client.force_login(producer_user)
        self.client.post(reverse('products:mark_surplus', args=[product.pk]), {
            'discount_percent': 30,
            'expires_at': (timezone.now() + timedelta(hours=48)).strftime('%Y-%m-%dT%H:%M'),
            'note': 'Perfect condition, must sell quickly',
        })
        product.refresh_from_db()
        self.assertEqual(product.effective_price, Decimal('7.00'))
        self.client.force_login(customer)
        cart = Cart.objects.create(customer=customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': future_date().isoformat(),
            'allergen_acknowledged': 'on',
        })
        self.assertEqual(OrderItem.objects.get(order__customer=customer).price_at_time, Decimal('7.00'))

    def test_tc020_recipes_and_farm_stories_complete(self):
        """TC-020: producers publish recipes/stories and linked recipes appear on product pages."""
        producer_user, producer = make_producer()
        product = make_product(producer, name='Carrots')
        self.client.force_login(producer_user)
        self.client.post(reverse('products:recipe_create'), {
            'title': 'Roasted Root Vegetable Medley',
            'description': 'Seasonal recipe',
            'ingredients': 'Carrots',
            'instructions': 'Roast until tender',
            'seasonal_tag': 'Autumn/Winter',
            'products': [product.pk],
        })
        self.client.post(reverse('products:story_create'), {
            'title': 'Harvest Season',
            'body': 'A story from the farm.',
            'seasonal_tag': 'Autumn',
        })
        self.assertTrue(Recipe.objects.filter(products=product).exists())
        self.assertTrue(FarmStory.objects.filter(producer=producer).exists())
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Roasted Root Vegetable Medley')
        response = self.client.get(reverse('products:producer_profile', args=[producer.pk]))
        self.assertContains(response, 'Harvest Season')

    def test_tc021_order_history_reorder_and_receipt_complete(self):
        """TC-021: customers can filter history, view details, reorder and download receipts."""
        customer = make_customer()
        _, producer = make_producer()
        product = make_product(producer, stock=20)
        order, _, _ = make_order(customer, product, status='delivered')
        self.client.force_login(customer)
        response = self.client.get(reverse('cart:order_history') + f'?producer={producer.business_name}')
        self.assertContains(response, order.order_number)
        self.client.post(reverse('cart:reorder', args=[order.pk]))
        self.assertTrue(CartItem.objects.filter(cart__customer=customer, product=product).exists())
        response = self.client.get(reverse('cart:order_receipt', args=[order.pk]))
        self.assertContains(response, order.order_number)

    def test_tc022_security_complete(self):
        """TC-022: authentication uses generic errors, logs failures, rate limits and enforces roles."""
        customer = make_customer()
        _, producer = make_producer()
        for _ in range(5):
            self.client.post(reverse('accounts:login'), {'email': customer.email, 'password': 'wrong'})
        self.assertEqual(LoginAttempt.objects.filter(email=customer.email, success=False).count(), 5)
        response = self.client.post(reverse('accounts:login'), {'email': customer.email, 'password': 'wrong'})
        self.assertContains(response, 'Too many failed login attempts')
        self.client.force_login(customer)
        response = self.client.get(reverse('products:product_create'))
        self.assertEqual(response.status_code, 403)
        self.client.force_login(producer.user)
        response = self.client.get(reverse('products:product_create'))
        self.assertEqual(response.status_code, 200)

    def test_tc023_low_stock_notifications_complete(self):
        """TC-023: checkout decrements stock, creates low-stock alerts and replenishment clears them."""
        customer = make_customer()
        producer_user, producer = make_producer()
        product = make_product(producer, stock=4, low_stock_threshold=3)
        cart = Cart.objects.create(customer=customer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        self.client.force_login(customer)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': future_date().isoformat(),
            'allergen_acknowledged': 'on',
        })
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 2)
        self.assertTrue(Notification.objects.filter(user=producer_user, category='stock', is_read=False).exists())
        self.client.force_login(producer_user)
        self.client.post(reverse('products:stock_update', args=[product.pk]), {'stock_quantity': 10})
        self.assertFalse(Notification.objects.filter(user=producer_user, category='stock', is_read=False).exists())

    def test_tc024_reviews_complete(self):
        """TC-024: reviews require delivered verified purchases and prevent duplicates."""
        customer = make_customer()
        _, producer = make_producer()
        product = make_product(producer)
        order, _, item = make_order(customer, product, status='delivered')
        self.client.force_login(customer)
        response = self.client.post(reverse('products:write_review', args=[item.pk]), {
            'rating': 5,
            'title': 'Excellent quality and flavour',
            'text': 'Fresh and flavourful.',
        })
        self.assertRedirects(response, reverse('products:product_detail', args=[product.pk]))
        self.assertEqual(ProductReview.objects.get(product=product).rating, 5)
        response = self.client.post(reverse('products:write_review', args=[item.pk]), {
            'rating': 4,
            'title': 'Again',
            'text': 'Duplicate',
        })
        self.assertEqual(ProductReview.objects.filter(product=product).count(), 1)
        pending_order, _, pending_item = make_order(customer, make_product(producer, name='Pending Item'), status='pending')
        response = self.client.get(reverse('products:write_review', args=[pending_item.pk]))
        self.assertRedirects(response, reverse('cart:order_detail', args=[pending_order.pk]))

    def test_tc024_product_page_shows_review_button_for_eligible_customer(self):
        """TC-024: product page surfaces a review action for delivered verified purchases."""
        customer = make_customer()
        _, producer = make_producer()
        product = make_product(producer)
        make_order(customer, product, status='delivered')
        self.client.force_login(customer)
        response = self.client.get(reverse('products:product_detail', args=[product.pk]))
        self.assertContains(response, 'Write Review')

    def test_tc025_admin_commission_reporting_complete(self):
        """TC-025: admins can view and export commission reports with multi-producer splits."""
        admin = User.objects.create_superuser(
            email='admin@test.com',
            password='Adminpass99!',
            first_name='Admin',
            last_name='User',
        )
        customer = make_customer()
        _, p1 = make_producer(email='p1@test.com', business='Producer One')
        _, p2 = make_producer(email='p2@test.com', business='Producer Two')
        order = Order.objects.create(
            customer=customer,
            delivery_address='1 Test St',
            delivery_date=future_date(),
            status='delivered',
        )
        po1 = ProducerOrder.objects.create(order=order, producer=p1, delivery_date=order.delivery_date, status='delivered')
        po2 = ProducerOrder.objects.create(order=order, producer=p2, delivery_date=order.delivery_date, status='delivered')
        OrderItem.objects.create(order=order, producer_order=po1, product=make_product(p1, price='80.00'), producer=p1, product_name='P1', price_at_time='80.00', quantity=1)
        OrderItem.objects.create(order=order, producer_order=po2, product=make_product(p2, price='70.00'), producer=p2, product_name='P2', price_at_time='70.00', quantity=1)
        Payment.objects.create(order=order, amount=order.total, commission=order.commission_amount, producer_amount=order.producer_payment, status='completed')
        self.client.force_login(admin)
        response = self.client.get(reverse('orders:commission_report'))
        self.assertContains(response, '7.50')
        self.assertContains(response, '76.00')
        self.assertContains(response, '66.50')
        response = self.client.get(reverse('orders:commission_report_csv'))
        self.assertContains(response, order.order_number)

    def test_tc025_modern_admin_dashboard_renders(self):
        """TC-025: admin dashboard provides a styled operations console with quick reporting links."""
        admin = User.objects.create_superuser(
            email='ops-admin@test.com',
            password='Adminpass99!',
            first_name='Ops',
            last_name='Admin',
        )
        self.client.force_login(admin)
        response = self.client.get('/admin/')
        self.assertContains(response, 'Marketplace Administration')
        self.assertContains(response, 'Commission Report')
        self.assertContains(response, 'admin-modern.css')
