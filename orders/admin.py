from django.contrib import admin
from django.db.models import Count

from .models import Order, OrderItem, Payment


def mark_as_confirmed(modeladmin, request, queryset):
    updated = queryset.filter(status='pending').update(status='confirmed')
    modeladmin.message_user(request, f'{updated} order(s) marked as Confirmed.')


mark_as_confirmed.short_description = 'Mark selected orders as Confirmed'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ['line_total']


class PaymentInline(admin.StackedInline):
    model = Payment
    extra = 0
    readonly_fields = ['transaction_id', 'created_at']


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['order_number', 'customer', 'status', 'delivery_date', 'total', 'created_at']
    list_filter = ['status', 'delivery_date']
    search_fields = ['order_number', 'customer__email']
    readonly_fields = ['order_number', 'created_at', 'updated_at']
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    actions = [mark_as_confirmed]
    inlines = [OrderItemInline, PaymentInline]

    def changelist_view(self, request, extra_context=None):
        extra_context = extra_context or {}
        qs = self.get_queryset(request)
        status_counts = {
            row['status']: row['count']
            for row in qs.values('status').annotate(count=Count('id'))
        }
        extra_context['status_summary'] = status_counts
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product_name', 'producer', 'price_at_time', 'quantity', 'line_total']
    list_filter = ['producer']
    search_fields = ['order__order_number', 'product_name']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['order', 'amount', 'commission', 'producer_amount', 'status', 'transaction_id', 'created_at']
    list_filter = ['status']
    readonly_fields = ['transaction_id', 'created_at']
    date_hierarchy = 'created_at'
