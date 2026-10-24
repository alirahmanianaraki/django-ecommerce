from django.contrib import admin, messages
from .models import Order, OrderItem, OrderStatusEvent
from .services import (
    transition_order,
    InvalidStatusTransition,
    TrackingNumberRequired
)
# Register your models here.

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'user', 'status', 'total_amount', 'is_paied', 'created_at']
    list_filter = ['status', 'is_paied']
    search_fields = ['user__username', 'user__email', 'tracking_number']
    readonly_fields = ['created_at', 'status_updated_at']

    actions = [
        'mark_paid',
        'mark_processing',
        'mark_shipped',
        'mark_delivered'
    ]

    def _transition_bulk(self, request, queryset, new_status):
        ok, failed = 0, 0
        for order in queryset:
            try:
                transition_order(
                    order,
                    new_status,
                    changed_by=request.user,
                    note=f"Marked {new_status} by admin",
                    tracking_number='ADMIN_PLACEHOLDER',
                )
                ok += 1
            except (InvalidStatusTransition, TrackingNumberRequired) as exc:
                failed += 1
                self.message_user(
                    request,
                    f"Order #{order.pk}: {exc}",
                    level=messages.WARNING,
                )
        if ok:
            self.message_user(
                request,
                f"{ok} order(s) moved to '{new_status}'",
                level=messages.SUCCESS
            )

    @admin.action(description='Mark as paid')
    def mark_paid(self, request, queryset):
        self._transition_bulk(request, queryset, Order.Status.PAID)

    @admin.action(description='Mark as processing')
    def mark_processing(self, request, queryset):
        self._transition_bulk(request, queryset, Order.Status.PROCESSING)

    @admin.action(description='Mark as shipped')
    def mark_shipped(self, request, queryset):
        self._transition_bulk(request, queryset, Order.Status.SHIPPED)

    @admin.action(description='Mark as delivered')
    def mark_delivered(self, request, queryset):
        self._transition_bulk(request, queryset, Order.Status.DELIVERED)

@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(admin.ModelAdmin):
    list_display = ['order', 'from_status', 'to_status', 'changed_at', 'changed_by']
    list_filter = ['to_status', 'changed_at']
    search_fields = ['order__pk', 'note']
    readonly_fields = ['order', 'from_status', 'to_status', 'changed_at', 'changed_by', 'note']
    ordering = ['-changed_at']

    def has_add_permission(self, request):
        # Events are created only by the transition service - not by hand
        return False

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ['order', 'product', 'quantity', 'unit_price']
    list_filter = ['product']
    search_fields = ['order', 'product']