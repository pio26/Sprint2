from datetime import timedelta

from django import forms
from django.utils import timezone


class CheckoutForm(forms.Form):
    PAYMENT_METHOD_CHOICES = [
        ('mock_card', 'Test card payment'),
        ('mock_invoice', 'Invoice / purchase order'),
    ]
    RECURRENCE_CHOICES = [
        ('weekly', 'Weekly'),
        ('fortnightly', 'Fortnightly'),
    ]
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]

    delivery_address = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
        label='Delivery Address',
    )
    delivery_date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label='Delivery Date',
    )
    special_instructions = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
        label='Special Instructions (optional)',
    )
    payment_method = forms.ChoiceField(
        required=False,
        choices=PAYMENT_METHOD_CHOICES,
        initial='mock_card',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    test_payment_reference = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Sandbox reference or purchase order'}),
    )
    allergen_acknowledged = forms.BooleanField(
        required=True,
        error_messages={'required': 'You must confirm you have reviewed the allergen information before placing your order.'},
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I have reviewed the allergen information for all items in my cart.',
    )
    make_recurring = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    recurrence_frequency = forms.ChoiceField(
        required=False,
        choices=RECURRENCE_CHOICES,
        initial='weekly',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    recurring_delivery_weekday = forms.TypedChoiceField(
        required=False,
        choices=WEEKDAY_CHOICES,
        coerce=int,
        initial=2,
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    def clean_delivery_date(self):
        date = self.cleaned_data['delivery_date']
        min_date = (timezone.now() + timedelta(hours=48)).date()
        if date < min_date:
            raise forms.ValidationError(
                "Delivery date must be at least 48 hours from now."
            )
        return date

    def clean_payment_method(self):
        return self.cleaned_data.get('payment_method') or 'mock_card'
