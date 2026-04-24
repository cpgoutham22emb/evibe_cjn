from django.shortcuts import render, redirect
from django.contrib import messages
from apps.store.core.cart_manager import Cart
from apps.store.models import ProductVariant


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

    for item in items:

        mrp_total += item['product'].mrp * item['quantity']
        subtotal += item['product'].get_final_price() * item['quantity']

    savings = mrp_total - subtotal

    return render(request, 'store/cart.html', {
        'items': items,
        'cart': cart,
        'mrp_total': mrp_total,
        'subtotal': subtotal,
        'savings': savings
    })