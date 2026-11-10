import unittest

from patchnotes.noise import drop_noise, noise_rule


def change(field, before, after):
    return {"field": field, "before": before, "after": after}


def record(changes, change_type="modified"):
    return {"version": "5.6", "folder": "talents", "entity_id": "albedo", "entity_name": "알베도",
            "change_type": change_type, "changes": changes}


class NoiseRuleTest(unittest.TestCase):
    def test_noise_changes(self):
        self.assertEqual(noise_rule(change("cv/english", "A", "B")), "성우 정보")
        self.assertEqual(noise_rule(change("combat2/attributes/labels[3]", "기본 피해|{param2:F2P}", "기존 피해|{param2:F2P}")),
                         "수치 표 항목 이름 수정")
        self.assertEqual(noise_rule(change("combat3/flavorText", "a", "b")), "소개 문구")
        self.assertEqual(noise_rule(change("combat1/name", "일반 공격·페보니우스 검술·백", "페보니우스 검술·백")),
                         "일반 공격 이름 표기")
        self.assertEqual(noise_rule(change("baseStatText", "NaN", "0%")), "빈 값 표기 (NaN·0%)")
        self.assertEqual(noise_rule(change("birthday", "11월 30일", "")), "생일 정보")

    def test_real_changes_are_kept(self):
        self.assertIsNone(noise_rule(change("passive1/description", "피해 10% 증가", "피해 20% 증가")))
        self.assertIsNone(noise_rule(change("combat1/name", "일반 공격·검술", "일반 공격·신검술")))   # 이름 자체가 바뀜
        self.assertIsNone(noise_rule(change("r1/values", [1, 2], [1, 3])))
        self.assertIsNone(noise_rule(change("baseStatText", "10%", "12%")))
        self.assertIsNone(noise_rule(change("combat2/attributes/labels[6]", None, "협동 공격 피해|{param9:F1P}")))   # 새 항목


class DropNoiseTest(unittest.TestCase):
    def test_record_with_only_noise_is_dropped(self):
        records = [record([change("combat1/name", "일반 공격·검술", "검술")])]
        kept, by_rule, dropped = drop_noise(records)
        self.assertEqual((kept, dropped), ([], 1))
        self.assertEqual(by_rule["일반 공격 이름 표기"], 1)

    def test_mixed_record_keeps_only_real_changes(self):
        records = [record([change("cv/korean", "A", "B"), change("c1/description", "전", "후")])]
        kept, _, dropped = drop_noise(records)
        self.assertEqual(dropped, 0)
        self.assertEqual([c["field"] for c in kept[0]["changes"]], ["c1/description"])

    def test_added_and_removed_are_kept(self):
        records = [record([], "added"), record([], "removed")]
        kept, _, dropped = drop_noise(records)
        self.assertEqual((len(kept), dropped), (2, 0))


if __name__ == "__main__":
    unittest.main()
