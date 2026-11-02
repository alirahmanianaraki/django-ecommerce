
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from .comparison import Comparison, build_comparison_table, MAX_COMPARE
from .models import Product

def comparison_page(request):
    comparison = Comparison(request)
    products = list(comparison)
    table = build_comparison_table(products)
    return render(request, 'myapp/comparison.html',
                  {
                      'table': table,
                      'comparison_max': MAX_COMPARE
                  })

@require_POST
def add_to_comparison(request):
    product_id = request.POST.get('product_id')
    if not product_id:
        return JsonResponse(
            {'success': False, 'error': 'Product id is required'},
            status=400
        )
    comparison = Comparison(request)
    result = comparison.add(product_id)

    if result['added']:
        return JsonResponse({
            'success': True,
            'count': len(comparison),
            'message': 'Added to comparison',
        })
    reason = result['reason']
    if reason == 'duplicate':
        return JsonResponse({
            'success': True,
            'count': len(comparison),
            'message': 'Already in comparison'
        })
    if reason == 'full':
        return JsonResponse({
            'success': False,
            'error': f"You can compare up to {MAX_COMPARE} products at a time",
        }, status=400)
    return JsonResponse({
        'success': False,
        'error': 'Product not found',
    }, status=400)


@require_POST
def remove_from_comparison(request):
    product_id = request.POST.get('product_id')

    if not product_id:
        return JsonResponse({
            'success': False,
            'error': 'Product id is required',
        }, status=400)

    comparison = Comparison(request)
    removed = comparison.remove(product_id)
    if removed:
        return JsonResponse({
            'success': True,
            'removed': removed,
            'count': len(comparison)
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Product not in comparison',
            'removed': False,
            'count': len(comparison)
        }, success=404)

