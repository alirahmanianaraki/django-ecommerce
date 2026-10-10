from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify

# Create your models here.
class Feature(models.Model):
    """Product specification (Brand, color, ...)"""
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(unique=True, blank=True)
    base_unit = models.CharField(
        max_length=25, 
        blank=True,
        help_text="Canonical unit for numeric_value")
    is_filterable = models.BooleanField(default=True)
    is_visible_on_product_page = models.BooleanField(default=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['display_order', 'name']

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.slug:
            base_slug = slugify(self.name)
            slug = base_slug
            counter = 1
            while Feature.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

class FeatureValue(models.Model):
    """A permitted value for a Feature"""
    feature = models.ForeignKey(
        Feature,
        on_delete=models.CASCADE,
        related_name='values'
    )
    value = models.CharField(max_length=200)
    unit = models.CharField(
        max_length=25,
        blank=True,
        help_text="Display unit e.g. TB, GB, MB, or leave blank for not-measured"
    )
    numeric_value = models.DecimalField(
        max_digits=25,
        decimal_places=6,
        null=True,
        blank=True,
        help_text="Optional; the value expressed in the feature\'s base unit"
    )
    slug = models.SlugField(blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ['feature__display_order', 'display_order', 'value']
        unique_together = [('feature', 'value', 'unit')]

    def __str__(self):
        if self.unit:
            return f"{self.feature.name}: {self.value} {self.unit}"
        return f"{self.feature.name}: {self.value}"

    def save(self, *args, **kwargs):
        if not self.slug:
            feature_name = self.feature.name
            slug_parameter = f"{feature_name}-{self.value}"
            if self.unit:
                slug_parameter = f"{slug_parameter}-{self.unit}"
                base_slug = slugify(slug_parameter)
            else:
                base_slug = slugify(slug_parameter)
            slug = base_slug
            counter = 1
            while(
                FeatureValue.objects
                .filter(feature=self.feature, slug=slug)
                .exclude(pk=self.pk)
                .exists()
            ):
                slug = f'{base_slug}-{counter}'
                counter += 1
            self.slug = slug
        super().save(*args, **kwargs)

class ProductFeature(models.Model):
    """The link between the products, features, and values"""
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='features'
    )
    feature = models.ForeignKey(
        Feature,
        on_delete=models.PROTECT,
        related_name='product_features'
    )
    value = models.ForeignKey(
        FeatureValue,
        on_delete=models.PROTECT,
        related_name='product_features'
    )

    class Meta:
        unique_together = [('product', 'feature', 'value')]
        ordering = ['feature__display_order', 'value__display_order']

    def __str__(self):
        return f"{self.product.title} - {self.feature.name}: {self.value.value}"

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

class ProductQuerySet(models.QuerySet):
    """Custom queryset for Product"""
    def with_specs(self):
        """
        Prefetch everything the detail page needs
        to render specifications
        """
        return self.prefetch_related(
            'features__feature',
            'features__value'
        )

class ProductManager(models.Manager.from_queryset(ProductQuerySet)):
    """Manager exposing ProductQueryset's helpers on Product.objects"""

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

    objects = ProductManager()

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

    @property
    def has_visible_specs(self):
        return self.features.filter(
            feature__is_visible_on_product_page=True
        ).exists()

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

