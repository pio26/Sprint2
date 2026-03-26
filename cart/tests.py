from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomerProfile, ProducerProfile, User
from orders.models import Order, OrderItem, Payment
from products.models import Category, Product

from .models import Cart, CartItem


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


def make_product(producer_profile, name='Tomatoes', stock=10,
                 availability='year_round'):
    cat, _ = Category.objects.get_or_create(name='Veg', slug='veg')
    return Product.objects.create(
        producer=producer_profile,
        category=cat,
        name=name,
        description=f'Fresh {name}',
        price='2.50',
        unit='kg',
        stock_quantity=stock,
        availability_status=availability,
    )


def future_date(days=3):
    return (timezone.now() + timedelta(days=days)).date().isoformat()


# --- TC-007: Add to Cart ---

class AddToCartTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, self.producer_profile = make_producer()
        self.product = make_product(self.producer_profile)
        self.url = reverse('cart:add_to_cart', kwargs={'product_id': self.product.pk})

    def test_add_to_cart_success(self):
        """TC-007: Customer can add an available product to cart."""
        self.client.force_login(self.customer)
        self.client.post(self.url, {'quantity': '1'})
        self.assertEqual(CartItem.objects.filter(cart__customer=self.customer).count(), 1)

    def test_add_to_cart_increments_existing(self):
        """TC-007: Adding the same product twice increments quantity."""
        self.client.force_login(self.customer)
        self.client.post(self.url, {'quantity': '2'})
        self.client.post(self.url, {'quantity': '3'})
        item = CartItem.objects.get(cart__customer=self.customer, product=self.product)
        # 2 + 3 = 5, within stock of 10
        self.assertEqual(item.quantity, 5)

    def test_add_to_cart_capped_at_stock(self):
        """TC-007: Quantity cannot exceed available stock."""
        self.client.force_login(self.customer)
        self.client.post(self.url, {'quantity': '8'})
        self.client.post(self.url, {'quantity': '5'})  # 8+5=13 > 10, should cap at 10
        item = CartItem.objects.get(cart__customer=self.customer, product=self.product)
        self.assertEqual(item.quantity, 10)

    def test_add_to_cart_blocked_for_producer(self):
        """TC-007: Producers cannot add to cart (403)."""
        producer_user, _ = make_producer(email='prod2@test.com')
        self.client.force_login(producer_user)
        response = self.client.post(self.url, {'quantity': '1'})
        self.assertEqual(response.status_code, 403)

    def test_add_to_cart_blocked_for_out_of_stock(self):
        """TC-007: Out-of-stock product cannot be added to cart."""
        self.client.force_login(self.customer)
        oos_product = make_product(self.producer_profile, name='Lettuce', stock=0)
        url = reverse('cart:add_to_cart', kwargs={'product_id': oos_product.pk})
        self.client.post(url, {'quantity': '1'})
        self.assertFalse(CartItem.objects.filter(cart__customer=self.customer, product=oos_product).exists())

    def test_add_to_cart_blocked_for_out_of_season(self):
        """TC-007: Out-of-season product cannot be added to cart."""
        self.client.force_login(self.customer)
        oos = make_product(self.producer_profile, name='Parsnip', availability='out_of_season')
        url = reverse('cart:add_to_cart', kwargs={'product_id': oos.pk})
        self.client.post(url, {'quantity': '1'})
        self.assertFalse(CartItem.objects.filter(cart__customer=self.customer, product=oos).exists())


# --- TC-008: Update Cart ---

class UpdateCartTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, producer_profile = make_producer()
        product = make_product(producer_profile)
        cart = Cart.objects.create(customer=self.customer)
        self.item = CartItem.objects.create(cart=cart, product=product, quantity=2)
        self.url = reverse('cart:update_cart', kwargs={'item_id': self.item.pk})

    def test_update_quantity_success(self):
        """TC-008: Customer can update item quantity."""
        self.client.force_login(self.customer)
        self.client.post(self.url, {'quantity': '5'})
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity, 5)

    def test_update_quantity_zero_removes_item(self):
        """TC-008: Setting quantity to 0 removes the cart item."""
        self.client.force_login(self.customer)
        self.client.post(self.url, {'quantity': '0'})
        self.assertFalse(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_update_cart_blocked_for_other_customer(self):
        """TC-008: Cannot update another customer's cart item."""
        other = make_customer(email='other@test.com')
        self.client.force_login(other)
        response = self.client.post(self.url, {'quantity': '9'})
        self.assertEqual(response.status_code, 404)


# --- TC-009: Remove from Cart ---

class RemoveFromCartTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, producer_profile = make_producer()
        product = make_product(producer_profile)
        cart = Cart.objects.create(customer=self.customer)
        self.item = CartItem.objects.create(cart=cart, product=product, quantity=1)
        self.url = reverse('cart:remove_from_cart', kwargs={'item_id': self.item.pk})

    def test_remove_from_cart_success(self):
        """TC-009: Customer can remove an item from the cart."""
        self.client.force_login(self.customer)
        self.client.post(self.url)
        self.assertFalse(CartItem.objects.filter(pk=self.item.pk).exists())

    def test_remove_from_cart_blocked_for_other_customer(self):
        """TC-009: Cannot remove another customer's cart item."""
        other = make_customer(email='other@test.com')
        self.client.force_login(other)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)


