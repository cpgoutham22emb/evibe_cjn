from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages

from .models import Product, Order, OrderItem, Category, ProductVariant
from .cart import Cart

import json
import razorpay
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.conf import settings
from django.db import transaction
from django.core.mail import send_mail


# -----------------------
# PRODUCT LIST
# -----------------------
def product_list(request):
    products = Product.objects.filter(active=True)

    featured_products = Product.objects.filter(
        is_featured=True,
        active=True,
        featured_order__isnull=False
    ).order_by('featured_order')[:6]

    best_sellers = Product.objects.filter(
    is_best_seller=True,
    active=True,
    best_seller_order__isnull=False
    ).order_by('best_seller_order')[:6]

    
    return render(request, "store/product_list.html", {
        "products": products,
        "featured_products": featured_products,
        "best_sellers": best_sellers,
    })

def product_detail(request, slug):
    product = get_object_or_404(Product, slug=slug)

    return render(request, "store/product_detail.html", {
        "product": product
    })

# -----------------------
# Category Products
# -----------------------
def category_products(request, slug):
    category = get_object_or_404(Category, name=slug)
    products = category.products.filter(active=True)

    return render(request, "store/category.html", {
        "category": category,
        "products": products
    })

# -----------------------
# CHECKOUT (GET + POST)
# -----------------------
@require_http_methods(["GET", "POST"])
def checkout(request):
    cart = Cart(request)
    items = cart.get_items()

    if not items:
        return redirect('/cart/')

    # GET → show checkout form
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

    # POST → place order
    if request.method == "POST":
        customer_name = request.POST.get('customer_name')
        phone = request.POST.get('phone')
        email = request.POST.get('email')
        address = request.POST.get('address')
        city = request.POST.get('city')
        pincode = request.POST.get('pincode')
        payment_method = request.POST.get('payment_method')

        # Calculate subtotal
        subtotal = 0

        for item in items:
            variant = item['variant']
            quantity = item['quantity']

            # 🔹 Refresh latest stock from database
            variant.refresh_from_db()
            if variant.stock < quantity:
               from django.contrib import messages
               messages.error(request, "Some items are out of stock")
               return redirect('/cart/')
            subtotal += variant.product.get_final_price() * quantity

        # Shipping logic
        if subtotal > 999:
            shipping_charge = 0
        else:
            shipping_charge = 99

        total_amount = subtotal + shipping_charge


        # Atomic transaction ensures order + items are created together
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
            

            # Create order items
            for item in items:
                OrderItem.objects.create(
                    order=order,
                    product=item['product'],
                    variant=item['variant'],
                    quantity=item['quantity'],
                    price=item['product'].get_final_price()
                )  

        # ONLINE PAYMENT
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

        # COD
        cart.clear()
        return redirect('/order-success/')


# -----------------------
# ORDER SUCCESS
# -----------------------
def order_success(request):
    return render(request, "store/order_success.html")


# -----------------------
# CART VIEWS
# -----------------------
def add_to_cart(request):

    if request.method == "POST":
        variant_id = request.POST.get("variant_id")
        variant = ProductVariant.objects.filter(id=variant_id).first()

        if not variant:
            messages.error(request, "Invalid product variant.")
            return redirect('/')

        if variant.stock <= 0:
            messages.error(request, "Product out of stock.")
            return redirect('/')

        cart = Cart(request)
        cart.add(variant_id)

    return redirect('cart')

def remove_from_cart(request, variant_id):
    cart = Cart(request)
    cart.remove(variant_id)
    return redirect('cart')

def increase_quantity(request, variant_id):
    cart = Cart(request)
    cart.increase(variant_id)
    return redirect('cart')


def decrease_quantity(request, variant_id):
    cart = Cart(request)
    cart.decrease(variant_id)
    return redirect('cart')

def cart_detail(request):
    cart = Cart(request)
    items = cart.get_items()
    mrp_total = 0
    subtotal = 0
    savings =0
    
    for item in items:
        mrp_total += item['product'].mrp * item['quantity']
        subtotal += item['product'].get_final_price() * item['quantity']
        savings = mrp_total - subtotal
    return render(request, 'store/cart.html', {'items': items, 'cart': cart, 'mrp_total': mrp_total, 'subtotal': subtotal, 'savings': savings})

# -----------------------
# Payment Success
# -----------------------
@csrf_exempt
def payment_success(request):

    if request.method == "POST":

        razorpay_order_id = request.POST.get("razorpay_order_id")
        razorpay_payment_id = request.POST.get("razorpay_payment_id")
        razorpay_signature = request.POST.get("razorpay_signature")

        try:

            # Safe order lookup
            order = get_object_or_404(
                Order,
                razorpay_order_id=razorpay_order_id
            )

            client = razorpay.Client(
                auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
            )

            # Verify Razorpay signature
            client.utility.verify_payment_signature({
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature
            })


            # Idempotent payment check
            if order.status != "PAID":

                order.razorpay_payment_id = razorpay_payment_id
                order.razorpay_signature = razorpay_signature
                order.status = "PAID"
                order.save()


                # Send confirmation email
                send_mail(
                    subject=f"EVIBE Order #{order.id} Confirmed",
                    message=f"""
Hi {order.customer_name},

Thank you for shopping with EVIBE.

Your order has been placed successfully.

Order ID: {order.id}
Total Amount: ₹{order.total_amount}

We will notify you once your order is shipped.

Thanks,
EVIBE Team
""",
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[order.email],
                    fail_silently=True,
                )


                # Safe stock reduction with row lock

                with transaction.atomic():

                    for item in order.items.all():
                        variant = ProductVariant.objects.select_for_update().get(
                            id=item.variant.id
                        )

                        if variant.stock >= item.quantity:
                            variant.stock -= item.quantity
                            variant.save()
                        else:
                            order.status = "CANCELLED"
                            order.save()


            # Clear cart
            from .cart import Cart
            cart = Cart(request)
            cart.clear()

            return redirect('/order-success/')


        except razorpay.errors.SignatureVerificationError:

            order.status = "CANCELLED"
            order.save()

            return render(request, "store/payment_failed.html")


    return redirect('/')

# -----------------------
# Webhook for Razorpay payment capture
# -----------------------
@csrf_exempt
def razorpay_webhook(request):

    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    payload = request.body
    signature = request.headers.get("X-Razorpay-Signature")

    client = razorpay.Client(
        auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
    )

    try:
        # Verify webhook signature
        client.utility.verify_webhook_signature(
            payload,
            signature,
            webhook_secret
        )

        data = json.loads(payload)

        if data["event"] == "payment.captured":

            payment = data["payload"]["payment"]["entity"]

            razorpay_order_id = payment["order_id"]
            razorpay_payment_id = payment["id"]

            try:
                order = Order.objects.get(
                    razorpay_order_id=razorpay_order_id
                )
            except Order.DoesNotExist:
                return HttpResponse(status=200)

            # Prevent duplicate webhook processing
            if order.status == "PAID":
                return HttpResponse(status=200)

            order.razorpay_payment_id = razorpay_payment_id
            order.status = "PAID"
            order.save()

            #  Safe stock deduction
            with transaction.atomic():

                for item in order.items.all():
                    variant = ProductVariant.objects.select_for_update().get(
                        id=item.variant.id
                    )

                    if variant.stock >= item.quantity:
                        variant.stock -= item.quantity
                        variant.save()
                    else:
                        order.status = "CANCELLED"
                        order.save()

        return HttpResponse(status=200)

    except Exception as e:
        print("Webhook error:", e)
        return HttpResponse(status=400)

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