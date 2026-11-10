from django.contrib import admin
from .models import WalletTransaction, Wallet

# Register your models here.
class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

@admin.register(Wallet)
class WalletAdmin(ReadOnlyAdmin):
    list_display = ['user', 'balance', 'updated_at']
    search_fields = ['user__username', 'user__email']

@admin.register(WalletTransaction)
class WalletTransactionAdmin(ReadOnlyAdmin):
    list_display = ['created_at', 'wallet', 'kind', 'amount', 'balance_after', 'order', 'reference']
    list_filter = ['kind', 'created_at']
    search_fields = ['reference', 'wallet__user__username', 'wallet__user__email']
