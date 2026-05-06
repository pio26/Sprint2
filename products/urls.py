from django.urls import path

from . import views

app_name = 'products'

urlpatterns = [
    # Public views — static paths first to avoid <int:pk> conflicts
    path('', views.product_list, name='product_list'),
    path('search/', views.product_search, name='product_search'),
    path('surplus/', views.surplus_deals, name='surplus_deals'),
    path('categories/', views.category_list, name='category_list'),
    path('category/<slug:slug>/', views.products_by_category, name='products_by_category'),
    # Producer-only views — static paths before <int:pk>
    path('add/', views.product_create, name='product_create'),
    path('dashboard/', views.producer_dashboard, name='producer_dashboard'),
    path('content/recipe/add/', views.recipe_create, name='recipe_create'),
    path('content/story/add/', views.story_create, name='story_create'),
    path('producer/<int:producer_id>/', views.producer_profile, name='producer_profile'),
    path('reviews/order-item/<int:order_item_id>/', views.write_review, name='write_review'),
    # Dynamic pk paths
    path('<int:pk>/', views.product_detail, name='product_detail'),
    path('<int:pk>/edit/', views.product_edit, name='product_edit'),
    path('<int:pk>/delete/', views.product_delete, name='product_delete'),
    path('<int:pk>/stock/', views.stock_update, name='stock_update'),
    path('<int:pk>/surplus/', views.mark_surplus, name='mark_surplus'),
]
