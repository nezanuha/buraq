"""
Number formatting utilities — grouping, decimals and localisation.

Usage::

    from buraq.utils.numberformat import format as format_number

    format_number(1234567.89, ".", ",", 2)  # → "1,234,567.89"
"""
from __future__ import annotations

from decimal import Decimal


def format(
    number,
    decimal_sep: str = ".",
    decimal_pos: int | None = None,
    grouping: int = 3,
    thousand_sep: str = ",",
    force_grouping: bool = False,
    use_l10n: bool | None = None,
) -> str:
    """
    Format a number into a string with optional decimal and thousand separators.

    ``decimal_pos`` — number of decimal places (None = keep all).
    ``grouping``    — digits per group in the integer part (usually 3).
    ``force_grouping`` — apply thousand_sep even when grouping=0.
    """
    use_grouping = grouping > 0 or force_grouping
    sign = ""
    if isinstance(number, Decimal):
        if decimal_pos is not None:
            number = number.quantize(Decimal(10) ** -decimal_pos)
        str_number = str(number)
    else:
        str_number = f"{number:.{decimal_pos}f}" if decimal_pos is not None else str(number)

    if str_number.startswith("-"):
        sign = "-"
        str_number = str_number[1:]

    if "." in str_number:
        int_part, dec_part = str_number.split(".", 1)
    else:
        int_part, dec_part = str_number, ""

    if decimal_pos is not None:
        dec_part = dec_part[:decimal_pos].ljust(decimal_pos, "0")

    if use_grouping and grouping:
        chunks = []
        while int_part:
            chunks.append(int_part[-grouping:])
            int_part = int_part[:-grouping]
        int_part = thousand_sep.join(reversed(chunks))

    result = int_part
    if dec_part:
        result += decimal_sep + dec_part

    return sign + result
