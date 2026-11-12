from django.contrib import admin
from .models import StripeWebhookEvent, TopUp
# Register your models here.

@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'received_at']
    list_filter = ['event_type']
    search_fields = ['event_id']
    readonly_fields = ['event_id', 'event_type', 'received_at']

    def has_add_permission(self, request):
        return False

@admin.register(TopUp)
class TopUpAdmin(admin.ModelAdmin):
    list_display = ['pk', 'user', 'amount', 'currency', 'status', 
                    'created_at', 'completed_at', ]
    list_filter = ['status', 'created_at']
    search_fields = ['user__username', 'user__email',
                     'stripe_checkout_session_id', 'stripe_payment_intent_id']

    # Top-ups are written only by the code, never by hand.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
    
