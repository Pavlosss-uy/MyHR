"""
utils/seeding.py — Task 3.10
Standardized seed-setting for reproducible training runs.
"""
import os
import random

import numpy as np
import torch


def set_all_seeds(seed: int = 42) -> None:
    """Set seeds for Python, NumPy, PyTorch (CPU + CUDA) for reproducibility."""
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)
    os.environ["PYTHONHASHSEED"] = str(seed)
