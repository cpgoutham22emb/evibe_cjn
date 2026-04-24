from django.shortcuts import render, get_object_or_404
from apps.store.models import Order


def my_orders(request):

    orders = None

    if request.method == "POST":

        phone = request.POST.get("phone")

        orders = Order.objects.filter(
            phone=phone
        ).order_by("-created_at")

    return render(request, "store/my_orders.html", {
        "orders": orders
    })


def track_order(request, order_id):

    order = get_object_or_404(Order, id=order_id)

    return render(request, "store/track_order.html", {
        "order": order
    })