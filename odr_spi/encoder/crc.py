"""CRC-16/CCITT as used by DAB datagroups and packets (ETSI EN 300 401).

Polynomial 0x1021, register preset to 0xFFFF, result inverted.
"""

def _make_table():
    table = []
    for i in range(256):
        crc = i << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else (crc << 1)
        table.append(crc & 0xFFFF)
    return table


_TABLE = _make_table()


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _TABLE[((crc >> 8) ^ b) & 0xFF]
    return crc ^ 0xFFFF
