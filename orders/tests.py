from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, Notification, ProducerProfile, User
from products.models import Category, Product

from .models import Order, OrderItem, Payment, ProducerOrder, RecurringOrder, RecurringOrderItem


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


# --- TC-009 extras: producer cannot access other producer's order detail ---

class ProducerOrderDetailAccessTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer = make_producer()
        self.other_producer_user, self.other_producer = make_producer(email='other@test.com')
        own_product = make_product(self.producer)
        other_product = make_product(self.other_producer, name='Other Veg')
        self.own_order = make_order(self.customer, self.producer, own_product, status='pending')
        self.other_order = make_order(self.customer, self.other_producer, other_product, status='pending')

    def test_producer_gets_404_on_other_producers_order_detail(self):
        """TC-009: Producer receives 404 when accessing another producer's order detail."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:order_detail', args=[self.other_order.pk]))
        self.assertEqual(response.status_code, 404)

    def test_producer_can_view_own_order_detail(self):
        """TC-009: Producer can view the detail of their own order."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:order_detail', args=[self.own_order.pk]))
        self.assertEqual(response.status_code, 200)

    def test_orders_sorted_by_delivery_date_on_incoming(self):
        """TC-009: Incoming orders page shows producer's orders (delivery date ordering checked)."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:incoming_orders'))
        self.assertContains(response, self.own_order.order_number)


# --- TC-010 extras: cancelled status transition ---

class CancelledTransitionTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer = make_producer()
        self.product = make_product(self.producer)

    def test_pending_to_cancelled_is_valid(self):
        """TC-010: pending → cancelled is a valid status transition."""
        order = make_order(self.customer, self.producer, self.product, status='pending')
        self.client.force_login(self.producer_user)
        self.client.post(
            reverse('orders:update_status', kwargs={'order_id': order.pk}),
            {'status': 'cancelled'},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_cancelled_is_terminal_state(self):
        """TC-010: cancelled is a terminal state — no further transitions allowed."""
        order = make_order(self.customer, self.producer, self.product, status='cancelled')
        self.client.force_login(self.producer_user)
        self.client.post(
            reverse('orders:update_status', kwargs={'order_id': order.pk}),
            {'status': 'pending'},
        )
        order.refresh_from_db()
        self.assertEqual(order.status, 'cancelled')

    def test_status_history_recorded_on_update(self):
        """TC-010: Status history entry is created when producer updates order status."""
        from .models import OrderStatusHistory
        order = make_order(self.customer, self.producer, self.product, status='pending')
        self.client.force_login(self.producer_user)
        self.client.post(
            reverse('orders:update_status', kwargs={'order_id': order.pk}),
            {'status': 'confirmed', 'note': 'Preparing your order'},
        )
        self.assertTrue(OrderStatusHistory.objects.filter(order=order).exists())


# --- TC-023 extras: above threshold no notification ---

class StockThresholdEdgeCaseTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer = make_producer()

    def _checkout_with_product(self, product, qty):
        from cart.models import Cart, CartItem
        cart, _ = Cart.objects.get_or_create(customer=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=qty)
        self.client.force_login(self.customer)
        self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': (timezone.now() + timedelta(days=3)).date().isoformat(),
            'allergen_acknowledged': 'on',
        })

    def test_above_threshold_does_not_trigger_notification(self):
        """TC-023: Stock above threshold produces no low-stock alert."""
        product = make_product(self.producer, stock=20)
        Product.objects.filter(pk=product.pk).update(low_stock_threshold=5)
        product.refresh_from_db()
        self._checkout_with_product(product, qty=2)
        self.assertFalse(
            Notification.objects.filter(user=self.producer_user, category='stock').exists()
        )

    def test_stock_at_zero_hides_product(self):
        """TC-023: Product with zero stock is not visible to customers."""
        product = make_product(self.producer, stock=1)
        Product.objects.filter(pk=product.pk).update(low_stock_threshold=0)
        product.refresh_from_db()
        self._checkout_with_product(product, qty=1)
        product.refresh_from_db()
        self.assertEqual(product.stock_quantity, 0)
        response = self.client.get(reverse('products:product_list'))
        self.assertNotContains(response, product.name)


# --- TC-025 extras: commission report access control and figures ---

class CommissionReportAccessTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer = make_producer()
        self.admin = User.objects.create_superuser(
            email='admin@test.com', password='Adminpass99!',
            first_name='Admin', last_name='User',
        )

    def test_non_admin_customer_blocked_from_commission_report(self):
        """TC-025: A regular customer cannot access the admin commission report."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('orders:commission_report'))
        self.assertIn(response.status_code, [302, 403])

    def test_producer_blocked_from_commission_report(self):
        """TC-025: A producer cannot access the admin commission report."""
        self.client.force_login(self.producer_user)
        response = self.client.get(reverse('orders:commission_report'))
        self.assertIn(response.status_code, [302, 403])

    def test_admin_can_access_commission_report(self):
        """TC-025: Admin user can access the commission report."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('orders:commission_report'))
        self.assertEqual(response.status_code, 200)

    def test_commission_report_csv_only_for_admin(self):
        """TC-025: Commission CSV export is blocked for non-admin users."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('orders:commission_report_csv'))
        self.assertIn(response.status_code, [302, 403])

    def test_commission_report_calculates_5_percent(self):
        """TC-025: Commission report shows correct 5% figure for a £100 order."""
        order = Order.objects.create(
            customer=self.customer,
            delivery_address='1 Test St',
            delivery_date=(timezone.now() + timedelta(days=3)).date(),
            status='delivered',
        )
        po = ProducerOrder.objects.create(
            order=order, producer=self.producer,
            delivery_date=order.delivery_date, status='delivered',
        )
        product = make_product(self.producer, price='100.00')
        OrderItem.objects.create(
            order=order, producer_order=po, product=product,
            producer=self.producer, product_name=product.name,
            price_at_time=Decimal('100.00'), quantity=1,
        )
        Payment.objects.create(
            order=order,
            amount=Decimal('100.00'),
            commission=Decimal('5.00'),
            producer_amount=Decimal('95.00'),
            status='completed',
        )
        self.client.force_login(self.admin)
        response = self.client.get(reverse('orders:commission_report'))
        self.assertContains(response, '5.00')
        self.assertContains(response, '95.00')


