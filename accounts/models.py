from django.conf import settings
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email address is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'admin')
        return self.create_user(email, password, **extra_fields)


class User(AbstractUser):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('community', 'Community Group'),
        ('restaurant', 'Restaurant'),
        ('producer', 'Producer'),
        ('admin', 'Admin'),
    ]
    username = None
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    phone = models.CharField(max_length=20, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    objects = UserManager()


class CustomerProfile(models.Model):
    ACCOUNT_TYPE_CHOICES = [
        ('individual', 'Individual / Family'),
        ('community_group', 'Community Group'),
        ('restaurant', 'Restaurant / Cafe'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='customer_profile')
    account_type = models.CharField(max_length=30, choices=ACCOUNT_TYPE_CHOICES, default='individual')
    organization_name = models.CharField(max_length=200, blank=True)
    organization_type = models.CharField(max_length=100, blank=True)
    payment_terms = models.CharField(max_length=100, blank=True)
    delivery_address = models.TextField()
    postcode = models.CharField(max_length=10)

    def __str__(self):
        if self.organization_name:
            return self.organization_name
        return self.user.get_full_name() or self.user.email


class ProducerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='producer_profile')
    business_name = models.CharField(max_length=200)
    business_address = models.TextField()
    postcode = models.CharField(max_length=10)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.business_name


class Notification(models.Model):
    CATEGORY_CHOICES = [
        ('order', 'Order'),
        ('stock', 'Stock'),
        ('payment', 'Payment'),
        ('surplus', 'Surplus'),
        ('security', 'Security'),
        ('general', 'General'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='general')
    related_order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, null=True, blank=True)
    related_product = models.ForeignKey('products.Product', on_delete=models.CASCADE, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['category']),
        ]

    def __str__(self):
        return f'{self.title} -> {self.user.email}'


class LoginAttempt(models.Model):
    email = models.EmailField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    success = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'created_at']),
            models.Index(fields=['ip_address', 'created_at']),
        ]

    def __str__(self):
        result = 'success' if self.success else 'failed'
        return f'{self.email} {result} at {self.created_at:%Y-%m-%d %H:%M}'
