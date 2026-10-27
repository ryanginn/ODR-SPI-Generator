"""MSC datagroups (directory mode) and packet mode encoding.

Datagroups are byte-identical to python-dabmsc's encode_directorymode() for
the same transport IDs. Packets match its encode_packets() except that one
pass of the carousel is written instead of repeating it up to four times.
"""

from .crc import crc16

MAX_SEGMENT_SIZE = 8189

DG_BODY = 4
DG_DIRECTORY_UNCOMPRESSED = 6

PACKET_SIZES = (24, 48, 72, 96)


def _segments(data: bytes, max_size=MAX_SEGMENT_SIZE):
    out = []
    for i in range(0, len(data), max_size):
        chunk = data[i:i + max_size]
        out.append(len(chunk).to_bytes(2, "big") + chunk)  # repetition count 0
    return out


def datagroup(transport_id, dg_type, segment, segment_index, continuity, last):
    hdr = bytes([
        0x70 | (dg_type & 0x0F),  # no extension, CRC, segment header, user access
        (continuity % 16) << 4,  # repetition index 0
        (0x80 if last else 0) | ((segment_index >> 8) & 0x7F),
        segment_index & 0xFF,
        0x12,  # transport id present, length indicator 2
    ]) + (transport_id & 0xFFFF).to_bytes(2, "big")
    body = hdr + segment
    return body + crc16(body).to_bytes(2, "big")


def encode_directorymode(objects, next_transport_id):
    """objects: list of mot.MotObject.  next_transport_id: callable -> int."""
    entries = b"".join(
        o.transport_id.to_bytes(2, "big") + o.header_core_and_extension() for o in objects
    )
    directory = (
        (len(entries) + 13).to_bytes(4, "big")  # compression flag 0, RFU 0, 30-bit size
        + len(objects).to_bytes(2, "big")
        + bytes(3)  # carousel period undefined
        + bytes(2)  # RFU + segment size 0
        + bytes(2)  # no directory extension
        + entries
    )

    groups = []
    dir_tid = next_transport_id()
    segs = _segments(directory)
    for i, seg in enumerate(segs):
        groups.append(datagroup(dir_tid, DG_DIRECTORY_UNCOMPRESSED, seg, i, i % 16, i == len(segs) - 1))

    continuity = 0
    for o in objects:
        segs = _segments(o.body)
        for i, seg in enumerate(segs):
            groups.append(datagroup(o.transport_id, DG_BODY, seg, i, continuity, i == len(segs) - 1))
            continuity = (continuity + 1) % 16

    # pad the body continuity index the same way python-dabmsc does
    if continuity != 0:
        empty = bytes(2)
        groups.append(datagroup(next_transport_id(), DG_BODY, empty, 0, continuity, True))
        continuity = (continuity + 1) % 16
        if continuity != 0:
            groups.append(datagroup(next_transport_id(), DG_BODY, empty, 0, 15, True))
    return groups


def _packet(size, address, data, first, last, index):
    hdr = bytes([
        (((size // 24) - 1) << 6) | ((index & 3) << 4) | (0x08 if first else 0)
        | (0x04 if last else 0) | ((address >> 8) & 0x03),
        address & 0xFF,
        len(data) & 0x7F,
    ])
    body = hdr + data + bytes(size - len(data) - 5)
    return body + crc16(body).to_bytes(2, "big")


def _required_size(n, max_size):
    if n > max_size - 5:
        return max_size
    for s in PACKET_SIZES:
        if n <= s - 5:
            return s
    return 96


def _split(data, pieces, chunk):
    """Split data into `pieces` parts of at most `chunk` bytes, as evenly as possible."""
    base, extra = divmod(len(data), pieces)
    out, pos = [], 0
    for n in range(pieces):
        size = base + (1 if n < extra else 0)
        out.append(data[pos:pos + size])
        pos += size
    assert all(0 < len(p) <= chunk for p in out)
    return out


def encode_packets(groups, address=1, size=96):
    """One pass of the carousel as packets.

    The multiplexer loops the file, so the packet count is made a multiple of
    four: the continuity index then ends on 3 and carries on from 0 without a
    break. Rather than repeating the whole carousel (up to 4x the size, as
    python-dabmsc does), the last datagroup is spread over 1-3 extra packets."""
    if not 1 <= address <= 1023:
        raise ValueError("packet address must be between 1 and 1023")
    if size not in PACKET_SIZES:
        raise ValueError("packet size must be one of %s" % (PACKET_SIZES,))
    if not groups:
        return []
    chunk = size - 5
    plans = [[dg[i:i + chunk] for i in range(0, len(dg), chunk)] for dg in groups]
    total = sum(len(p) for p in plans)
    extra = -total % 4
    if extra:
        last = groups[-1]
        plans[-1] = _split(last, len(plans[-1]) + extra, chunk)
    out = []
    index = -1
    for parts in plans:
        for n, part in enumerate(parts):
            index = (index + 1) % 4
            out.append(_packet(_required_size(len(part), size), address, part, n == 0, n == len(parts) - 1, index))
    return out
