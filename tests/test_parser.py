import unittest
from tal_0.core import Opcode, TALFrame, TALParseError, TALParser

class ParserTests(unittest.TestCase):
    def test_canonical_six_field_ret(self):
        wire="RET:r1>c0:find/vec:out=[{id='d1',score=0.93}],stat='ok':$:a7;"
        frame=TALParser.parse(wire)
        self.assertEqual(frame.correlation_id,'a7')
        self.assertEqual(TALParser.serialize(frame),wire)
    def test_empty_flags(self):
        self.assertEqual(TALParser.parse("THK:c0>self:plan:goal='audit'::p1;").flags,'')
    def test_nested_payload_commas(self):
        payload="out=[{id='d1',score=0.93},{id='d2',score=0.88}],msg='a,b',ok=T"
        self.assertEqual(TALParser.split_assignment(TALParser.split_payload(payload)[0])[0],'out')
        self.assertEqual(len(TALParser.split_payload(payload)),3)
    def test_escaped_semicolon_round_trip(self):
        frame=TALFrame(Opcode.RET,'r1','c0','read',"msg='a;b,c=d:e'",'','a1')
        self.assertEqual(TALParser.parse(frame.serialize()),frame)
    def test_bad_seven_field_frame_rejected(self):
        with self.assertRaises(TALParseError): TALParser.parse("RET:r1>c0:read:out='x'::$:a1;")
    def test_stream(self):
        self.assertEqual(len(TALParser.parse_stream("CMD:c0>r1:read:path='a'::a1;RET:r1>c0:read:stat='ok':$:a1;")),2)
    def test_bad_opcode(self):
        with self.assertRaises(TALParseError): TALParser.parse('NOPE:c0>r1:read:::a1;')

if __name__=='__main__': unittest.main()
