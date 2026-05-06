from django.contrib import admin

from .models import Category, FarmStory, Product, ProductReview, ProductStockHistory, Recipe


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}
    search_fields = ['name']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'producer', 'category', 'price', 'effective_price', 'stock_quantity', 'availability_status', 'is_organic', 'is_surplus']
    list_filter = ['category', 'availability_status', 'is_organic', 'is_surplus']
    search_fields = ['name', 'description', 'producer__business_name']
    list_editable = ['stock_quantity', 'availability_status', 'is_surplus']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        (None, {'fields': ('producer', 'category', 'name', 'description', 'image')}),
        ('Pricing & Stock', {'fields': ('price', 'unit', 'stock_quantity', 'low_stock_threshold')}),
        ('Availability', {'fields': ('availability_status', 'season_start', 'season_end')}),
        ('Quality', {'fields': ('allergens', 'is_organic', 'harvest_date', 'best_before')}),
        ('Surplus Deals', {'fields': ('is_surplus', 'surplus_discount_percent', 'surplus_expires_at', 'surplus_note')}),
        ('Timestamps', {'fields': ('created_at', 'updated_at'), 'classes': ('collapse',)}),
    )


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ['title', 'producer', 'seasonal_tag', 'is_published', 'created_at']
    list_filter = ['is_published', 'seasonal_tag']
    search_fields = ['title', 'description', 'producer__business_name']
    filter_horizontal = ['products']


@admin.register(FarmStory)
class FarmStoryAdmin(admin.ModelAdmin):
    list_display = ['title', 'producer', 'seasonal_tag', 'is_published', 'created_at']
    list_filter = ['is_published', 'seasonal_tag']
    search_fields = ['title', 'body', 'producer__business_name']


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'customer', 'rating', 'verified_purchase', 'created_at']
    list_filter = ['rating', 'verified_purchase']
    search_fields = ['product__name', 'customer__email', 'title', 'text']


@admin.register(ProductStockHistory)
class ProductStockHistoryAdmin(admin.ModelAdmin):
    list_display = ['product', 'previous_quantity', 'new_quantity', 'changed_by', 'created_at']
    list_filter = ['product__producer']
    search_fields = ['product__name', 'changed_by__email']
    readonly_fields = ['product', 'changed_by', 'previous_quantity', 'new_quantity', 'note', 'created_at']
