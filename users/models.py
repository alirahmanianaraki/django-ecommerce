from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Address(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='user_address'
    )
    title = models.CharField(max_length=100)
    full_name = models.CharField(max_length=100)
    description = models.TextField()
    city = models.CharField(max_length=150)
    state = models.CharField(max_length=150)
    postal_code = models.CharField(max_length=50)
    country = models.CharField(max_length=150)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'User: {self.user} | Under name: {self.full_name} | Title: {self.title}'