from django.shortcuts import render, get_object_or_404
from .models import ProductImage, Product, Tag

# Create your views here.
def index(request):
    products = Product.objects.all()
    return render(request, 'myapp/index.html', 
                  {
                      'products': products,
                  })

def detail(request, slug):
    product = get_object_or_404(Product,
                                slug=slug)
    return render(request, 'myapp/detail.html',
                  {
                      'product': product
                  })

def tag(request, slug):
    tag = get_object_or_404(Tag, slug=slug)
    related_products = Product.objects.filter(tag=tag).prefetch_related('product_images')
    return render(request,'myapp/tagged-products.html',
                  {
                      'related_products': related_products,
                      'tag': tag
                  })