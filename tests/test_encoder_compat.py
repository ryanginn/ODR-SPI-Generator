"""Byte-for-byte comparison against the original python-dabmot / python-dabmsc
stack.  Skipped unless those libraries are importable, e.g.:

    PYTHONPATH=python-dabmot/src:python-dabmsc/src:python-mot-epg/src:python-hybridspi/src \
        python -m pytest tests/test_encoder_compat.py
"""
import itertools
import unittest

from odr_spi.encoder import msc, mot, spi_binary
from odr_spi.encoder.crc import crc16

try:
    import crcmod
    import msc as ref_msc
    import msc.datagroups as ref_dg
    import msc.packets as ref_pk
    import mot as ref_mot
    from mot.epg import ScopeId as RefScopeId, EpgContentType
    HAVE_REF = True
except Exception:  # pragma: no cover
    HAVE_REF = False


def original_si(ecc, eid, label, shortlabel, services, ensemble_media):
    """The SI TLV builder copied verbatim (logic-wise) from the legacy script."""
    def tlv(tag, data):
        if len(data) < 0xFE: return bytes([tag, len(data)]) + data
        else: return bytes([tag, 0xFE, (len(data) >> 8) & 0xFF, len(data) & 0xFF]) + data

    def attr_str(tag, s):
        b = s.encode('utf-8')
        return bytes([tag, len(b)]) + b

    def attr_u16(tag, val):
        return bytes([tag, 2, (val >> 8) & 0xFF, val & 0xFF])

    def media(m):
        url, mime, w, h = m
        p = bytearray()
        p += attr_str(0x82, url)
        p += bytes([0x83, 1, 0x04 if (w == 32 and h == 32) else 0x02])
        p += attr_u16(0x84, w)
        p += attr_u16(0x85, h)
        p += attr_str(0x80, mime)
        return tlv(0x13, tlv(0x2B, bytes(p)))

    ens = bytearray(bytes([0x80, 3, ecc, (eid >> 8) & 0xFF, eid & 0xFF]))
    ens += tlv(0x10, tlv(0x01, shortlabel[:8].encode()))
    ens += tlv(0x11, tlv(0x01, label[:16].encode()))
    for m in ensemble_media:
        ens += media(m)
    for short, med, secc, sid, ms in services:
        sp = bytearray()
        sp += tlv(0x10, tlv(0x01, short.encode()))
        sp += tlv(0x11, tlv(0x01, med.encode()))
        sp += tlv(0x2D, tlv(0x80, bytes([0x40, secc, eid >> 8, eid & 0xFF, sid >> 8, sid & 0xFF])))
        for m in ms:
            sp += media(m)
        ens += tlv(0x28, bytes(sp))
    root = attr_u16(0x80, 1) + attr_str(0x82, "ODR") + tlv(0x26, bytes(ens))
    return tlv(0x03, root)


class CrcTest(unittest.TestCase):
    @unittest.skipUnless(HAVE_REF, "reference libraries not installed")
    def test_crc_matches_crcmod(self):
        ref = crcmod.mkCrcFun(0x11021, 0x0, False, 0xFFFF)
        for data in (b"", b"123456789", bytes(range(256)) * 3):
            self.assertEqual(crc16(data), ref(data))


class SiTest(unittest.TestCase):
    def test_si_matches_legacy_builder(self):
        media = [("1", "image/png", 32, 32), ("2", "image/png", 320, 240)]
        services = [("Demo R1", "Demo Radio 1", 0xE3, 0x2491, media), ("Ri Ra", "Raidio Ri Ra", 0xE2, 0x2493, [])]
        expected = original_si(0xE3, 0x2EA1, "Demo DAB", "DEMO", services, [("3", "image/jpeg", 32, 32)])
        got = spi_binary.service_information(
            {"ecc": 0xE3, "eid": 0x2EA1, "short_name": "DEMO", "medium_name": "Demo DAB",
             "media": [("3", "image/jpeg", 32, 32)]},
            [{"short_name": sh, "medium_name": md, "bearers": [(ecc, 0x2EA1, sid, 0)], "media": ms}
             for sh, md, ecc, sid, ms in services])
        self.assertEqual(got, expected)

    def test_genre_encoding(self):
        self.assertEqual(spi_binary.genre_bytes("urn:tva:metadata:cs:ContentCS:2002:3.6.8"), b"\x03\x06\x08")
        self.assertIsNone(spi_binary.genre_bytes("urn:tva:metadata:cs:ContentCS:2002:10"))


@unittest.skipUnless(HAVE_REF, "reference libraries not installed")
class MscCompatTest(unittest.TestCase):
    def _objects(self):
        big = bytes((i * 7) % 256 for i in range(20000))  # forces multi-segment bodies
        specs = [("0", b"\x03\x05hello", (7, 0)), ("1", b"\x89PNG" + bytes(300), (2, 3)), ("2", big, (2, 1))]
        ours, theirs = [], []
        for i, (name, body, ct) in enumerate(specs):
            tid = 1000 + i
            o = mot.MotObject(name, body, ct, tid).add(mot.UniqueBodyVersion(0x1234567))
            r = ref_mot.MotObject(name, body, ref_mot.ContentType(*ct), transport_id=tid)
            r.add_parameter(ref_mot.UniqueBodyVersion(0x1234567))
            if name == "0":
                o.add(mot.ScopeId(spi_binary.ensemble_id(0xE1, 0xC185)))
                r.add_parameter(RefScopeId(0xE1, 0xC185))
            ours.append(o)
            theirs.append(r)
        return ours, theirs

    def test_directory_and_packets(self):
        ours, theirs = self._objects()
        for n_objects in (1, 2, 3):
            ids = itertools.count(5000)
            ref_ids = itertools.count(5000)
            orig = ref_dg.generate_transport_id
            ref_dg.generate_transport_id = lambda name=None: next(ref_ids)
            try:
                ref_groups = ref_dg.encode_directorymode(theirs[:n_objects], directory_parameters=[])
            finally:
                ref_dg.generate_transport_id = orig
            groups = msc.encode_directorymode(ours[:n_objects], lambda: next(ids))
            self.assertEqual(groups, [g.tobytes() for g in ref_groups])
            for size in (24, 48, 72, 96):
                ref_packets = ref_pk.encode_packets(ref_groups, address=1, size=size, padding=True)
                packets = msc.encode_packets(groups, address=1, size=size)
                self.assertEqual(b"".join(packets), b"".join(p.tobytes() for p in ref_packets))

    def test_scope_id(self):
        self.assertEqual(mot.ScopeId(spi_binary.content_id(0xE1, 0xC185, 0xC586)).encode(),
                         bytes.fromhex("E706 40E1 C185 C586".replace(" ", "")))


if __name__ == "__main__":
    unittest.main()
