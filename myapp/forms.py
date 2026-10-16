from django import forms
from django.core.validators import MaxValueValidator, MinValueValidator
from .models import Review

class ReviewForm(forms.ModelForm):
    rating = forms.IntegerField(
        min_value=1,
        max_value=5,
        widget=forms.HiddenInput(),
    )

    class Meta:
        model = Review
        fields = ['rating', 'title', 'body']
        widgets = {
            'title': forms.TextInput(attrs={
                'placeholder': 'Summerize your experience (optional)',
                'maxlength': 120,
            }),
            'body': forms.Textarea(attrs={
                'rows': 4,
                'placeholder': 'What did you think of this product? (optional)',
            }),
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        return title

    def clean_body(self):
        body = self.cleaned_data.get('body', '').strip()
        return body

    def clean(self):
        cleaned_data = super().clean()
        title = cleaned_data.get('title', '').strip()
        body = cleaned_data.get('body', '').strip()

        if title and not body:
            self.add_error('body', 'Please provide a body if you provide a title.')
        elif body and not title:
            self.add_error('title', 'Please provide a title if you provide a body.')
        
        return cleaned_data