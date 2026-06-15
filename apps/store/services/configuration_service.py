from apps.store.models import StoreConfiguration


def get_store_config():

    config = StoreConfiguration.objects.first()

    if not config:
        raise ValueError(
            "StoreConfiguration not found"
        )

    return config