def evibe_customer(request):

    return {

        "evibe_customer_name":
            request.session.get(
                "evibe_customer_name"
            ),

        "reward_coupon":
            request.session.get(
                "reward_coupon"
            )

    }