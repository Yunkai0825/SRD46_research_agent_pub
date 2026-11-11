"""Output archive locations mirror each benchmark or user-output directory."""
from ..packing import Store
from ..unpack_images import check_rel


class PartRoot:
    """Provide the shared ZIP reader with a run's part directory."""

    def __init__(self, directory):
        self.directory = directory

    def __truediv__(self, name):
        if name != "zips":
            raise ValueError("Expected the ZIP part directory")
        return self.directory


class OutputStore(Store):
    def __init__(self, root, target):
        super().__init__(root)
        self.zips = self.root / "zips" / check_rel(target, "output target")
        self.part_root = PartRoot(self.zips)
