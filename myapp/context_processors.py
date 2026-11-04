from .models import Category
from .comparison import Comparison, MAX_COMPARE
from .recently_viewed import RecentlyViewed

def top_categories(request):
    return{
        'top_categories': (
            Category.objects
            .filter(parent__isnull=True)
            .exclude(slug='uncategorized')
        )
    }

def comparison(request):
    """
    Inject a Comparison instance + the cap into every template
    """
    cmp = Comparison(request)
    return {
        'comparison': cmp,
        'comparison_ids': {int(i) for i in cmp.ids},
        'comparison_max': MAX_COMPARE
    }

def recently_viewed(request):
    """
    Inject a RecentlyViewed instance into every template
    """
    return {'recently_viewed': RecentlyViewed(request)}
