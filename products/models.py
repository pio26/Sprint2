import math
import re
from decimal import Decimal, ROUND_HALF_UP

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg
from django.utils import timezone


POSTCODE_COORDINATES = {
    'BS1': (51.4545, -2.5879),
    'BS2': (51.4594, -2.5775),
    'BS3': (51.4389, -2.6025),
    'BS4': (51.4407, -2.5602),
    'BS5': (51.4620, -2.5521),
    'BS6': (51.4698, -2.6041),
    'BS7': (51.4860, -2.5833),
    'BS8': (51.4570, -2.6200),
    'BS9': (51.4866, -2.6276),
    'BS10': (51.5092, -2.6105),
    'BS11': (51.4965, -2.6754),
    'BS13': (51.4147, -2.6097),
    'BS14': (51.4136, -2.5647),
    'BS15': (51.4616, -2.5009),
    'BS16': (51.4840, -2.5118),
    'BS41': (51.4030, -2.6580),
}


def postcode_area(postcode):
    if not postcode:
        return ''
    raw = postcode.strip().upper()
    if ' ' in raw:
        return raw.split()[0]
    cleaned = raw.replace(' ', '')
    match = re.match(r'^([A-Z]{1,2}\d{1,2}[A-Z]?)', cleaned)
    return match.group(1) if match else cleaned


def postcode_distance_miles(from_postcode, to_postcode):
    from_coords = POSTCODE_COORDINATES.get(postcode_area(from_postcode))
    to_coords = POSTCODE_COORDINATES.get(postcode_area(to_postcode))
    if not from_coords or not to_coords:
        return None

    lat1, lon1 = map(math.radians, from_coords)
    lat2, lon2 = map(math.radians, to_coords)
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    miles = 3958.8 * 2 * math.asin(math.sqrt(a))
    return Decimal(str(miles)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    AVAILABILITY_CHOICES = [
        ('in_season', 'In Season'),
        ('out_of_season', 'Out of Season'),
        ('year_round', 'Available Year-Round'),
    ]

    producer = models.ForeignKey(
        'accounts.ProducerProfile',
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=50)
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='year_round')
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

    allergens = models.JSONField(default=list, blank=True)
    allergens_declared = models.BooleanField(
        default=False,
        help_text='Tick to confirm allergen information has been reviewed and is complete for this product.',
    )

    is_organic = models.BooleanField(default=False)
    harvest_date = models.DateField(null=True, blank=True)
    best_before = models.DateField(null=True, blank=True)

    is_surplus = models.BooleanField(default=False)
    surplus_discount_percent = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(90)],
    )
    surplus_expires_at = models.DateTimeField(null=True, blank=True)
    surplus_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['availability_status']),
            models.Index(fields=['producer']),
            models.Index(fields=['is_organic']),
            models.Index(fields=['is_surplus']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        if self.stock_quantity <= 0:
            return False
        if self.availability_status == 'out_of_season':
            return False
        if self.availability_status == 'in_season':
            today = timezone.now().date()
            if self.season_start and today < self.season_start:
                return False
            if self.season_end and today > self.season_end:
                return False
        return True

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def is_surplus_active(self):
        if not self.is_surplus or self.surplus_discount_percent <= 0:
            return False
        if self.surplus_expires_at and self.surplus_expires_at < timezone.now():
            return False
        return self.is_available

    @property
    def effective_price(self):
        if not self.is_surplus_active:
            return self.price
        multiplier = Decimal('1') - (Decimal(self.surplus_discount_percent) / Decimal('100'))
        return (self.price * multiplier).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def average_rating(self):
        value = self.reviews.aggregate(avg=Avg('rating'))['avg']
        if value is None:
            return None
        return Decimal(str(value)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)

    def food_miles_from(self, customer_postcode):
        return postcode_distance_miles(customer_postcode, self.producer.postcode)


class ProductStockHistory(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='stock_history')
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )
    previous_quantity = models.PositiveIntegerField()
    new_quantity = models.PositiveIntegerField()
    note = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.product.name}: {self.previous_quantity} → {self.new_quantity}'


class Recipe(models.Model):
    producer = models.ForeignKey('accounts.ProducerProfile', on_delete=models.CASCADE, related_name='recipes')
    title = models.CharField(max_length=200)
    description = models.TextField()
    ingredients = models.TextField()
    instructions = models.TextField()
    seasonal_tag = models.CharField(max_length=100, blank=True)
    products = models.ManyToManyField(Product, blank=True, related_name='recipes')
    image = models.ImageField(upload_to='recipes/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class FarmStory(models.Model):
    producer = models.ForeignKey('accounts.ProducerProfile', on_delete=models.CASCADE, related_name='stories')
    title = models.CharField(max_length=200)
    body = models.TextField()
    seasonal_tag = models.CharField(max_length=100, blank=True)
    image = models.ImageField(upload_to='stories/', blank=True, null=True)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


class ProductReview(models.Model):
    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='product_reviews')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='reviews')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='reviews')
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    title = models.CharField(max_length=120)
    text = models.TextField()
    is_anonymous = models.BooleanField(default=False)
    verified_purchase = models.BooleanField(default=True)
    producer_response = models.TextField(blank=True)
    producer_response_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.UniqueConstraint(fields=['customer', 'product'], name='one_review_per_customer_product')
        ]

    def __str__(self):
        return f'{self.product.name}: {self.rating}/5'