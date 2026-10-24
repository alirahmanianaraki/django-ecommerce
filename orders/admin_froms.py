from django import forms
from .models import Order

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

    def clear(self):
        cleaned = super().clean()
        new_status = cleaned.get('new_status')
        tracking_number = (cleaned.get('tracking_number')or '').strip()

        if new_status == Order.Status.SHIPPED and not tracking_number:
            self.add_error(
                'tracking_number',
                'A tracking number is required to mark an order as shipped'
            )
        return cleaned