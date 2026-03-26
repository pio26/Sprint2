from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = 'categories'
        ordering = ['name']

    def __str__(self):
        return self.name


class Product(models.Model):
    AVAILABILITY_CHOICES = [
        ('in_season', 'In Season'),
        ('out_of_season', 'Out of Season'),
        ('year_round', 'Available Year-Round'),
    ]

    producer = models.ForeignKey(
        'accounts.ProducerProfile',
        on_delete=models.CASCADE,
        related_name='products'
    )
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='products')
    name = models.CharField(max_length=200)
    description = models.TextField()
    price = models.DecimalField(max_digits=8, decimal_places=2)
    unit = models.CharField(max_length=50)
    stock_quantity = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to='products/', blank=True, null=True)

    availability_status = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='year_round')
    season_start = models.DateField(null=True, blank=True)
    season_end = models.DateField(null=True, blank=True)

    allergens = models.JSONField(default=list, blank=True)

    is_organic = models.BooleanField(default=False)
    harvest_date = models.DateField(null=True, blank=True)
    best_before = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['category']),
            models.Index(fields=['availability_status']),
            models.Index(fields=['producer']),
        ]

    def __str__(self):
        return self.name

    @property
    def is_available(self):
        if self.stock_quantity <= 0:
            return False
        if self.availability_status == 'out_of_season':
            return False
        return True
