from typing import Iterable, Tuple, List

from .register import Register


def group_registers(
    registers: Iterable[Register],
    include_complex_regs: bool,
) -> List[Tuple[int, int, list[Register]]]:

    blocks: List[Tuple[int, int, list[Register]]] = []
    sorted_regs = sorted(
        (
            registers
            if include_complex_regs
            else (r for r in registers if not r.is_complex)
        ),
        key=lambda r: r.address,
    )

    for reg in sorted_regs:
        if not blocks or blocks[-1][0] + blocks[-1][1] != reg.address:
            blocks.append((reg.address, 1, [reg]))
        else:
            start, cnt, lst = blocks[-1]
            blocks[-1] = (start, cnt + 1, lst + [reg])
    return blocks
