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


def split_blocks(
    blocks: Iterable[Tuple[int, int, list[Register]]],
    max_count: int,
) -> List[Tuple[int, int, list[Register]]]:
    """Cut contiguous blocks into reads of at most max_count registers.

    Some RS485 gateways and older controllers stop answering, or answer with an
    exception, when one request spans too many registers.
    """
    out: List[Tuple[int, int, list[Register]]] = []
    for _start, _count, regs in blocks:
        for i in range(0, len(regs), max_count):
            part = regs[i : i + max_count]
            out.append((part[0].address, len(part), part))
    return out
