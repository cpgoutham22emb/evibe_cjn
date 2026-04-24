from django.shortcuts import render, get_object_or_404
from apps.store.models import Product, Category
from apps.analytics.models import ProductView

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

    # SESSION BASED TRACKING
    session_id = request.session.session_key

    if not session_id:
        request.session.create()
        session_id = request.session.session_key

    # CHECK IF ALREADY VIEWED
    already_viewed = ProductView.objects.filter(
        product=product,
        session_id=session_id
    ).exists()

    if not already_viewed:
        ProductView.objects.create(
            product=product,
            session_id=session_id
        )

    return render(request, "store/product_detail.html", {
        "product": product
    })


def category_products(request, slug):

    category = get_object_or_404(Category, name=slug)

    products = category.products.filter(active=True)

    return render(request, "store/category.html", {
        "category": category,
        "products": products
    })