# --- TC-012: Weekly settlement management command ---

class WeeklySettlementCommandTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer_user, self.producer = make_producer()
        product = make_product(self.producer, price='20.00')
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='1 Test St',
            delivery_date=timezone.now().date(),
            status='delivered',
        )
        po = ProducerOrder.objects.create(
            order=self.order, producer=self.producer,
            delivery_date=self.order.delivery_date, status='delivered',
        )
        OrderItem.objects.create(
            order=self.order, producer_order=po, product=product,
            producer=self.producer, product_name=product.name,
            price_at_time=Decimal('20.00'), quantity=1,
        )
        self.payment = Payment.objects.create(
            order=self.order,
            amount=Decimal('20.00'),
            commission=Decimal('1.00'),
            producer_amount=Decimal('19.00'),
            status='pending',
        )

    def test_settlement_command_marks_payments_completed(self):
        """TC-012: process_weekly_settlements marks pending delivered-order payments as completed."""
        self.assertEqual(self.payment.status, 'pending')
        call_command('process_weekly_settlements', stdout=StringIO())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'completed')

    def test_settlement_command_dry_run_does_not_update(self):
        """TC-012: --dry-run flag previews without updating payment status."""
        call_command('process_weekly_settlements', '--dry-run', stdout=StringIO())
        self.payment.refresh_from_db()
        self.assertEqual(self.payment.status, 'pending')

    def test_settlement_command_skips_non_delivered_orders(self):
        """TC-012: Pending-status orders are not included in settlements."""
        pending_order = Order.objects.create(
            customer=self.customer,
            delivery_address='1 Test St',
            delivery_date=timezone.now().date(),
            status='pending',
        )
        pending_payment = Payment.objects.create(
            order=pending_order,
            amount=Decimal('10.00'),
            commission=Decimal('0.50'),
            producer_amount=Decimal('9.50'),
            status='pending',
        )
        call_command('process_weekly_settlements', stdout=StringIO())
        pending_payment.refresh_from_db()
        self.assertEqual(pending_payment.status, 'pending')


