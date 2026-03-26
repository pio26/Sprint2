from django.contrib import admin

from .models import Category, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'producer', 'category', 'price', 'stock_quantity', 'availability_status', 'is_organic']
    list_filter = ['category', 'availability_status', 'is_organic']
    search_fields = ['name', 'description', 'producer__business_name']
    list_editable = ['stock_quantity', 'availability_status']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('producer', 'category', 'name', 'description', 'image')}),
        ('Pricing & Stock', {'fields': ('price', 'unit', 'stock_quantity')}),
        ('Availability', {'fields': ('availability_status', 'season_start', 'season_end')}),
        ('Quality', {'fields': ('allergens', 'is_organic', 'harvest_date', 'best_before')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )
