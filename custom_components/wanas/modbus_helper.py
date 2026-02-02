from typing import Iterable, Tuple, List

from .register import Register


def group_registers(
    registers: Iterable[Register],
) -> List[Tuple[int, int, list[Register]]]:

    blocks: List[Tuple[int, int, list[Register]]] = []
    sorted_regs = sorted(registers, key=lambda r: r.address)

    for reg in sorted_regs:
        if not blocks or blocks[-1][0] + blocks[-1][1] != reg.address:
            blocks.append((reg.address, 1, [reg]))
        else:
            start, cnt, lst = blocks[-1]
            blocks[-1] = (start, cnt + 1, lst + [reg])
    return blocks
