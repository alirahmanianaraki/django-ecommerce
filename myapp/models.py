from django.contrib.postgres.search import SearchVectorField, SearchVector
from django.contrib.postgres.indexes import GinIndex
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse
from django.utils.text import slugify
from django.contrib.auth.models import User
from django.db.models import Q
from django.utils import timezone
from decimal import Decimal

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

class StockAlert(models.Model):
    """
    A request to be notified when a product is back in stock
    """
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='stock_alerts'
    )
    email = models.EmailField()
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['product', 'notified_at']),
        ]

    def __str__(self):
        status = 'notified' if self.notified_at else 'waiting'
        return f"{self.email} - {self.product.title} ({status})"

class Review(models.Model):
    product = models.ForeignKey(
        'Product',
        on_delete=models.CASCADE,
        related_name='reviews'
    )
    user = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='product_reviews'
    )
    rating = models.PositiveSmallIntegerField()
    title = models.CharField(max_length=120, blank=True)
    body = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('product', 'user')]
        constraints = [
            models.CheckConstraint(
                condition=Q(rating__gte=1) & Q(rating__lte=5),
                name='review_rating_between_1_and_5',
            ),
        ]

    def __str__(self):
        return f"{self.product.title} - {self.rating}★ by {self.user.username} "

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
    discount_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Leave blank if this product is not on sale. Must be lower than 'price'"
    )
    discount_starts_at = models.DateTimeField(null=True, blank=True)
    discount_ends_at = models.DateTimeField(null=True, blank=True)
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
    avg_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0
    )
    rating_count = models.PositiveSmallIntegerField(default=0)

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

    def clean(self):
        super().clean()
        if self.discount_price is not None:
            if self.discount_price <= 0:
                raise ValidationError(
                    {'discount_price': "Discount price must be greater than 0"}
                )
            if self.price is not None and self.discount_price >= self.price:
                raise ValidationError(
                    {'discount_price': 'Discount price must be lower than the regular price'}
                )
            if (
                self.discount_starts_at
                and self.discount_ends_at
                and self.discount_starts_at >= self.discount_ends_at
            ):
                raise ValidationError(
                    {'discount_ends_at': 'Sale end date must be after the start date'}
                )

    def __str__(self):
        return f'{self.title}--id: {self.pk}'

    @property
    def has_visible_specs(self):
        return self.features.filter(
            feature__is_visible_on_product_page=True
        ).exists()

    @property
    def has_discount(self):
        """
        True if a valid discount_price is set AND we're inside the sale window
        """
        if not self.discount_price:
            return False
        if self.discount_price >= self.price:
            return False
        now = timezone.now()
        if self.discount_starts_at and now < self.discount_starts_at:
            return False
        if self.discount_ends_at and now > self.discount_ends_at:
            return False
        return True

    def get_effective_price(self):
        """
        The price a customer actually pays.
        Falls back to 'price' when there's no active discount.
        """
        if self.has_discount:
            return self.discount_price
        return self.price

    @property
    def discount_percent(self):
        """
        Rounded integer percent off
        """
        if not self.has_discount:
            return 0
        saving = self.price - self.discount_price
        return int((saving / self.price) * 100)

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

class Coupon(models.Model):
    """
    A discount code that can be applied to a cart
    """
    class DiscountType(models.TextChoices):
        PERCENT = 'percent', 'Percentage'
        FIXED = 'fixed', 'Fixed amount'

    code = models.CharField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    discount_type = models.CharField(
        max_length=10,
        choices=DiscountType.choices,
        default=DiscountType.PERCENT
    )
    value = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Percent (0-100) for 'percent', or amount for 'fixed'.",
    )
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
        help_text="Minimum cart subtotal to use this coupon"
    )
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text='Leave blank for unlimited uses'
    )
    used_count = models.PositiveIntegerField(default=0)
    one_per_user = models.BooleanField(
        default=False,
        help_text='If ture, each user may redeem this coupon only once'
    )
    is_active= models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(
                condition=Q(value__gt=0),
                name='coupon_value_positive'
            )
        ]

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()}: {self.value})"

    def save(self, *args, **kwargs):
        if self.code:
            self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.discount_type == self.DiscountType.PERCENT and self.value > 100:
            raise ValidationError(
                {'value': 'A percentage coupon cannot exceed 100%'}
            )
        if self.valid_from and self.valid_until and self.valid_from >= self.valid_until:
            raise ValidationError(
                {'valid_unitl': "valid_until must be after valid_from"}
            )

    @property
    def is_currently_valid(self):
        """Time-window check"""
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return False
        return True

    def calculate_discount(self, subtotal):
        """
        Return the dollar amount to subtract from 'subtotal'.
        """
        subtotal = Decimal(subtotal)
        if subtotal <= 0:
            return Decimal('0.00')

        if self.discount_type == self.DiscountType.PERCENT:
            raw = subtotal * (self.value / Decimal('100'))
        else:
            raw = self.value

        # Never discount below zero, and never above the subtotal
        return min(raw, subtotal).quantize(Decimal('0.01'))

