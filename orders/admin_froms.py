# Correct name should be 'admin_forms.py'
from decimal import Decimal

from django import forms

from .models import Order

class RefundForm(forms.Form):
    amount = forms.DecimalField(
        max_digits=10, decimal_places=2,
        min_value=Decimal('0.01'),
        help_text='Amount to return to the customer wallet',
    )
    note = forms.CharField(
        max_length=200,
        help_text='Shown to the customer in their wallet history. Keep it polite and short.'
    )

class OverrideStatusForm(forms.Form):
    new_status = forms.ChoiceField(choices=Order.Status.choices)
    note = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}),
        help_text='Required. This will appear in the customer timeline'
    )
    tracking_number = forms.CharField(
        required=False,
        help_text='Only used when moving to shipped status'
    )

    def clean(self):
        cleaned = super().clean()
        new_status = cleaned.get('new_status')
        tracking_number = (cleaned.get('tracking_number')or '').strip()

        if new_status == Order.Status.SHIPPED and not tracking_number:
            self.add_error(
                'tracking_number',
                'A tracking number is required to mark an order as shipped'
            )
        return cleaned