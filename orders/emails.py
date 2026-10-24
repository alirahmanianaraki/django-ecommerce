from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils.html import strip_tags

def send_order_confirmation(order, request=None):
    """
    Send an order confirmation email to the user who placed 'order'
    """
    recipient = order.user.email
    if not recipient:
        return

    subject = f"Order confirmation - #{order.pk}"

    context = {
        'order': order,
        'items': order.orderitem_set.all(),
        'order_url': _build_order_url(order, request),
        'site_name': 'VoltPC',
    }
    text_body = render_to_string('orders/email/order_confirmation.txt', context)
    html_body = render_to_string('orders/email/order_confirmation.html', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to={recipient},
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)

def send_status_update_email(order, old_status, new_status):
    """
    Send the customer an email explaining the status change
    """
    recipient = order.user.email
    if not recipient:
        return

    subject_map = {
        'paid': f"Payment recieved for order #{order.pk}",
        'processing': f"Your order #{order.pk} is being prepared",
        'shipped': f"Your order #{order.pk} has shipped",
        'delivered': f"Your order #{order.pk} has been delivered",
        'cancelled': f"Your order #{order.pk} has been cancelled"
    }

    subject = subject_map.get(new_status, f"Order {order.pk} update: {new_status}")
    context = {
        'order': order,
        'old_status': old_status,
        'new_status': new_status,
        'site_name': 'VoltPC',
    }
    text_body = render_to_string('orders/email/status_update.txt', context)
    html_body = render_to_string('orders/email/status_update.html', context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient]
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)

def _build_order_url(order, request):
    """
    Return an absolute URL to the order detail page
    """
    path = reverse("orders:order_detail", kwargs={'pk': order.pk})
    if request is not None:
        return request.build_absolute_uri(path)
    return path