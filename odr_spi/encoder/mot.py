"""MOT objects and header parameters (ETSI EN 301 234, ETSI TS 102 371)."""

from datetime import datetime, timezone

# (type, subtype) content types
CT_IMAGE_JFIF = (2, 1)
CT_IMAGE_PNG = (2, 3)
CT_SPI_SI = (7, 0)
CT_SPI_PI = (7, 1)

CHARSET_ISO_LATIN1 = 4


def mjd(d) -> int:
    """Modified Julian Date of a date/datetime."""
    return d.toordinal() - 678576


class HeaderParameter:
    param_id = 0

    def data(self) -> bytes:
        raise NotImplementedError

    def encode(self) -> bytes:
        data = self.data()
        n = len(data)
        pid = self.param_id & 0x3F
        if n == 0:
            return bytes([pid])
        if n == 1:
            return bytes([0x40 | pid]) + data
        if n == 4:
            return bytes([0x80 | pid]) + data
        if n <= 127:
            return bytes([0xC0 | pid, n]) + data
        if n <= 32767:
            return bytes([0xC0 | pid, 0x80 | (n >> 8), n & 0xFF]) + data
        raise ValueError("header parameter too long")


class ContentName(HeaderParameter):
    param_id = 12

    def __init__(self, name: str):
        self.name = name

    def data(self):
        return bytes([CHARSET_ISO_LATIN1 << 4]) + self.name.encode("latin-1")


class UniqueBodyVersion(HeaderParameter):
    param_id = 13

    def __init__(self, value: int):
        self.value = value & 0xFFFFFFFF

    def data(self):
        return self.value.to_bytes(4, "big")


def encode_mot_time(t: datetime) -> bytes:
    """MOT absolute time with validity flag set (EN 301 234 6.2.4.1)."""
    t = t.astimezone(timezone.utc) if t.tzinfo else t
    bits = (1 << 31) | (mjd(t.date()) << 14)
    if t.second:
        bits = (bits | (1 << 11) | (t.hour << 6) | t.minute) << 16
        bits |= (t.second << 10)
        return bits.to_bytes(6, "big")
    bits |= (t.hour << 6) | t.minute
    return bits.to_bytes(4, "big")


class ScopeStart(HeaderParameter):
    param_id = 0x25

    def __init__(self, t: datetime):
        self.t = t

    def data(self):
        return encode_mot_time(self.t)


class ScopeEnd(ScopeStart):
    param_id = 0x26


class ScopeId(HeaderParameter):
    param_id = 0x27

    def __init__(self, raw: bytes):
        self.raw = raw

    def data(self):
        return self.raw


class MotObject:
    def __init__(self, name: str, body: bytes, content_type, transport_id: int):
        self.name = name
        self.body = body
        self.content_type = content_type
        self.transport_id = transport_id & 0xFFFF
        self.parameters = [ContentName(name)]

    def add(self, param: HeaderParameter):
        self.parameters.append(param)
        return self

    def header_core_and_extension(self) -> bytes:
        ext = b"".join(p.encode() for p in self.parameters)
        ctype, subtype = self.content_type
        core = (len(self.body) << 28) | ((len(ext) + 7) << 15) | (ctype << 9) | subtype
        return core.to_bytes(7, "big") + ext
