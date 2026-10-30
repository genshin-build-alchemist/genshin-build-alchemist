import unittest

from patchnotes.differ import diff_json, flatten


class FlattenTest(unittest.TestCase):
    def test_nested_paths(self):
        data = {"a": {"b": 1}, "c": ["x", "y"]}
        self.assertEqual(flatten(data), {"a/b": 1, "c[0]": "x", "c[1]": "y"})

    def test_ignores_raw_and_id_keys(self):
        data = {"id": 1, "name": "호두", "descriptionRaw": "<color=#FFF>태그</color>"}
        self.assertEqual(flatten(data), {"name": "호두"})

    def test_ignores_lore_and_cost_fields(self):
        data = {"name": "검", "story": "옛이야기", "region": "몬드", "costs": {"ascend1": []}}
        self.assertEqual(flatten(data), {"name": "검"})

    def test_number_list_is_one_value(self):
        self.assertEqual(flatten({"p": [1.0, 2.5, 3]}), {"p": [1.0, 2.5, 3]})


class DiffJsonTest(unittest.TestCase):
    def test_detects_text_change(self):
        before = {"passive1": {"description": "감전 반응을 발동하면"}}
        after = {"passive1": {"description": "감전, 별 초전도 반응을 발동하면"}}
        changes = diff_json(before, after)
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]["field"], "passive1/description")
        self.assertIn("별 초전도", changes[0]["after"])

    def test_detects_number_table_change(self):
        before = {"combat1": {"attributes": {"parameters": {"param1": [0.5, 0.6]}}}}
        after = {"combat1": {"attributes": {"parameters": {"param1": [0.5, 0.7]}}}}
        changes = diff_json(before, after)
        self.assertEqual(changes[0]["field"], "combat1/attributes/parameters/param1")
        self.assertEqual(changes[0]["after"], [0.5, 0.7])

    def test_formatting_only_change_is_ignored(self):
        before = {"d": "<color=#FFD780FF>피해</color> 증가"}
        after = {"d": "피해   증가"}
        self.assertEqual(diff_json(before, after), [])

    def test_added_and_removed_fields(self):
        changes = {c["field"]: c for c in diff_json({"a": "1"}, {"b": "2"})}
        self.assertIsNone(changes["a"]["after"])
        self.assertIsNone(changes["b"]["before"])

    def test_identical_json_has_no_changes(self):
        data = {"name": "치치", "x": [1, 2]}
        self.assertEqual(diff_json(data, data), [])


if __name__ == "__main__":
    unittest.main()
