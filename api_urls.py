from django.urls import path

from products.api_views import CategoryListAPIView, ProductListAPIView


urlpatterns = [
    path('categories/', CategoryListAPIView.as_view(), name='api_categories'),
    path('products/', ProductListAPIView.as_view(), name='api_products'),
]
