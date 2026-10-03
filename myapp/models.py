from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Create your models here.
class Category(models.Model):
    """Hierarchical product categories with optional parent"""
    name = models.CharField(max_length=100)
    slug = models.SlugField(
        unique=True,
        blank=True,
        null=True
        )
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='children'
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Category.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()

        # Rule 1: a category can't be its own parent
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError({'parent': "A category can't be its own parent."})

        # Rule 2: No cycle - walk up from the proposed parent
        ancestor = self.parent
        while ancestor is not None:
            if ancestor.pk == self.pk:
                raise ValidationError({
                    'parent': "This creates a cycle in the category tree"
                })
            ancestor = ancestor.parent

    def get_absolute_url(self):
        return reverse('myapp:category', kwargs={
            'slug': self.slug
        })

    @property
    def is_root(self):
        return self.parent_id is None

    @property
    def full_path(self):
        """Return 'Root > Child > Grandchild"""
        names = [self.name]
        ancestor = self.parent
        while ancestor is not None:
            names.append(ancestor.name)
            ancestor = ancestor.parent
        return " -> ".join(reversed(names))

    def get_descendants(self, include_self=False):
        """
        Return a list of this category and all its descendants.
        Uses breadth-first traversal (BFT) to gather children, grandchildren, etcs.
        """
        result = [self] if include_self else []
        to_visit = list(self.children.all())
        while to_visit:
            current = to_visit.pop(0)
            result.append(current)
            to_visit.extend(current.children.all())

        return result
    
    def get_ancestors(self):
        ancestors = []
        ancestor = None
        if self.parent:
            ancestor = self.parent
        while ancestor is not None:
            ancestors.append(ancestor)
            ancestor = ancestor.parent
        return list(reversed(ancestors))


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
    category = models.ManyToManyField(
        'Category',
        blank=True,
        related_name='products',
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

