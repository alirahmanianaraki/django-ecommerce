from decimal import Decimal
from django.core.management.base import BaseCommand, CommandError
from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from wallets.models import Wallet

class Command(BaseCommand):
    help = 'Verify that every wallet balance equals the sum of its ledger entries'

    def handle(self, *args, **options):
        money = DecimalField(max_digits=12, decimal_places=2)
        broken = (
            Wallet.objects
            .annotate(ledger_total=Coalesce(
                Sum('transactions__amount'), Value(Decimal('0.00'), output_field=money),
                output_field=money
            )).exclude(balance=F('ledger_total'))
        )
        if not broken.exists():
            self.stdout.write(self.style.SUCCESS('All wallets are consistent'))
            return
        for wallet in broken:
            self.stderr.write(
                f"Wallet {wallet.pk} (user {wallet.user_id}): balance {wallet.balance} "
                f"but ledger says {wallet.ledger_total}"
            )
        raise CommandError(f"{broken.count()} wallet(s) are inconsistent!")
