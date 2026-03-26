from django.urls import path

from . import views

app_name = 'products'

urlpatterns = [
    # Public views — static paths first to avoid <int:pk> conflicts
    path('', views.product_list, name='product_list'),
    path('search/', views.product_search, name='product_search'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:slug>/', views.products_by_category, name='products_by_category'),
    # Producer-only views — static paths before <int:pk>
    path('add/', views.product_create, name='product_create'),
    path('dashboard/', views.producer_dashboard, name='producer_dashboard'),
    # Dynamic pk paths
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('<int:pk>/stock/', views.stock_update, name='stock_update'),
]
