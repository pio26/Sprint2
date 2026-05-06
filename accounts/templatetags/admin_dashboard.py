from decimal import Decimal

from django import template

from accounts.models import LoginAttempt, Notification, User
from orders.models import Order
from products.models import Product

register = template.Library()


@register.simple_tag
def admin_dashboard_stats():
    delivered = Order.objects.filter(status='delivered')
    revenue = sum((order.total for order in delivered), Decimal('0.00'))
    commission = sum((order.commission_amount for order in delivered), Decimal('0.00'))
    failed_logins = LoginAttempt.objects.filter(success=False).count()
    return {
        'users': User.objects.count(),
        'products': Product.objects.count(),
        'orders': Order.objects.count(),
        'pending_orders': Order.objects.filter(status='pending').count(),
        'delivered_orders': delivered.count(),
        'unread_notifications': Notification.objects.filter(is_read=False).count(),
        'low_stock_products': Product.objects.filter(stock_quantity__lte=5).count(),
        'surplus_products': Product.objects.filter(is_surplus=True).count(),
        'failed_logins': failed_logins,
        'revenue': revenue,
        'commission': commission,
    }
