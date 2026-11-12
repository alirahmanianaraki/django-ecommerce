from django.shortcuts import render, redirect, get_object_or_404
from django.urls import path
from django.contrib.admin import helpers
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied

from payments.models import Refund
from payments.refunds import RefundError, cancel_order_and_refund, refund_order_to_wallet
from payments.services import PaymentError
from .admin_froms import OverrideStatusForm, RefundForm
from .services import override_order_status, TrackingNumberRequired
from .models import Order, OrderItem, OrderStatusEvent
from .services import (
    transition_order,
    InvalidStatusTransition,
    TrackingNumberRequired
)
# Register your models here.

class RefundInline(admin.TabularInline):
    model = Refund
    extra = 0
    can_delete = False
    fields = ['created_at', 'amount', 'destination', 'reason', 'note', 'created_by']
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ['pk', 'user', 'status', 'total_amount', 'is_paied', 'created_at']
    list_filter = ['status', 'is_paied', 'status_updated_at']
    search_fields = ['user__username', 'user__email', 'tracking_number']
    readonly_fields = ['status', 'created_at', 'refunded_amount', 'status_updated_at', 'override_link',
                       'stripe_checkout_session_id', 'stripe_payment_intent_id', 'paid_at', 'refund_link']
    inlines = [RefundInline]

    actions = [
        'mark_paid',
        'mark_processing',
        'mark_shipped',
        'mark_delivered',
        'cancel_and_refund',
        'refund_remaining',
    ]

    def override_link(self, obj):
        if not obj.pk:
            return '-'
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:orders_order_override_status', args=[obj.pk])
        return format_html(
            '<a class="button" href="{}">Manual status override</a>', url
        )
    override_link.short_description = 'Status override'

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

    def get_urls(self):
        """
        Extend the admin's URLconf with our custom override view.
        """
        urls = super().get_urls()
        custom = [
            path(
                '<int:pk>/override-status/',
                self.admin_site.admin_view(self.override_status_view),
                name='orders_order_override_status',
            ),
            path('<int:pk>/refund/',
                 self.admin_site.admin_view(self.refund_view),
                 name='orders_order_refund')
        ]
        return custom + urls

    def override_status_view(self, request, pk):
        order = get_object_or_404(Order, pk=pk)

        if request.method == 'POST':
            form = OverrideStatusForm(request.POST)
            if form.is_valid():
                try:
                    event = override_order_status(
                        order,
                        new_status=form.cleaned_data['new_status'],
                        changed_by=request.user,
                        note=form.cleaned_data['note'],
                        tracking_number=form.cleaned_data.get('tracking_number', ''),
                    )
                    if event is None:
                        self.message_user(
                            request,
                            'Status unchanged (the order was already in that state)',
                            level=messages.INFO
                        )
                    else:
                        self.message_user(
                            request,
                            f"Order #{order.pk} status overriden to ''{order.status}'",
                            level=messages.SUCCESS
                        )
                    # Redirect to the standard change page so the admin
                    # sees the updated timeline.
                    return redirect(
                        f"admin:orders_order_change", order.pk
                    )
                except TrackingNumberRequired as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                except ValueError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
        else:
            form = OverrideStatusForm(initial={'new_status': order.status})

        context = {
            **self.admin_site.each_context(request),
            'title': f"Override Status for order #{order.pk}",
            'opts': self.model._meta,
            'order': order,
            'form': form,
            'original': order
        }
        return render(
            request,
            'admin/orders/order/override_status.html',
            context
        )

    def refund_link(self, obj):
        if not obj.pk or not obj.is_paied:
            return '-'
        from django.urls import reverse
        from django.utils.html import format_html
        url = reverse('admin:orders_order_refund', args=[obj.pk])
        return format_html('<a class="button" href="{}"> Issue a (partial) refund</a>', url)
    refund_link.short_description = 'Refunds'

    def _refund_allowed(self, request):
        """
        Refunds move money, so they need their own permission (superuser have it).
        """
        if request.user.has_perm('payments.add_refund'):
            return True
        self.message_user(request, "You don't have permission to issue refunds",
                          level=messages.ERROR)
        return False

    def refund_view(self, request, pk):
        if not request.user.has_perm('payments.add_refund'):
            raise PermissionDenied
        order = get_object_or_404(Order, pk=pk)
        already = order.refunded_amount
        remaining = order.total_amount - already
        can_refund = order.is_paied and remaining > 0

        if request.method == 'POST' and can_refund:
            form = RefundForm(request.POST)
            if form.is_valid():
                try:
                    refund = refund_order_to_wallet(
                        order.pk, reason=Refund.Reason.ADMIN,
                        amount=form.cleaned_data['amount'],
                        note=form.cleaned_data['note'],
                        created_by=request.user,
                    )
                except RefundError as exc:
                    self.message_user(request, str(exc), level=messages.ERROR)
                else:
                    self.message_user(
                        request, f"Refunded ${refund.amount} to the customer's wallet",
                        level=messages.SUCCESS
                    )
                    return redirect('admin:orders_order_change', order.pk)
        else:
            form = RefundForm(initial={'amount': remaining if remaining > 0 else None})

        context = {
            **self.admin_site.each_context(request),
            'title': f"Refund for order #{order.pk}",
            'opts': self.model._meta,
            'order': order,
            'original': order,
            'form': form,
            'already_refunded': already,
            'remaining': remaining,
            'can_refund': can_refund,
        }
        return render(request, 'admin/orders/order/refund.html',
                      context)

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

    @admin.action(description='Cancel and refund to customer wallet (for not shipped yet)')
    def cancel_and_refund(self, request, queryset):
        ok = 0

        if not self._refund_allowed(request):
            return

        for order in queryset:
            try:
                cancel_order_and_refund(
                    order.pk, actor=request.user, staff=True,
                    reason=Refund.Reason.ADMIN,
                    note=f"Cancelled by staff ({request.user.username})"
                )
                ok += 1
            except (RefundError, PaymentError, InvalidStatusTransition) as exc:
                self.message_user(request, f"Order #{order.pk}: {exc}", level=messages.WARNING)
        if ok:
            self.message_user(request, f"{ok} order(s) cancelled", level=messages.SUCCESS)

    @admin.action(description='Refund remaining amount to customer wallet (for delivered and compensation)')
    def refund_remaining(self, request, queryset):
        ok = 0

        if not self._refund_allowed(request):
            return

        for order in queryset:
            try:
                refund = refund_order_to_wallet(
                    order.pk, reason=Refund.Reason.ADMIN,
                    note=f"Refunded by staff ({request.user.username})",
                    created_by=request.user
                )
            except RefundError as exc:
                self.message_user(request, f"Order #{order.pk}: {exc}", level=messages.WARNING)
                continue
            if refund is None:
                self.message_user(request, f"Order #{order.pk}: nothing left to refund", level=messages.INFO)
            else:
                ok += 1
        if ok:
            self.message_user(request, f"{ok} refund(s) issued", level=messages.SUCCESS)
        
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