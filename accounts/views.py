from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import (
    CustomerProfileForm,
    CustomerRegistrationForm,
    LoginForm,
    ProducerProfileForm,
    ProducerRegistrationForm,
)


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
            user = authenticate(request, username=email, password=password)
            if user is not None:
                login(request, user)
                if user.role == 'producer':
                    return redirect('products:producer_dashboard')
                return redirect('home')
            else:
                # TC-022: generic message — never reveal whether email exists
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

    if user.role == 'customer':
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
