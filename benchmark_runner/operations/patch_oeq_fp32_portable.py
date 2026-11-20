"""Apply the OpenEquivariance compatibility patch used for PyTorch 2.5 FP32 runs."""

from importlib.util import find_spec
from pathlib import Path

import torch


ORIGINAL = "    def register_autocast(cls):\n        global torch\n        import torch\n"
GUARD = "\n        if not hasattr(torch.library, 'register_autocast'):\n            return  # PyTorch 2.5 FP32-only evaluation; autocast is not used.\n"


def main():
    if hasattr(torch.library, "register_autocast"):
        print("The installed PyTorch supports register_autocast.")
        return
    package = find_spec("openequivariance")
    if package is None or package.origin is None:
        raise RuntimeError("Install OpenEquivariance in the evaluation environment first.")
    directory = Path(package.origin).parent / "_torch"
    matched = 0
    for path in sorted(directory.glob("TensorProduct*.py")):
        source = path.read_text()
        if ORIGINAL in source:
            matched += 1
            if ORIGINAL + GUARD not in source:
                path.write_text(source.replace(ORIGINAL, ORIGINAL + GUARD, 1))
    if not matched:
        raise RuntimeError("The installed OpenEquivariance source layout differs from version 0.5.4.")
    print(f"Verified the FP32 compatibility guard in {matched} OpenEquivariance files.")


if __name__ == "__main__":
    main()
