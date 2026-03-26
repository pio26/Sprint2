from datetime import timedelta

from django import forms
from django.utils import timezone


class CheckoutForm(forms.Form):
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

    def clean_delivery_date(self):
        date = self.cleaned_data['delivery_date']
        min_date = (timezone.now() + timedelta(hours=48)).date()
        if date < min_date:
            raise forms.ValidationError(
                "Delivery date must be at least 48 hours from now."
            )
        return date
