from django.contrib import admin
from .models import StripeWebhookEvent
# Register your models here.

@admin.register(StripeWebhookEvent)
class StripeWebhookEventAdmin(admin.ModelAdmin):
    list_display = ['event_id', 'event_type', 'received_at']
    list_filter = ['event_type']
    search_fields = ['event_id']
    readonly_fields = ['event_id', 'event_type', 'received_at']

    def has_add_permission(self, request):
        return False
