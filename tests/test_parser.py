import unittest

from tal_0.core import Opcode, TALFrame, TALParseError, TALParser


class TALParserTests(unittest.TestCase):
    def test_single_frame_round_trip(self):
        frame = TALFrame(Opcode.CMD, "c0", "r1", "find/vec", "q='auth',limit=5", "!?", "a7")
        wire = TALParser.serialize(frame)
        self.assertEqual(wire, "CMD:c0>r1:find/vec:q=\\'auth\\'\\,limit\\=5:!? :a7;".replace("!? :", "!?:"))
        self.assertEqual(TALParser.parse(wire), frame)

    def test_stream_parsing(self):
        stream = "CMD:c0>r1:read:path='a'::a1;RET:r1>c0:read:stat='ok':$:a1;"
        frames = TALParser.parse_stream(stream)
        self.assertEqual(len(frames), 2)
        self.assertEqual(frames[1].correlation_id, "a1")

    def test_escaped_delimiters_round_trip(self):
        frame = TALFrame(Opcode.RET, "r1", "c0", "read", "msg='a;b,c=d:e\\\\f'", "", "a1")
        self.assertEqual(TALParser.parse(frame.serialize()), frame)

    def test_parent_id_is_derived_from_payload(self):
        frame = TALParser.parse("CMD:r1>r2:read:path='spec.md',parent=a7:!:b3;")
        self.assertEqual(frame.parent_id, "a7")

    def test_malformed_frame_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("CMD:c0>r1:read:path='x':!:a1")

    def test_unknown_opcode_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("NOPE:c0>r1:read:::a1;")

    def test_bad_routing_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("CMD:c0r1:read:::a1;")

    def test_unknown_escape_rejected(self):
        with self.assertRaises(TALParseError):
            TALParser.parse("CMD:c0>r1:read:x=foo\\q::a1;")

    def test_missing_correlation_is_allowed_at_wire_level_for_generic_frames(self):
        frame = TALParser.parse("THK:c0>self:plan:goal='x':::p1;")
        self.assertEqual(frame.correlation_id, "p1")

    def test_empty_stream(self):
        self.assertEqual(TALParser.parse_stream(""), [])


if __name__ == "__main__":
    unittest.main()
