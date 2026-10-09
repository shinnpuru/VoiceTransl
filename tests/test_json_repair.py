import json
import unittest
from GalTransl.JsonRepair import load_translation_object
from GalTransl.Backend.ForGalJsonTranslate import ForGalJsonTranslate
from GalTransl.CSentense import CSentense


class JsonRepairTests(unittest.TestCase):
    def test_only_complete_text_endings_are_repaired(self):
        for text in ('{"id":1,"dst":"译文"', '{"id":1,"dst":"译文”}', '{"id":1,"dst":"译文”'):
            self.assertEqual(load_translation_object(text), {'id': 1, 'dst': '译文'})
        for text in ('{"id":1,"dst":"截断', '{"id":1,"dst":', '{"id":1,"dst":"x",garbage', '{"id":1,"dst":"x"} arbitrary text'):
            with self.assertRaises(json.JSONDecodeError):
                load_translation_object(text)

    def test_valid_dialogue_quotes_braces_and_slashes_remain_unchanged(self):
        obj = {'id': 1, 'dst': '说：“保留” {大括号} / 路径 / "英文引号"'}
        self.assertEqual(load_translation_object(json.dumps(obj, ensure_ascii=False)), obj)

    def test_repair_does_not_bypass_id_or_signature_validation(self):
        translator = ForGalJsonTranslate.__new__(ForGalJsonTranslate)
        sentence = CSentense('原文', '', 1)
        for line in ('abc|{"id":2,"dst":"译文"', 'xyz|{"id":1,"dst":"译文”}'):
            ok, _ = translator._parse_jsonline_result_line(line, [sentence], 'test', '', 'dst', {'i': -1}, [], sig_list=['abc'])
            self.assertFalse(ok)
