from django.shortcuts import render, get_object_or_404, redirect
from apps.store.models import Order


def my_orders(request):

    customer_email = request.session.get(
        "evibe_customer_email"
    )

    if not customer_email:

        return redirect(
            "order_access"
        )

    orders = (Order.objects.filter(
            email=customer_email
        )
        .select_related("invoice")
        .order_by(
            "-created_at"
        )
    )

    return render(
        request,
        "store/my_orders.html",
        {
            "orders": orders
        }
    )

def track_order(
    request,
    order_id
):

    customer_email = request.session.get(
        "evibe_customer_email"
    )

    if not customer_email:

        return redirect(
            "order_access"
        )

    order = get_object_or_404(
        Order,
        id=order_id,
        email=customer_email
    )

    return render(
        request,
        "store/track_order.html",
        {
            "order": order
        }
    )

def order_access(request):

    customer_email = request.session.get(
        "evibe_customer_email"
    )

    if customer_email:

        return redirect(
            "my_orders"
        )

    return render(
        request,
        "store/order_access.html"
    )