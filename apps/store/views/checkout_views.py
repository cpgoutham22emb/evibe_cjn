from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from django.conf import settings

import razorpay

from apps.store.models import Order, OrderItem
from apps.store.core.cart_manager import Cart


@require_http_methods(["GET", "POST"])
def checkout(request):

    cart = Cart(request)

    items = cart.get_items()

    if not items:
        return redirect('/cart/')

    if request.method == "GET":

        subtotal = cart.get_total_price()
        mrp_total = cart.get_total_mrp()

        savings = mrp_total - subtotal

        return render(request, "store/checkout.html", {
            "items": items,
            "cart": cart,
            "mrp_total": mrp_total,
            "savings": savings
        })

    if request.method == "POST":

        customer_name = request.POST.get('customer_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address = request.POST.get('address')
        city = request.POST.get('city')
        pincode = request.POST.get('pincode')
        payment_method = request.POST.get('payment_method')

        subtotal = cart.get_total_price()

        shipping_charge = 0 if subtotal > 999 else 99

        total_amount = subtotal + shipping_charge

        with transaction.atomic():

            order = Order.objects.create(
                customer_name=customer_name,
                phone=phone,
                email=email,
                address=address,
                city=city,
                pincode=pincode,
                payment_method=payment_method,
                status='CREATED',
                subtotal=subtotal,
                shipping_charge=shipping_charge,
                total_amount=total_amount
            )

            for item in items:

                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    variant=item['variant'],
                    quantity=item['quantity'],
                    price=item['product'].get_final_price()
                )

        if payment_method == "ONLINE":

            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            razorpay_order = client.order.create({
                "amount": int(total_amount * 100),
                "currency": "INR",
                "payment_capture": "1"
            })

            order.razorpay_order_id = razorpay_order["id"]
            order.save()

            return render(request, "store/razorpay_checkout.html", {
                "order": order,
                "razorpay_key": settings.RAZORPAY_KEY_ID,
                "razorpay_order_id": razorpay_order["id"],
                "amount": int(total_amount * 100),
                "customer_name": customer_name,
                "phone": phone,
            })

        cart.clear()

        return redirect('/order-success/')


def order_success(request):

    return render(request, "store/order_success.html")