# --- TC-010: Checkout ---

class CheckoutTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, producer_profile = make_producer()
        product = make_product(producer_profile)
        cart = Cart.objects.create(customer=self.customer)
        CartItem.objects.create(cart=cart, product=product, quantity=2)
        self.url = reverse('cart:checkout')

    def _checkout_post(self, delivery_date=None):
        return self.client.post(self.url, {
            'delivery_address': '1 Test St, Bristol',
            'delivery_date': delivery_date or future_date(3),
            'special_instructions': '',
        })

    def test_checkout_creates_order_and_clears_cart(self):
        """TC-010: Successful checkout creates Order, OrderItems, Payment and clears cart."""
        self.client.force_login(self.customer)
        response = self._checkout_post()
        # Redirects to confirmation
        self.assertEqual(response.status_code, 302)
        self.assertIn('/confirmation/', response['Location'])
        # Order created
        order = Order.objects.filter(customer=self.customer).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.items.count(), 1)
        # Payment created
        self.assertTrue(Payment.objects.filter(order=order).exists())
        # Cart cleared
        self.assertEqual(CartItem.objects.filter(cart__customer=self.customer).count(), 0)

    def test_checkout_rejects_past_date(self):
        """TC-010: Delivery date less than 48h from now is rejected."""
        self.client.force_login(self.customer)
        yesterday = (timezone.now() - timedelta(days=1)).date().isoformat()
        response = self._checkout_post(delivery_date=yesterday)
        # Stays on checkout page (form error)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '48 hours')
        self.assertEqual(Order.objects.filter(customer=self.customer).count(), 0)

    def test_checkout_empty_cart_redirects(self):
        """TC-010: Checking out with empty cart redirects back."""
        CartItem.objects.filter(cart__customer=self.customer).delete()
        self.client.force_login(self.customer)
        response = self._checkout_post()
        self.assertRedirects(response, reverse('cart:cart_detail'))

    def test_checkout_blocked_for_producer(self):
        """TC-010: Producers cannot checkout."""
        producer_user, _ = make_producer(email='prod2@test.com')
        self.client.force_login(producer_user)
        response = self._checkout_post()
        self.assertEqual(response.status_code, 403)


# --- TC-012: Order History ---

class OrderHistoryTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, producer_profile = make_producer()
        product = make_product(producer_profile)
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='1 Test St',
            delivery_date=future_date(3),
            status='pending',
        )
        OrderItem.objects.create(
            order=self.order,
            product=product,
            producer=producer_profile,
            product_name=product.name,
            price_at_time=product.price,
            quantity=1,
        )

    def test_order_history_shows_customers_orders(self):
        """TC-012: Customer can see their own orders in order history."""
        self.client.force_login(self.customer)
        response = self.client.get(reverse('cart:order_history'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.order_number)

    def test_order_history_hides_other_customers_orders(self):
        """TC-012: Customer cannot see another customer's orders."""
        other = make_customer(email='other@test.com')
        other_order = Order.objects.create(
            customer=other,
            delivery_address='2 Other St',
            delivery_date=future_date(3),
            status='pending',
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('cart:order_history'))
        self.assertNotContains(response, other_order.order_number)

    def test_order_history_requires_login(self):
        """TC-012: Unauthenticated access redirects to login."""
        response = self.client.get(reverse('cart:order_history'))
        self.assertEqual(response.status_code, 302)


# --- TC-013: Reorder ---

class ReorderTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        _, self.producer_profile = make_producer()
        self.available_product = make_product(self.producer_profile, name='Carrots', stock=10)
        self.order = Order.objects.create(
            customer=self.customer,
            delivery_address='1 Test St',
            delivery_date=future_date(3),
            status='delivered',
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.available_product,
            producer=self.producer_profile,
            product_name=self.available_product.name,
            price_at_time=self.available_product.price,
            quantity=3,
        )
        self.url = reverse('cart:reorder', kwargs={'order_id': self.order.pk})

    def test_reorder_adds_available_items_to_cart(self):
        """TC-013: Reorder adds available products back to the cart."""
        self.client.force_login(self.customer)
        self.client.post(self.url)
        self.assertTrue(
            CartItem.objects.filter(
                cart__customer=self.customer,
                product=self.available_product
            ).exists()
        )

    def test_reorder_skips_unavailable_products(self):
        """TC-013: Reorder skips products that are out of stock."""
        self.available_product.stock_quantity = 0
        self.available_product.save()
        self.client.force_login(self.customer)
        self.client.post(self.url)
        self.assertFalse(
            CartItem.objects.filter(cart__customer=self.customer).exists()
        )

    def test_reorder_blocked_for_other_customer(self):
        """TC-013: Cannot reorder another customer's order."""
        other = make_customer(email='other@test.com')
        self.client.force_login(other)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)
