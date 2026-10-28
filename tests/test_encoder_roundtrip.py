"""Decode the generated packet stream back into MOT objects and check that
every layer (packets, datagroups, directory, bodies) is consistent."""
import itertools
import unittest
from datetime import datetime, timezone

from odr_spi.encoder import msc, mot, spi_binary
from odr_spi.encoder.crc import crc16


def decode_packets(stream, size):
    groups, buf, expect_index = [], b"", None
    pos = 0
    while pos < len(stream):
        psize = ((stream[pos] >> 6) + 1) * 24
        pkt = stream[pos:pos + psize]
        assert crc16(pkt[:-2]) == int.from_bytes(pkt[-2:], "big"), "packet CRC"
        assert psize <= size
        index = (pkt[0] >> 4) & 3
        if expect_index is not None:
            assert index == expect_index, "packet continuity"
        expect_index = (index + 1) % 4
        first, last = bool(pkt[0] & 0x08), bool(pkt[0] & 0x04)
        n = pkt[2] & 0x7F
        if first:
            buf = b""
        buf += pkt[3:3 + n]
        if last:
            groups.append(buf)
        pos += psize
    assert expect_index == 0, "stream must end on continuity index 3"
    return groups


def parse_datagroup(dg):
    assert crc16(dg[:-2]) == int.from_bytes(dg[-2:], "big"), "datagroup CRC"
    dg_type = dg[0] & 0x0F
    last = bool(dg[2] & 0x80)
    seg_no = ((dg[2] & 0x7F) << 8) | dg[3]
    tid = int.from_bytes(dg[5:7], "big")
    seg_len = int.from_bytes(dg[7:9], "big") & 0x1FFF
    data = dg[9:9 + seg_len]
    assert 9 + seg_len + 2 == len(dg)
    return dg_type, tid, seg_no, last, data


class RoundTripTest(unittest.TestCase):
    def test_roundtrip(self):
        big = bytes((i * 13) % 256 for i in range(30000))
        objs = [
            mot.MotObject("0", spi_binary.service_information(
                {"ecc": 0xE1, "eid": 0xC185, "short_name": "Test", "medium_name": "Test Mux"},
                [{"short_name": "R1", "medium_name": "Radio 1", "bearers": [(0xE1, 0xC185, 0xC586, 0)],
                  "short_description": "Hits", "genres": ["urn:tva:metadata:cs:ContentCS:2002:3.6.8"]}]),
                mot.CT_SPI_SI, 1).add(mot.ScopeId(spi_binary.ensemble_id(0xE1, 0xC185))),
            mot.MotObject("logo", big, mot.CT_IMAGE_PNG, 2).add(mot.UniqueBodyVersion(42)),
        ]
        ids = itertools.count(100)
        groups = msc.encode_directorymode(objs, lambda: next(ids))
        for size in (24, 48, 72, 96):
            stream = b"".join(msc.encode_packets(groups, address=1, size=size))
            decoded = decode_packets(stream, size)
            bodies, directory = {}, b""
            for dg in decoded:
                t, tid, seg_no, last, data = parse_datagroup(dg)
                if t == 6:
                    directory = data if seg_no == 0 else directory + data
                elif t == 4:
                    bodies[tid] = data if seg_no == 0 else bodies[tid] + data
            self.assertEqual(int.from_bytes(directory[:4], "big"), len(directory))
            self.assertEqual(int.from_bytes(directory[4:6], "big"), 2)
            self.assertEqual(bodies[1], objs[0].body)
            self.assertEqual(bodies[2], big)

    def test_single_pass_ends_on_continuity_3(self):
        # every packet count modulo 4, and a last datagroup too small to split evenly
        for n_groups in range(1, 9):
            groups = [msc.datagroup(100 + i, msc.DG_BODY, bytes(2 + i * 37), 0, i, True) for i in range(n_groups)]
            for size in (24, 48, 72, 96):
                stream = b"".join(msc.encode_packets(groups, address=1, size=size))
                self.assertEqual(decode_packets(stream, size), groups)  # one pass, intact
                self.assertEqual(len(msc.encode_packets(groups, 1, size)) % 4, 0)

    def test_timepoint(self):
        t = datetime(2026, 10, 26, 6, 30, tzinfo=timezone.utc)
        raw = int.from_bytes(spi_binary.timepoint(t), "big")
        self.assertEqual((raw >> 14) & 0x1FFFF, 61339)  # MJD of 2026-10-26
        self.assertEqual((raw >> 6) & 0x1F, 6)
        self.assertEqual(raw & 0x3F, 30)

    def test_programme_information(self):
        start = datetime(2026, 10, 26, tzinfo=timezone.utc)
        pi = spi_binary.programme_information(
            (0xE1, 0xC185, 0xC586, 0), start, start.replace(day=27),
            [{"crid": "crid://x/1", "short_id": 1, "medium_name": "Breakfast", "start": start, "duration": 3600}],
            created=start)
        self.assertEqual(pi[0], spi_binary.T_EPG)


if __name__ == "__main__":
    unittest.main()
