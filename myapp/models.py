from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Create your models here.
class Tag(models.Model):
    name = models.CharField(max_length=100)
    slug = models.SlugField(
        blank=True,
        null=True,
        unique=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def get_absolute_url(self):
        return reverse('myapp:tag', kwargs={
            'slug': self.slug
        })

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Tag.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter = counter + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Product(models.Model):
    title = models.CharField(max_length=150)
    description = models.TextField()
    price = models.DecimalField(
        decimal_places=2,
        max_digits=10
        )
    slug = models.SlugField(
        unique=True,
        blank=True,
        null=True,
    )
    stock = models.SmallIntegerField()
    is_available = models.BooleanField(default=True)
    tag = models.ManyToManyField(
        Tag,
        blank=True,
        related_name='products'
    )
    search_vector = SearchVectorField(null=True, blank=True)

    class Meta:
        indexes = [
            # Full-text search index
            GinIndex(
                fields=['search_vector'],
                name='product_search_vector_idx',
            ),
            # Trigram search index
            GinIndex(
                fields=['title'],
                name='product_title_trgm_idx',
                opclasses=['gin_trgm_ops']
            )
        ]

    def get_absolute_url(self):
        return reverse('myapp:detail', kwargs={
            'slug': self.slug
        })

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.title )
            slug = base_slug
            counter = 1
            while Product.objects.filter(slug=slug).exists():
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)
        # Filling the search_vector field
        Product.objects.filter(pk=self.pk).update(
            search_vector=SearchVector('title', weight='A') + SearchVector('description', weight='B')
        )

    def __str__(self):
        return f'{self.title}--id: {self.pk}'

class ProductImage(models.Model):
    image = models.ImageField(
        upload_to='product_images/',
        default='product_images/ProductPlaceHolderImage.jpg'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name='product_images',
    )

