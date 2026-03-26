from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('incoming/', views.incoming_orders, name='incoming_orders'),
    path('dashboard/', views.producer_dashboard, name='producer_dashboard'),
    path('settlements/', views.payment_settlements, name='settlements'),
    path('<int:order_id>/', views.order_detail_producer, name='order_detail'),
    path('<int:order_id>/update-status/', views.update_order_status, name='update_status'),
]
