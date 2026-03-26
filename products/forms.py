from django import forms

from .models import Category, Product

UK_ALLERGENS = [
    'Celery', 'Cereals with gluten', 'Crustaceans', 'Eggs', 'Fish',
    'Lupin', 'Milk', 'Molluscs', 'Mustard', 'Nuts', 'Peanuts',
    'Sesame', 'Soybeans', 'Sulphur dioxide',
]

ALLERGEN_CHOICES = [(a, a) for a in UK_ALLERGENS]


class ProductForm(forms.Form):
    name = forms.CharField(
        max_length=200,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 4})
    )
    category = forms.ModelChoiceField(
        queryset=Category.objects.all(),
        empty_label='Select a category',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    price = forms.DecimalField(
        max_digits=8, decimal_places=2, min_value=0.01,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    unit = forms.CharField(
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. per kg, per dozen, per litre'})
    )
    stock_quantity = forms.IntegerField(
        min_value=0,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={'class': 'form-control'})
    )
    availability_status = forms.ChoiceField(
        choices=Product.AVAILABILITY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_availability_status'})
    )
    season_start = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    season_end = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    allergens = forms.MultipleChoiceField(
        choices=ALLERGEN_CHOICES,
        required=False,
        widget=forms.CheckboxSelectMultiple()
    )
    is_organic = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    harvest_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    best_before = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def save(self, producer_profile, instance=None):
        data = self.cleaned_data
        if instance is None:
            instance = Product(producer=producer_profile)

        instance.name = data['name']
        instance.description = data['description']
        instance.category = data['category']
        instance.price = data['price']
        instance.unit = data['unit']
        instance.stock_quantity = data['stock_quantity']
        instance.availability_status = data['availability_status']
        instance.season_start = data.get('season_start')
        instance.season_end = data.get('season_end')
        instance.allergens = data.get('allergens', [])
        instance.is_organic = data.get('is_organic', False)
        instance.harvest_date = data.get('harvest_date')
        instance.best_before = data.get('best_before')

        if data.get('image'):
            instance.image = data['image']

        instance.save()
        return instance


class StockUpdateForm(forms.Form):
    stock_quantity = forms.IntegerField(
        min_value=0,
        label='Stock quantity',
        widget=forms.NumberInput(attrs={'class': 'form-control', 'style': 'max-width: 150px;'})
    )
