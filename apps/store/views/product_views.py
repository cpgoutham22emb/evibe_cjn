from django.shortcuts import render, get_object_or_404
from apps.store.models import Product, Category, ProductVariant
from apps.analytics.models import ProductView
from django.http import HttpRequest


def product_list(request):

    from django.db.models import F

    products = Product.objects.filter(active=True).order_by(
        F('all_products_order').asc(nulls_last=True)
    )[:6]

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

    new_arrivals = Product.objects.filter(
    active=True,
    is_new_arrival=True
    ).order_by('new_arrival_order')[:6]

    return render(request, "store/product_list.html", {
        "products": products,
        "featured_products": featured_products,
        "best_sellers": best_sellers,
        "new_arrivals": new_arrivals,
    })

def get_user_city(request):
    """
    Basic city detection for now.
    Later we can improve using IP-based geo lookup.
    """

    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if forwarded_for:
        ip = forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    # Localhost testing fallback
    if ip in ["127.0.0.1", "localhost", None]:
        return "Bangalore"

    # Temporary fallback
    return "Unknown"

def product_detail(request, slug):

    product = get_object_or_404(Product, slug=slug)

    session_id = request.session.session_key

    if not session_id:
        request.session.create()
        session_id = request.session.session_key

    city = get_user_city(request)

    already_viewed = ProductView.objects.filter(
        product=product,
        session_id=session_id
    ).exists()

    if not already_viewed:
        ProductView.objects.create(
            product=product,
            session_id=session_id,
            city=city
        )

    return render(request, "store/product_detail.html", {
        "product": product
    })

def category_products(request, slug):

    category = get_object_or_404(Category, name__iexact=slug)

    products = Product.objects.filter(
        category=category,
        active=True
    ).prefetch_related('images')

    size = request.GET.get('size')

    if size:
        products = products.filter(variants__size=size)

    products = products.order_by(
        F('all_products_order').asc(nulls_last=True),
        '-created_at'
    ).distinct()

    available_sizes = ProductVariant.objects.filter(
    product__category=category,
    product__active=True
    ).values_list(
        'size',
        flat=True
    ).distinct().order_by('size')

    return render(request, "store/category.html", {
        "category": category,
        "products": products,
        "available_sizes": available_sizes,
        "selected_size": size   
    })

from django.db.models import F

def all_products(request):

    products = Product.objects.filter(
        active=True
    ).prefetch_related('images')

    size = request.GET.get('size')

    if size:
        products = products.filter(
            variants__size=size
        )

    products = products.order_by(
        F('all_products_order').asc(nulls_last=True)
    ).distinct()

    available_sizes = ProductVariant.objects.filter(
        product__active=True
    ).values_list(
        'size',
        flat=True
    ).distinct().order_by('size')

    return render(request, 'store/all_products.html', {
        'products': products,
        'available_sizes': available_sizes,
        'selected_size': size
    })