import os
import sys

def get_asset_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)


def get_patches_path():
    """Directory containing sitecustomize.py injected into child Python processes."""
    return get_asset_path("compyctor_patches")