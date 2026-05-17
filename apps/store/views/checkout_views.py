from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db import transaction
from django.conf import settings

import razorpay

from apps.store.models import Order, OrderItem
from apps.store.core.cart_manager import Cart

from django.utils import timezone
from apps.customer_engagement.models import CustomerLead, RewardCoupon

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

        shipping_charge = 0 if subtotal > 999 else 99

        reward_coupon = None

        reward_discount = 0

        final_total = subtotal + shipping_charge

        # =========================
        # EVIBE AUTO REWARD
        # =========================

        customer_email = request.session.get("evibe_customer_email")

        if customer_email:

            print("SESSION EMAIL:", customer_email)

            lead = CustomerLead.objects.filter(
                email=customer_email
            ).first()

            print("LEAD:", lead)

            if lead:

                coupons = RewardCoupon.objects.filter(
                    customer=lead
                )

                print("ALL COUPONS:", coupons)

                reward_coupon = RewardCoupon.objects.filter(
                    customer=lead,
                    is_used=False,
                    valid_till__gte=timezone.now()
                ).first()

                print("FINAL COUPON:", reward_coupon)

                if reward_coupon:

                    reward_discount = (
                        subtotal * reward_coupon.discount_percentage  
                    ) / 100

                    final_total = final_total - reward_discount

        return render(request, "store/checkout.html", {
            "items": items,
            "cart": cart,
            "mrp_total": mrp_total,
            "savings": savings,
            "shipping_charge": shipping_charge,
            "reward_coupon": reward_coupon,
            "reward_discount": reward_discount,
            "final_total": final_total
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

        reward_discount = 0

        reward_coupon = None

        total_amount = subtotal + shipping_charge

        # =========================
        # EVIBE REWARD
        # =========================

        customer_email_session = request.session.get(
            "evibe_customer_email"
        )

        if customer_email_session:

            lead = CustomerLead.objects.filter(
                email=customer_email_session
            ).first()

            if lead:

                reward_coupon = RewardCoupon.objects.filter(
                    customer=lead,
                    is_used=False,
                    valid_till__gte=timezone.now()
                ).first()

                if reward_coupon:

                    reward_discount = (
                        subtotal * reward_coupon.discount_percentage
                    ) / 100

                    total_amount = total_amount - reward_discount

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
                total_amount=total_amount,
                reward_discount=reward_discount,
                reward_coupon_code=reward_coupon.coupon_code if reward_coupon else None
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

        # =========================
        # MARK REWARD USED
        # =========================

        if reward_coupon:

            reward_coupon.is_used = True

            reward_coupon.save()

        cart.clear()

        return redirect('/order-success/')


def order_success(request):

    return render(request, "store/order_success.html")