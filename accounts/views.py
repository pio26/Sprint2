from django.contrib import messages
from datetime import timedelta

from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils import timezone

from .forms import (
    CustomerProfileForm,
    CustomerRegistrationForm,
    LoginForm,
    ProducerProfileForm,
    ProducerRegistrationForm,
)
from .models import LoginAttempt


def _client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def register_customer(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = CustomerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your customer account has been created.')
            return redirect('home')
    else:
        form = CustomerRegistrationForm()

    return render(request, 'accounts/register_customer.html', {'form': form})


def register_producer(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = ProducerRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Welcome, {user.first_name}! Your producer account has been created.')
            return redirect('home')
    else:
        form = ProducerRegistrationForm()

    return render(request, 'accounts/register_producer.html', {'form': form})


def login_view(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            ip_address = _client_ip(request)
            window_start = timezone.now() - timedelta(minutes=15)
            recent_failures = LoginAttempt.objects.filter(
                email=email.lower(),
                success=False,
                created_at__gte=window_start,
            ).count()
            if recent_failures >= 5:
                messages.error(request, 'Too many failed login attempts. Please wait and try again.')
                return render(request, 'accounts/login.html', {'form': form})

            user = authenticate(request, username=email, password=password)
            if user is not None:
                LoginAttempt.objects.create(email=email.lower(), ip_address=ip_address, success=True)
                login(request, user)
                if form.cleaned_data.get('remember_me'):
                    request.session.set_expiry(60 * 60 * 24 * 14)
                else:
                    request.session.set_expiry(0)
                if user.role == 'producer':
                    return redirect('products:producer_dashboard')
                return redirect('home')
            else:
                # TC-022: generic message — never reveal whether email exists
                LoginAttempt.objects.create(email=email.lower(), ip_address=ip_address, success=False)
                messages.error(request, 'Invalid email or password.')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('home')


@login_required
def profile_view(request):
    user = request.user

    if user.role in ('customer', 'community', 'restaurant'):
        profile = user.customer_profile
        if request.method == 'POST':
            form = CustomerProfileForm(request.POST)
            if form.is_valid():
                form.save(user)
                messages.success(request, 'Profile updated successfully.')
                return redirect('accounts:profile')
        else:
            form = CustomerProfileForm(initial={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'delivery_address': profile.delivery_address,
                'postcode': profile.postcode,
                'organization_name': profile.organization_name,
                'organization_type': profile.organization_type,
                'payment_terms': profile.payment_terms,
            })
    elif user.role == 'producer':
        profile = user.producer_profile
        if request.method == 'POST':
            form = ProducerProfileForm(request.POST)
            if form.is_valid():
                form.save(user)
                messages.success(request, 'Profile updated successfully.')
                return redirect('accounts:profile')
        else:
            form = ProducerProfileForm(initial={
                'first_name': user.first_name,
                'last_name': user.last_name,
                'phone': user.phone,
                'business_name': profile.business_name,
                'business_address': profile.business_address,
                'postcode': profile.postcode,
                'description': profile.description,
            })
    else:
        form = None

    return render(request, 'accounts/profile.html', {'form': form, 'profile_user': user})
