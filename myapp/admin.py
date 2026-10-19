from django.contrib import admin, messages
from django.utils import timezone
from django import forms
from .models import (
    Product, ProductImage, Tag, Category, 
    Feature, FeatureValue, ProductFeature,
    Review, StockAlert
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
    actions = ['notify_waiting_customers']

    @admin.action(description='Notify waiting stock alerts for selected products')
    def notify_waiting_customers(self, request, queryset):
        from .emails import send_stock_alert_email

        total_sent = 0
        total_failed = 0

        for product in queryset:
            if product.stock <= 0:
                self.message_user(
                    request,
                    f"{product.title} is still out of stock - Skipped",
                    level=messages.WARNING
                )
                continue

            alerts = list(
                StockAlert.objects.filter(
                    product=product, notified_at__isnull=True)
            )
            if not alerts:
                self.message_user(
                    request,
                    f"{product.title}: no waiting alerts",
                    level=messages.INFO
                )
                continue

            for alert in alerts:
                try:
                    send_stock_alert_email(alert)
                    alert.notified_at = timezone.now()
                    alert.save(update_fields=['notified_at'])
                    total_sent += 1
                except Exception as exc:
                    total_failed += 1
                    self.message_user(
                        request,
                        f"Failed to email {alert.email}: {exc}",
                        level=messages.ERROR
                    )

        if total_sent:
            self.message_user(
                request,
                f"sent {total_sent} stock alert(s)",
                level=messages.SUCCESS
            )
        if total_failed:
            self.message_user(
                request,
                f"{total_failed} alert(s) failed to send",
                level=messages.WARNING
            )


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
    list_filter = ['is_filterable', 'is_visible_on_product_page']
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

@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ['product', 'user', 'rating', 'title', 'created_at']
    list_filter = ['rating', 'created_at']
    search_fields = ['product__title', 'user__username', 'title', 'body']
    autocomplete_fields = ['product', 'user']
    readonly_fields = ['created_at', 'updated_at']

@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ['product', 'email', 'created_at', 'notified_at']
    list_filter = ['notified_at', 'created_at']
    search_fields = ['email', 'product__title']
    autocomplete_fields = ['product']
    readonly_fields = ['created_at', 'notified_at']
    actions = ['mark_as_notified']

    @admin.action(description='Mark selected alerts as notified (no email sent)')
    def mark_as_notified(self, request, queryset):
        updated = queryset.filter(notified_at__isnull=True).update(
            notified_at__isnull=timezone.now()
        )
        self.message_user(
            request,
            f"{updated} alert(s) marked as notified",
            level=messages.success
        )