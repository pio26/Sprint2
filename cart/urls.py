from django.urls import path

from . import views

app_name = 'cart'

urlpatterns = [
    path('', views.cart_detail, name='cart_detail'),
    path('add/<int:product_id>/', views.add_to_cart, name='add_to_cart'),
    path('update/<int:item_id>/', views.update_cart, name='update_cart'),
    path('remove/<int:item_id>/', views.remove_from_cart, name='remove_from_cart'),
    path('checkout/', views.checkout, name='checkout'),
    path('confirmation/<int:order_id>/', views.order_confirmation, name='order_confirmation'),
    path('orders/', views.order_history, name='order_history'),
    path('orders/<int:order_id>/', views.order_detail_customer, name='order_detail'),
    path('orders/<int:order_id>/receipt/', views.order_receipt, name='order_receipt'),
    path('orders/<int:order_id>/reorder/', views.reorder, name='reorder'),
    path('recurring/', views.recurring_orders, name='recurring_orders'),
    path('recurring/<int:recurring_id>/', views.recurring_order_detail, name='recurring_order_detail'),
]
