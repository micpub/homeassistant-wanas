from __future__ import annotations

from typing import Callable, Any
from dataclasses import dataclass


@dataclass(frozen=True)
class Register:
    """One Modbus register."""

    address: int  # 0-based Modbus address
    name: str  # logical name -> dataclass field
    converter: Callable[[int], Any]  # raw -> Python value
    min: int
    max: int
    writable: bool = False  # True -> will also expose write helper
    write_value_step: int = 1
    write_converter: Callable[[Any], int] | None = None
