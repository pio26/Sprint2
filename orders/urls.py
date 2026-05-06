from django.urls import path

from . import views

app_name = 'orders'

urlpatterns = [
    path('incoming/', views.incoming_orders, name='incoming_orders'),
    path('dashboard/', views.producer_dashboard, name='producer_dashboard'),
    path('settlements/', views.payment_settlements, name='settlements'),
    path('settlements.csv', views.payment_settlements_csv, name='settlements_csv'),
    path('notifications/', views.notifications, name='notifications'),
    path('admin/commissions/', views.commission_report, name='commission_report'),
    path('admin/commissions.csv', views.commission_report_csv, name='commission_report_csv'),
    path('<int:order_id>/', views.order_detail_producer, name='order_detail'),
    path('<int:order_id>/update-status/', views.update_order_status, name='update_status'),
    path('<int:order_id>/update-delivery-date/', views.update_producer_delivery_date, name='update_delivery_date'),
]
