r"""
zip_images -- turn the committed files of a git repository into compartmented zip images (< 100 MB each)
and build a working folder, with its Python environment, from those zips alone.

    python -m zip_images plan   --commit HEAD
    python -m zip_images pack   --commit HEAD --store D:\images
    python -m zip_images verify --store D:\images
    python -m zip_images prune  --store D:\images --keep 2 [--yes]
    python -m zip_images unpack --images D:\images --dest ./app        (= the store's unpack_images.py)

See README.md in this folder. Standard library only.
"""

VERSION = "1.0"
