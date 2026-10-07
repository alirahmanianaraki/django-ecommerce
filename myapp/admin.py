from django.contrib import admin
from django import forms
from .models import (
    Product, ProductImage, Tag, Category, 
    Feature, FeatureValue, ProductFeature
    )
# Register your models here.

class CategoryAdminForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            exclude = [c.pk for c in self.instance.get_descendants(include_self=True)]
            self.fields['parent'].queryset = Category.objects.exclude(pk__in=exclude)

admin.site.register(ProductImage)
admin.site.register(Tag)

class ProductFeatureInline(admin.TabularInline):
    model = ProductFeature
    extra = 1
    autocomplete_fields = ['feature', 'value']

class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 3

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'price', 'stock', 'is_available']
    list_filter = ['is_available', 'category']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title', )}
    filter_horizontal = ['category', 'tag']
    inlines = [ProductImageInline, ProductFeatureInline]

@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    form = CategoryAdminForm
    list_display = ['name', 'parent', 'full_path', 'created_at']
    list_filter = ['parent', 'created_at']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name', )}
    ordering = ['name']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'parent__parent__parent__parent'
            )

@admin.register(Feature)
class FeatureAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'base_unit', 
                    'is_filterable', 'is_visible_on_product_page', 
                    'display_order']
    list_editable = ['base_unit', 'is_filterable', 'is_visible_on_product_page',
                     'display_order']
    search_fields = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}

@admin.register(FeatureValue)
class FeatureValueAdmin(admin.ModelAdmin):
    list_display = ['feature', 'unit', 'value', 'numeric_value', 'slug', 'display_order']
    list_filter = ['feature']
    list_editable = ['unit', 'numeric_value', 'display_order']
    search_fields = ['value', 'slug']
    #prepopulated_fields = {'slug': ('feature', 'value', 'unit')}
    autocomplete_fields = ['feature']

@admin.register(ProductFeature)
class ProductFeatureAdmin(admin.ModelAdmin):
    list_display = ['product', 'feature', 'value']
    list_filter = ['feature']
    autocomplete_fields = ['product', 'feature', 'value']
    search_fields = ['product__title', 'feature__name', 'value__value']

