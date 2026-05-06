from django.test import TestCase
from django.urls import reverse

from .models import CustomerProfile, ProducerProfile, User


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
    ProducerProfile.objects.create(
        user=user, business_name='Test Farm',
        business_address='Farm Lane', postcode='BS2 2BB'
    )
    return user


# --- TC-002: Customer Registration ---

class CustomerRegistrationTests(TestCase):

    def test_customer_registration_success(self):
        """TC-002: Customer can register and is logged in immediately."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'password1': 'Testpass99!',
            'password2': 'Testpass99!',
            'delivery_address': '10 Broad Street, Bristol',
            'postcode': 'BS1 1AB',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='alice@example.com')
        self.assertEqual(user.role, 'customer')
        self.assertTrue(CustomerProfile.objects.filter(user=user).exists())

    def test_customer_registration_password_too_short(self):
        """TC-002: Password shorter than 8 chars is rejected."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'password1': 'short',
            'password2': 'short',
            'delivery_address': '10 Broad Street',
            'postcode': 'BS1 1AB',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='alice@example.com').exists())

    def test_customer_registration_password_mismatch(self):
        """TC-002: Mismatched passwords rejected."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'password1': 'Testpass99!',
            'password2': 'Different99!',
            'delivery_address': '10 Broad Street',
            'postcode': 'BS1 1AB',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='alice@example.com').exists())

    def test_customer_registration_duplicate_email(self):
        """TC-002: Duplicate email is rejected."""
        make_customer(email='alice@example.com')
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'password1': 'Testpass99!',
            'password2': 'Testpass99!',
            'delivery_address': '10 Broad Street',
            'postcode': 'BS1 1AB',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='alice@example.com').count(), 1)


# --- TC-001: Producer Registration ---

class ProducerRegistrationTests(TestCase):

    def test_producer_registration_success(self):
        """TC-001: Producer can register with business details."""
        response = self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Bob',
            'last_name': 'Jones',
            'email': 'bob@farm.com',
            'password1': 'Farmpass99!',
            'password2': 'Farmpass99!',
            'business_name': 'Jones Farm',
            'business_address': 'Farm Lane, Bristol',
            'postcode': 'BS2 2BA',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='bob@farm.com')
        self.assertEqual(user.role, 'producer')
        profile = ProducerProfile.objects.get(user=user)
        self.assertEqual(profile.business_name, 'Jones Farm')

    def test_producer_registration_password_mismatch(self):
        """TC-001: Mismatched passwords rejected."""
        response = self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Bob',
            'last_name': 'Jones',
            'email': 'bob@farm.com',
            'password1': 'Farmpass99!',
            'password2': 'Different99!',
            'business_name': 'Jones Farm',
            'business_address': 'Farm Lane',
            'postcode': 'BS2 2BA',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='bob@farm.com').exists())

    def test_producer_registration_duplicate_email(self):
        """TC-001: Duplicate email is rejected."""
        make_producer(email='bob@farm.com')
        response = self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Bob',
            'last_name': 'Jones',
            'email': 'bob@farm.com',
            'password1': 'Farmpass99!',
            'password2': 'Farmpass99!',
            'business_name': 'Another Farm',
            'business_address': 'Other Lane',
            'postcode': 'BS2 2BA',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(User.objects.filter(email='bob@farm.com').count(), 1)


# --- TC-022: Authentication & Security ---

class AuthSecurityTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer = make_producer()

    def test_login_success_customer(self):
        """TC-022: Customer login redirects to home."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'customer@test.com',
            'password': 'Testpass99!',
        })
        self.assertRedirects(response, reverse('home'))

    def test_login_success_producer(self):
        """TC-022: Producer login redirects to producer dashboard."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'producer@test.com',
            'password': 'Testpass99!',
        })
        self.assertRedirects(response, reverse('products:producer_dashboard'))

    def test_login_wrong_password(self):
        """TC-022: Wrong password shows generic error (no email leak)."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'customer@test.com',
            'password': 'wrongpassword',
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('Invalid' in str(m) for m in messages))

    def test_login_nonexistent_email(self):
        """TC-022: Non-existent email shows same generic error as wrong password."""
        response = self.client.post(reverse('accounts:login'), {
            'email': 'nobody@example.com',
            'password': 'Testpass99!',
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any('Invalid' in str(m) for m in messages))

    def test_logout_clears_session(self):
        """TC-022: Logout terminates session."""
        self.client.login(username='customer@test.com', password='Testpass99!')
        response = self.client.post(reverse('accounts:logout'))
        self.assertRedirects(response, reverse('home'))
        # Subsequent protected request should redirect to login
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_protected_view_redirects_unauthenticated(self):
        """TC-022: Profile view redirects to login when not authenticated."""
        response = self.client.get(reverse('accounts:profile'))
        self.assertRedirects(response, f"{reverse('accounts:login')}?next={reverse('accounts:profile')}")

    def test_producer_required_blocks_customer(self):
        """TC-022: @producer_required returns 403 for a customer."""
        from django.http import HttpRequest
        from django.contrib.auth.middleware import get_user
        from .decorators import producer_required

        self.client.login(username='customer@test.com', password='Testpass99!')

        @producer_required
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = HttpRequest()
        request.user = self.customer
        response = dummy_view(request)
        self.assertEqual(response.status_code, 403)

    def test_customer_required_blocks_producer(self):
        """TC-022: @customer_required returns 403 for a producer."""
        from django.http import HttpRequest
        from .decorators import customer_required

        @customer_required
        def dummy_view(request):
            from django.http import HttpResponse
            return HttpResponse('ok')

        request = HttpRequest()
        request.user = self.producer
        response = dummy_view(request)
        self.assertEqual(response.status_code, 403)


# --- TC-001 extras: phone stored, password hashed ---

class ProducerRegistrationExtrasTests(TestCase):

    def test_producer_phone_stored_on_user(self):
        """TC-001: Phone number is saved on the user record."""
        self.client.post(reverse('accounts:register_producer'), {
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
        user = User.objects.get(email='jane@farm.com')
        self.assertEqual(user.phone, '01179 123456')

    def test_producer_password_is_hashed(self):
        """TC-001: Password is never stored as plain text."""
        self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@farm.com',
            'password1': 'Farmpass99!',
            'password2': 'Farmpass99!',
            'business_name': 'Bristol Valley Farm',
            'business_address': 'Farm Lane',
            'postcode': 'BS1 4DJ',
        })
        user = User.objects.get(email='jane@farm.com')
        self.assertNotEqual(user.password, 'Farmpass99!')
        self.assertTrue(user.password.startswith('pbkdf2') or user.password.startswith('argon2') or user.password.startswith('bcrypt'))

    def test_producer_postcode_stored_on_profile(self):
        """TC-001: Postcode is saved on the producer profile."""
        self.client.post(reverse('accounts:register_producer'), {
            'first_name': 'Jane',
            'last_name': 'Smith',
            'email': 'jane@farm.com',
            'password1': 'Farmpass99!',
            'password2': 'Farmpass99!',
            'business_name': 'Bristol Valley Farm',
            'business_address': 'Farm Lane',
            'postcode': 'BS1 4DJ',
        })
        user = User.objects.get(email='jane@farm.com')
        self.assertEqual(user.producer_profile.postcode, 'BS1 4DJ')


# --- TC-002 extras: restaurant account type, delivery address ---

class CustomerRegistrationExtrasTests(TestCase):

    def test_restaurant_account_type_sets_role(self):
        """TC-002/TC-018: Restaurant account type is stored with restaurant role."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Chef',
            'last_name': 'Kim',
            'email': 'chef@restaurant.com',
            'password1': 'Chefpass99!',
            'password2': 'Chefpass99!',
            'account_type': 'restaurant',
            'delivery_address': 'The Clifton Kitchen, Bristol',
            'postcode': 'BS8 4AB',
        })
        self.assertRedirects(response, reverse('home'))
        user = User.objects.get(email='chef@restaurant.com')
        self.assertEqual(user.role, 'restaurant')

    def test_customer_delivery_address_stored(self):
        """TC-002: Delivery address is linked to the customer profile."""
        self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Robert',
            'last_name': 'Johnson',
            'email': 'robert@example.com',
            'password1': 'Customer99!',
            'password2': 'Customer99!',
            'delivery_address': '45 Park Street, Bristol',
            'postcode': 'BS1 5JG',
        })
        user = User.objects.get(email='robert@example.com')
        self.assertEqual(user.customer_profile.delivery_address, '45 Park Street, Bristol')

    def test_customer_password_is_hashed(self):
        """TC-002: Customer password is not stored as plain text."""
        self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Alice',
            'last_name': 'Smith',
            'email': 'alice@example.com',
            'password1': 'Testpass99!',
            'password2': 'Testpass99!',
            'delivery_address': '10 Broad Street',
            'postcode': 'BS1 1AB',
        })
        user = User.objects.get(email='alice@example.com')
        self.assertNotEqual(user.password, 'Testpass99!')


# --- TC-022 extras: admin/role boundary checks ---

class AuthSecurityExtrasTests(TestCase):

    def setUp(self):
        self.customer = make_customer()
        self.producer = make_producer()

    def test_unauthenticated_profile_redirects_to_login(self):
        """TC-022: Unauthenticated access to profile page redirects with next param."""
        response = self.client.get(reverse('accounts:profile'))
        self.assertIn('/login/', response['Location'])

    def test_admin_user_cannot_checkout(self):
        """TC-022: Superuser (admin) is blocked from customer checkout (producer-type denial)."""
        admin = User.objects.create_superuser(
            email='admin@test.com', password='Adminpass99!',
            first_name='Admin', last_name='User',
        )
        self.client.force_login(admin)
        response = self.client.get(reverse('cart:checkout'))
        self.assertIn(response.status_code, [302, 403])

    def test_weak_password_rejected_on_registration(self):
        """TC-022: Password '123' is rejected at registration."""
        response = self.client.post(reverse('accounts:register_customer'), {
            'first_name': 'Weak',
            'last_name': 'Pass',
            'email': 'weak@example.com',
            'password1': '123',
            'password2': '123',
            'delivery_address': '1 Test St',
            'postcode': 'BS1 1AB',
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(email='weak@example.com').exists())
