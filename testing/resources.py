from __future__ import annotations

import os.path
from functools import cache
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from _typeshed import OpenTextMode


HERE = os.path.dirname(__file__)


@cache
def resource(*path: str, mode: OpenTextMode = "r") -> str:
    with open(os.path.join(HERE, "fixtures", *path), mode) as f:
        return f.read()