# --- TC-018: generate_recurring_orders management command ---

class RecurringOrderCommandTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        User.objects.filter(pk=self.customer.pk).update(role='restaurant')
        self.customer.refresh_from_db()
        self.customer.customer_profile.delivery_address = '1 Test St'
        self.customer.customer_profile.save()
        self.producer_user, self.producer = make_producer()
        self.product = make_product(self.producer, stock=50)

    def _make_recurring(self, days_offset=0):
        due_date = (timezone.now() - timedelta(days=days_offset)).date()
        recurring = RecurringOrder.objects.create(
            customer=self.customer,
            name='Test Weekly Order',
            frequency='weekly',
            delivery_weekday=2,
            next_delivery_date=due_date,
            is_active=True,
        )
        RecurringOrderItem.objects.create(
            recurring_order=recurring,
            product=self.product,
            producer=self.producer,
            quantity=2,
        )
        return recurring

    def test_generate_recurring_creates_order_and_payment(self):
        """TC-018: generate_recurring_orders creates an Order and Payment for a due template."""
        self._make_recurring(days_offset=1)
        call_command('generate_recurring_orders', stdout=StringIO())
        self.assertTrue(Order.objects.filter(customer=self.customer).exists())
        order = Order.objects.get(customer=self.customer)
        self.assertTrue(Payment.objects.filter(order=order).exists())

    def test_generate_recurring_advances_next_delivery_date(self):
        """TC-018: Next delivery date is advanced by one week after generation."""
        recurring = self._make_recurring(days_offset=1)
        original_date = recurring.next_delivery_date
        call_command('generate_recurring_orders', stdout=StringIO())
        recurring.refresh_from_db()
        self.assertEqual(recurring.next_delivery_date, original_date + timedelta(weeks=1))

    def test_generate_recurring_notifies_producer(self):
        """TC-018: Producer receives a notification for each generated recurring order."""
        self._make_recurring(days_offset=1)
        call_command('generate_recurring_orders', stdout=StringIO())
        self.assertTrue(
            Notification.objects.filter(user=self.producer_user, category='order').exists()
        )

    def test_generate_recurring_dry_run_no_order_created(self):
        """TC-018: --dry-run flag does not create any orders."""
        self._make_recurring(days_offset=1)
        call_command('generate_recurring_orders', '--dry-run', stdout=StringIO())
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())

    def test_generate_recurring_skips_future_templates(self):
        """TC-018: Templates with future next_delivery_date are not processed."""
        self._make_recurring(days_offset=-3)  # due in 3 days
        call_command('generate_recurring_orders', stdout=StringIO())
        self.assertFalse(Order.objects.filter(customer=self.customer).exists())


# --- TC-015: Allergen acknowledgement gate at checkout ---

class AllergenAcknowledgementGateTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, self.producer = make_producer()
        product = make_product(self.producer)
        from cart.models import Cart, CartItem
        cart = Cart.objects.create(customer=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=1)

    def test_checkout_blocked_without_allergen_acknowledgement(self):
        """TC-015: Checkout form is invalid and order not created when allergen checkbox unchecked."""
        self.client.force_login(self.customer)
        response = self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': (timezone.now() + timedelta(days=3)).date().isoformat(),
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 0)

    def test_checkout_shows_allergen_warning_section(self):
        """TC-015: Checkout page displays allergen information panel."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('cart:checkout'))
        self.assertContains(response, 'Allergen Information')

    def test_checkout_proceeds_with_acknowledgement(self):
        """TC-015: Checkout succeeds when allergen checkbox is checked."""
        self.client.force_login(self.customer)
        response = self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': (timezone.now() + timedelta(days=3)).date().isoformat(),
            'allergen_acknowledged': 'on',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Order.objects.filter(customer=self.customer).exists())

    def test_allergen_error_message_shown(self):
        """TC-015: Validation error message appears when allergen checkbox is not checked."""
        self.client.force_login(self.customer)
        response = self.client.post(reverse('cart:checkout'), {
            'delivery_address': '1 Test St',
            'delivery_date': (timezone.now() + timedelta(days=3)).date().isoformat(),
        })
        self.assertContains(response, 'allergen')
