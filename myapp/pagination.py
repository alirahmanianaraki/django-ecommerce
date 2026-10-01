# myapp/pagination.py

from django.core.paginator import Paginator

DEFAULT_PAGE_SIZE = 24

def paginate(request, queryset, per_page=DEFAULT_PAGE_SIZE):
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'paginator': paginator
    }

    return page_obj, context