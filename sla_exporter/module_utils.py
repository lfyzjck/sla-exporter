import logging


def register_module(module_cls_registry: dict, name: str):
    def wrapper(cls):
        module_cls_registry[name] = cls
        logging.info(f"register module {cls} as {name}")
        return cls

    return wrapper
