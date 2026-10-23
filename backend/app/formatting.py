"""Indian number formatting for messages (1,23,45,678.90)."""


def indian(value: float, decimals: int = 2) -> str:
    sign = "-" if value < 0 else ""
    whole, _, fraction = f"{abs(value):.{decimals}f}".partition(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}{whole}.{fraction}" if decimals else f"{sign}{whole}"
