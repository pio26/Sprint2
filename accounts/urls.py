from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/customer/', views.register_customer, name='register_customer'),
    path('register/producer/', views.register_producer, name='register_producer'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('profile/', views.profile_view, name='profile'),
]
