from django.contrib import admin
from django import forms
from .models import (
    Product, 
    ProductImage, 
    Tag,
    Category)
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

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['title', 'price', 'stock', 'is_available']
    list_filter = ['is_available', 'category']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title', )}
    filter_horizontal = ['category', 'tag']

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
