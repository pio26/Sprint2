from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, ProducerProfile, User
from products.models import Category, Product

from .models import Order, OrderItem, Payment


# --- Helpers ---

def make_customer(email='customer@test.com', password='Testpass99!'):
    user = User.objects.create_user(
        email=email, password=password,
        first_name='Alice', last_name='Smith', role='customer'
    )
    CustomerProfile.objects.create(user=user, delivery_address='1 Test St', postcode='BS1 1AA')
    return user


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


def make_product(producer_profile, name='Carrots', price='4.00', stock=10):
    cat, _ = Category.objects.get_or_create(name='Veg', slug='veg')
    return Product.objects.create(
        producer=producer_profile,
        category=cat,
        name=name,
        description=f'Fresh {name}',
        price=price,
        unit='kg',
        stock_quantity=stock,
        availability_status='year_round',
    )


def future_date(days=3):
    return (timezone.now() + timedelta(days=days)).date()


def make_order(customer, producer_profile, product, qty=2, status='pending'):
    price = Decimal(str(product.price))
    subtotal = price * qty
    order = Order.objects.create(
        customer=customer,
        delivery_address='1 Test St',
        delivery_date=future_date(),
        status=status,
    )
    OrderItem.objects.create(
        order=order,
        product=product,
        producer=producer_profile,
        product_name=product.name,
        price_at_time=price,
        quantity=qty,
    )
    Payment.objects.create(
        order=order,
        amount=subtotal,
        commission=(subtotal * Decimal('0.05')).quantize(Decimal('0.01')),
        producer_amount=(subtotal * Decimal('0.95')).quantize(Decimal('0.01')),
    )
    return order


# --- TC-006: Access Control ---

class AccessControlTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer_profile = make_producer()
        self.other_producer_user, self.other_profile = make_producer(email='other@test.com')

    def test_incoming_orders_requires_producer(self):
        """TC-006: Customer cannot access incoming orders (403)."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('orders:incoming_orders'))
        self.assertEqual(response.status_code, 403)

    def test_incoming_orders_requires_login(self):
        """TC-006: Unauthenticated access redirects to login."""
        response = self.client.get(reverse('orders:incoming_orders'))
        self.assertEqual(response.status_code, 302)

    def test_incoming_orders_shows_only_own_orders(self):
        """TC-006: Producer sees only orders containing their products."""
        customer = make_customer(email='c2@test.com')
        product_mine = make_product(self.producer_profile, name='Mine')
        product_other = make_product(self.other_profile, name='Other')

        own_order = make_order(customer, self.producer_profile, product_mine)
        other_order = make_order(customer, self.other_profile, product_other)

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:incoming_orders'))

        self.assertContains(response, own_order.order_number)
        self.assertNotContains(response, other_order.order_number)

    def test_producer_dashboard_blocked_for_customer(self):
        """TC-006: Customer cannot access producer dashboard."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('orders:producer_dashboard'))
        self.assertEqual(response.status_code, 403)

    def test_settlements_blocked_for_customer(self):
        """TC-015: Customer cannot access payment settlements (403)."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('orders:settlements'))
        self.assertEqual(response.status_code, 403)


# --- TC-014: Order Status Transitions ---

class OrderStatusTransitionTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer_profile = make_producer()
        self.product = make_product(self.producer_profile)
        self.other_producer_user, self.other_profile = make_producer(email='other@test.com')
        self.other_product = make_product(self.other_profile, name='Lettuce')

    def _update_status(self, order, new_status):
        return self.client.post(
            reverse('orders:update_status', kwargs={'order_id': order.pk}),
            {'status': new_status},
        )

    def test_valid_transition_pending_to_confirmed(self):
        """TC-014: pending → confirmed is a valid transition."""
        order = make_order(self.customer, self.producer_profile, self.product, status='pending')
        self.client.force_login(self.producer_user)
        self._update_status(order, 'confirmed')
        order.refresh_from_db()
        self.assertEqual(order.status, 'confirmed')

    def test_valid_transition_confirmed_to_ready(self):
        """TC-014: confirmed → ready is a valid transition."""
        order = make_order(self.customer, self.producer_profile, self.product, status='confirmed')
        self.client.force_login(self.producer_user)
        self._update_status(order, 'ready')
        order.refresh_from_db()
        self.assertEqual(order.status, 'ready')

    def test_valid_transition_ready_to_delivered(self):
        """TC-014: ready → delivered is a valid transition."""
        order = make_order(self.customer, self.producer_profile, self.product, status='ready')
        self.client.force_login(self.producer_user)
        self._update_status(order, 'delivered')
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')

    def test_invalid_transition_pending_to_delivered_rejected(self):
        """TC-014: pending → delivered (skipping steps) is rejected."""
        order = make_order(self.customer, self.producer_profile, self.product, status='pending')
        self.client.force_login(self.producer_user)
        self._update_status(order, 'delivered')
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')  # unchanged

    def test_invalid_transition_delivered_to_any_rejected(self):
        """TC-014: delivered is a terminal state — no further transitions."""
        order = make_order(self.customer, self.producer_profile, self.product, status='delivered')
        self.client.force_login(self.producer_user)
        self._update_status(order, 'confirmed')
        order.refresh_from_db()
        self.assertEqual(order.status, 'delivered')  # unchanged

    def test_producer_cannot_update_other_producers_order(self):
        """TC-014: Producer cannot update status of another producer's order."""
        order = make_order(self.customer, self.other_profile, self.other_product, status='pending')
        self.client.force_login(self.producer_user)
        response = self._update_status(order, 'confirmed')
        self.assertEqual(response.status_code, 404)
        order.refresh_from_db()
        self.assertEqual(order.status, 'pending')


# --- TC-015: Payment Settlements ---

class PaymentSettlementsTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer_profile = make_producer()
        self.product = make_product(self.producer_profile, price='10.00')
        self.order = make_order(
            self.customer, self.producer_profile, self.product, qty=2, status='delivered'
        )

    def test_settlements_page_loads_for_producer(self):
        """TC-015: Producer can access the payment settlements page."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:settlements'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)

    def test_settlements_shows_correct_net_payout(self):
        """TC-015: Net payout = subtotal minus 5% commission (£20 → £1.00 commission → £19.00 net)."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:settlements'))
        self.assertContains(response, '19.00')  # net payout: 20 - 1 = 19
        self.assertContains(response, '1.00')   # commission

    def test_settlements_shows_only_own_orders(self):
        """TC-015: Producer only sees settlements for their own products."""
        _, other_profile = make_producer(email='other@test.com')
        other_product = make_product(other_profile, name='Lettuce', price='5.00')
        other_order = make_order(self.customer, other_profile, other_product, status='delivered')

        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:settlements'))

        self.assertContains(response, self.order.order_number)
        self.assertNotContains(response, other_order.order_number)

    def test_producer_dashboard_shows_revenue(self):
        """TC-015: Producer dashboard shows gross revenue from delivered orders."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:producer_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '20.00')  # gross: 10 * 2
