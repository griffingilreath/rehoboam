import unittest
from jetson.cognition_service.main import CognitionService

class TestCognitionServiceExtraction(unittest.TestCase):
    def test_extract_json_simple(self):
        text = '{"foo": "bar"}'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"foo": "bar"})

    def test_extract_json_markdown(self):
        text = 'Here is the json:\n```json\n{"foo": "bar"}\n```'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"foo": "bar"})

    def test_extract_json_markdown_no_lang(self):
        text = 'Here is the json:\n```\n{"foo": "bar"}\n```'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"foo": "bar"})

    def test_extract_json_surrounded_by_text(self):
        text = 'Some prefix text {"foo": "bar"} some suffix text.'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"foo": "bar"})

    def test_extract_json_nested_braces(self):
        text = 'Prefix {"foo": {"bar": "baz"}} Suffix'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"foo": {"bar": "baz"}})

    def test_extract_json_multiple_candidates_first_wins(self):
        # Should pick the first valid JSON object
        text = 'First {"a": 1} Second {"b": 2}'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"a": 1})

    def test_extract_json_invalid(self):
        text = 'Not json at all'
        result = CognitionService._extract_json(text)
        self.assertIsNone(result)

    def test_extract_json_unbalanced_braces_fallback(self):
        # This tests the brace balancing logic vs the simple fallback
        text = 'Prefix { "a": { "b": 1 } } Suffix'
        result = CognitionService._extract_json(text)
        self.assertEqual(result, {"a": {"b": 1}})

if __name__ == "__main__":
    unittest.main()
