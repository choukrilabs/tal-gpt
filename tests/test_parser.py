import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import unittest

from tal_0.core import Opcode, TALFrame, TALParseError, TALParser


class ParserTests(unittest.TestCase):
    def test_round_trip_single_frame(self):
        frame = TALFrame(Opcode.CMD, "c0", "r1", "find/vec", "q='auth_cve',limit=1", "!")
        self.assertEqual(TALParser.parse(frame.serialize()), frame)

    def test_parse_stream_returns_all_frames(self):
        frames = TALParser.parse_stream(
            "SYN:c0>r1:sync:ver='1'::;ACK:r1>c0:sync:ok=T::;RET:r1>c0:find/vec:hits=['x']::;"
        )
        self.assertEqual([f.header for f in frames], [Opcode.SYN, Opcode.ACK, Opcode.RET])

    def test_malformed_frame_is_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("CMD:c0>r1:find/vec:q='x'")

    def test_unknown_opcode_is_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("NOPE:c0>r1:x:y::;")

    def test_empty_routing_is_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("CMD:c0>:exec/py:code='x'::;")


if __name__ == "__main__":
    unittest.main()
