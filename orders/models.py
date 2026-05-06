from decimal import Decimal, ROUND_HALF_UP
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('ready', 'Ready for Collection/Delivery'),
        ('delivered', 'Delivered'),
        ('cancelled', 'Cancelled'),
    ]

    VALID_TRANSITIONS = {
        'pending': ['confirmed', 'cancelled'],
        'confirmed': ['ready', 'cancelled'],
        'ready': ['delivered'],
        'delivered': [],
        'cancelled': [],
    }

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='orders')
    order_number = models.CharField(max_length=20, unique=True, editable=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    delivery_address = models.TextField()
    delivery_date = models.DateField()
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['delivery_date']),
            models.Index(fields=['customer']),
        ]

    def save(self, *args, **kwargs):
        if not self.order_number:
            import uuid
            self.order_number = f"BFN-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return self.order_number

    @property
    def total(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def commission_amount(self):
        return (self.total * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def total_with_commission(self):
        return self.total + self.commission_amount

    @property
    def producer_payment(self):
        return self.total - self.commission_amount

    def clean(self):
        from django.utils import timezone
        from datetime import timedelta
        if self.delivery_date:
            min_date = (timezone.now() + timedelta(hours=48)).date()
            if self.delivery_date < min_date:
                raise ValidationError("Delivery date must be at least 48 hours from now.")

    def can_transition_to(self, new_status):
        return new_status in self.VALID_TRANSITIONS.get(self.status, [])


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    producer_order = models.ForeignKey('ProducerOrder', on_delete=models.CASCADE, null=True, blank=True, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.SET_NULL, null=True)
    producer = models.ForeignKey('accounts.ProducerProfile', on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=200)
    price_at_time = models.DecimalField(max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price_at_time * self.quantity


class ProducerOrder(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='producer_orders')
    producer = models.ForeignKey('accounts.ProducerProfile', on_delete=models.CASCADE, related_name='producer_orders')
    delivery_date = models.DateField()
    status = models.CharField(max_length=20, choices=Order.STATUS_CHOICES, default='pending')
    special_instructions = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['delivery_date', 'created_at']
        constraints = [
            models.UniqueConstraint(fields=['order', 'producer'], name='one_producer_order_per_order')
        ]

    def __str__(self):
        return f'{self.order.order_number} / {self.producer.business_name}'

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())

    @property
    def commission_amount(self):
        return (self.subtotal * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

    @property
    def producer_payment(self):
        return self.subtotal - self.commission_amount

    def can_transition_to(self, new_status):
        return new_status in Order.VALID_TRANSITIONS.get(self.status, [])


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_history')
    producer_order = models.ForeignKey(ProducerOrder, on_delete=models.CASCADE, null=True, blank=True, related_name='status_history')
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    from_status = models.CharField(max_length=20)
    to_status = models.CharField(max_length=20)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.order.order_number}: {self.from_status} -> {self.to_status}'


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    commission = models.DecimalField(max_digits=10, decimal_places=2)
    producer_amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, default='card')
    transaction_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.transaction_id:
            import uuid
            self.transaction_id = f"SBX-{uuid.uuid4().hex[:12].upper()}"
        super().save(*args, **kwargs)


class RecurringOrder(models.Model):
    FREQUENCY_CHOICES = [
        ('weekly', 'Weekly'),
        ('fortnightly', 'Fortnightly'),
    ]
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    customer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='recurring_orders')
    name = models.CharField(max_length=200, default='Recurring order')
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='weekly')
    delivery_weekday = models.PositiveSmallIntegerField(choices=WEEKDAY_CHOICES, default=2)
    next_delivery_date = models.DateField()
    special_instructions = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['next_delivery_date']

    def __str__(self):
        return f'{self.name} for {self.customer.email}'


class RecurringOrderItem(models.Model):
    recurring_order = models.ForeignKey(RecurringOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    producer = models.ForeignKey('accounts.ProducerProfile', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['recurring_order', 'product'], name='one_product_per_recurring_template')
        ]

    @property
    def line_total(self):
        return self.product.effective_price * self.quantity
