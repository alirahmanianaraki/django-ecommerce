from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse

def send_stock_alert_email(alert):
    """
    Send a "back in stock" notification for a single StockAlert
    """
    recipient = alert.email
    if not recipient:
        return

    product = alert.product
    subject = f"Back in stock: {product.title}"
    product_path = product.get_absolute_url()
    site_url = getattr(settings, 'SITE_URL', "").rstrip('/')
    product_url = f"{site_url}{product_path}" if site_url else product_path

    context = {
        'product': product,
        'product_url': product_url,
        'site_name': 'VoltPC'
    }

    text_body = render_to_string('myapp/email/stock_alert.txt', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient]
    )
    msg.send(fail_silently=False)