from decimal import Decimal
from collections import OrderedDict
from django.conf import settings
from django.db import models


class Cart(models.Model):
    customer = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cart'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def get_total(self):
        return sum(item.line_total for item in self.items.select_related('product').all())

    def get_total_food_miles(self, customer_postcode=None):
        postcode = customer_postcode
        if postcode is None and hasattr(self.customer, 'customer_profile'):
            postcode = self.customer.customer_profile.postcode
        total = 0
        for item in self.items.select_related('product__producer').all():
            miles = item.product.food_miles_from(postcode)
            if miles is not None:
                total += float(miles) * item.quantity
        return round(total, 1)

    def get_items_by_producer(self):
        grouped = OrderedDict()
        for item in self.items.select_related('product__producer__user').all():
            producer = item.product.producer
            if producer.id not in grouped:
                grouped[producer.id] = {
                    'producer': producer,
                    'items': [],
                    'subtotal': Decimal('0.00'),
                }
            grouped[producer.id]['items'].append(item)
            grouped[producer.id]['subtotal'] += item.line_total
        return grouped

    @property
    def item_count(self):
        return self.items.count()


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('products.Product', on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart', 'product')

    @property
    def line_total(self):
        return self.product.effective_price * self.quantity
