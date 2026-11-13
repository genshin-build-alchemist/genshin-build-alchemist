"""lib/ui.py 화면 부품 테스트 + app.py 실행 테스트 (Streamlit AppTest, 브라우저 없이).

실행 (저장소 루트에서): python -m unittest discover -s dashboard/tests
"""
import sys
import unittest
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD))

from lib import loader, ui  # noqa: E402


class PartsTest(unittest.TestCase):
    def test_wrap(self):
        self.assertEqual(ui.wrap("x"), '<div class="gd">x</div>')

    def test_checks(self):
        self.assertEqual(ui.checks_html([]), "")   # 문제가 없으면 아무것도 안 보임
        html = ui.checks_html([{"level": "gray", "msg": "g"}, {"level": "red", "msg": "<r>"}])
        self.assertLess(html.index('class="red"'), html.index('class="gray"'))   # 빨강이 먼저
        self.assertIn("&lt;r&gt;", html)
        self.assertIn('<span class="gray">⚠️ g</span>', html)

    def test_header_has_cond_on_right(self):
        html = ui.header_html("제목", "평가셋 info_v2 · 데이터 7.2", cond="DEV 60문항")
        self.assertLess(html.index("평가셋 info_v2"), html.index('class="cond"'))
        self.assertNotIn('class="cond"', ui.header_html("제목", "m"))

    def test_tip_script(self):
        """툴팁 스크립트: 한 번만 실행, customdata를 툴팁에, meta.spike면 점선."""
        js = ui.TIP_SCRIPT
        self.assertTrue(js.startswith("<script>") and js.rstrip().endswith("</script>"))
        for part in ["window.__gdTip", "plotly_hover", "plotly_unhover", "p.customdata", "meta.spike", "gd-hovering"]:
            self.assertIn(part, js)
        self.assertIn("#gd-tip", ui.CSS)
        self.assertIn("cursor:help", ui.CSS)

    def test_selected_css(self):
        self.assertIn(".st-key-tab_1 button", ui.selected_css("tab_1"))

    def test_summary_bold(self):
        html = ui.summary_html(["📈 **0.021 → 0.817**", "둘째"])
        self.assertIn("<b>0.021 → 0.817</b>", html)
        self.assertIn("<br>", html)
        self.assertEqual(ui.summary_html([]), "")

    def test_delta(self):
        self.assertEqual(ui.delta(2.384, 1.895, higher_is_better=False, unit="초"), ("▲ 0.489초", False))
        self.assertEqual(ui.delta(4, 11, higher_is_better=False, unit="개"), ("▼ 7개", True))
        self.assertEqual(ui.delta(0.796, 0.011), ("▲ 0.785", True))
        self.assertIsNone(ui.delta(None, 1))

    def test_cards(self):
        html = ui.cards_html([{"label": "평균", "value": "2.384", "unit": "초", "delta": ("▲ 0.489초", False)},
                              {"label": "Macro F1", "medal": "1.5B", "value_text": "0.862점(F1)"}])
        self.assertIn("repeat(2,", html)
        self.assertIn('<div class="dl bad">▲ 0.489초</div>', html)
        self.assertIn("🥇</span>1.5B", html)
        self.assertIn("0.862점(F1)", html)

    def test_insight_under_chart_parts(self):
        self.assertIn("💡", ui.insight_html(["**굵게**"]))
        self.assertIn("<b>굵게</b>", ui.insight_html(["**굵게**"]))
        self.assertEqual(ui.insight_html([]), "")

    def test_result_table(self):
        html = ui.result_table_html(["단계", "평균"], [["rag", "1.0초"], ["rag_v4", "2.384초"]],
                                    highlight=1, widths={0: "90px"})
        self.assertIn("📊 결과", html)
        self.assertIn('<th style="width:90px">단계</th>', html)
        self.assertIn('<tr class="hl"><td>rag_v4</td>', html)

    def test_box_items(self):
        html = ui.box_html("팀 결정 사항", [{"title": "모델", "items": ["a", "b"]}, {"title": "GPU", "desc": "속도"}])
        self.assertIn("<b>모델</b><ul><li>a</li>", html)
        self.assertIn("<b>GPU</b> → 속도", html)
        self.assertIn("다음", ui.box_html("다음", "한 줄"))
        self.assertEqual(ui.box_html("x", []), "")



@unittest.skipUnless(all((loader.DATA_DIR / f).is_dir() for f in loader.FOLDERS), "dashboard/data 폴더가 없음")
class AppRunTest(unittest.TestCase):
    """브라우저 없이 app.py를 끝까지 실행해서 에러가 없는지."""

    @classmethod
    def setUpClass(cls):
        from streamlit.testing.v1 import AppTest
        cls.at = AppTest.from_file(str(DASHBOARD / "app.py"), default_timeout=60).run()

    @staticmethod
    def md(at):
        """화면 글 (CSS <style> 블록은 뺀다)."""
        return "\n".join(m.value for m in at.markdown if not m.value.lstrip().startswith("<style>"))

    def test_no_exception(self):
        self.assertEqual(list(self.at.exception), [])

    def test_four_tab_buttons(self):
        labels = [b.label for b in self.at.button if b.key and b.key.startswith("tab_")]
        self.assertEqual(labels, ["① 성능 변화", "② 응답 시간", "③ 보조 지표", "④ 모델 비교"])

    def test_first_tab(self):
        md = self.md(self.at)
        self.assertIn("평가셋 info_v2 · 데이터 7.2", md)
        self.assertIn("공식 평가 121문항", md)       # 조건 칩 (① 것)
        self.assertIn("0.021 → 0.817", md)          # ① 요약 (yaml)
        self.assertIn("다음 과제", md)
        self.assertNotIn(ui.text.STALE_MSG, md)     # based_on이 최신
        self.assertNotIn("**", md)                  # 굵게 표시가 모두 <b>로 바뀜
        self.assertNotIn("code_version이 파일마다", md)   # ④ 경고는 ④ 탭에서만
        self.assertEqual(len(self.at.expander), 1)  # 고른 탭만 그린다
        self.assertNotIn("숫자는 각 탭의 결과 JSON 값", md)   # 하단 안내 줄은 없앰

    def test_layout_keys(self):
        """회색 상자는 key를 붙인 container에 CSS로 칠한다 (st-key-dk, st-key-panel_*)."""
        at = self.at.button(key="tab_1").click().run()
        keys = set()

        def walk(node):   # 블록 id 끝에 '-{key}'가 붙는다
            for child in getattr(node, "children", {}).values():
                block_id = getattr(getattr(child, "proto", None), "id", "")
                if isinstance(block_id, str) and "-" in block_id:
                    keys.add(block_id.rsplit("-", 1)[1])
                walk(child)
        walk(at.main)
        self.assertIn("dk", keys)
        self.assertTrue({"panel_c2a", "panel_c2b", "panel_c2c"} <= keys)

    def test_tab2_cards_charts_table(self):
        at = self.at.button(key="tab_1").click().run()
        self.assertEqual(list(at.exception), [])
        md = self.md(at)
        # 숫자 카드 (와이어프레임 ②와 같은 값)
        for card in ['<div class="kn">2.384<small>초</small></div><div class="dl bad">▲ 0.489초</div>',
                     '<div class="kn">1.482<small>초</small></div><div class="dl bad">▲ 0.382초</div>',
                     '<div class="kn">6.59<small>초</small></div><div class="dl good">▼ 1.847초</div>',
                     '<div class="kn">0.796</div><div class="dl good">▲ 0.785</div>',
                     '<div class="kn">4<small>개</small></div><div class="dl good">▼ 7개</div>']:
            self.assertIn(card, md)
        self.assertIn("rag_v4 기준 · baseline 대비 변화", md)
        # 그래프 3개, 📊 결과 표 (마지막 단계 강조)
        self.assertEqual(len(at.get("plotly_chart")), 3)
        self.assertIn("📊 결과", md)
        self.assertIn('<tr class="hl"><td>rag_v4</td><td>2.384초</td><td>1.482초</td><td>6.59초</td>'
                      '<td>0.796</td><td>4개</td></tr>', md)

    def test_tab2_conditions_and_chips(self):
        at = self.at.button(key="tab_1").click().run()
        md = self.md(at)
        self.assertIn("DEV 60문항 · Colab T4", md)  # 조건 칩이 ② 것으로 바뀜
        for row in ["실행 순서", "<code>main@af0c97c</code>", "<code>info_v2</code>",
                    "<code>Qwen/Qwen2.5-3B-Instruct</code>, float16", "<code>max_new_tokens=160</code>",
                    "DEV 60문항 (모든 방법이 같은 질문)"]:
            self.assertIn(row, md)
        chips = {b.key: b for b in at.button if b.key and b.key.startswith("chip_")}
        self.assertFalse(chips["chip_stage_response_time_rag_v4"].disabled)
        self.assertTrue(chips["chip_stage_response_time_rag_v5"].disabled)   # (예정)

    def test_tab4_has_no_warning(self):
        at = self.at.button(key="tab_3").click().run()
        md = self.md(at)
        self.assertIn("rag_v4 프롬프트 고정", md)   # ④ 조건 칩
        self.assertNotIn('class="chk"', md)       # 검증 경고 없음


    def test_tab3_aux(self):
        at = self.at.button(key="tab_2").click().run()
        self.assertEqual(list(at.exception), [])
        md = self.md(at)
        self.assertIn("DEV 60문항 · 후처리 없음 · 저장된 답 재채점", md)   # ③ 조건 칩
        for card in ['<div class="kn">0.717</div><div class="dl good">▲ 0.717</div>',
                     '<div class="kn">0.75</div><div class="dl good">▲ 0.75</div>',
                     '<div class="kn">0.089</div><div class="dl good">▼ 0.829</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 3)
        self.assertIn('<tr class="hl"><td>rag_v4</td><td>0.717</td><td>0.75</td><td>0.089</td><td>5 / 56</td></tr>', md)
        self.assertIn('data-tip="정답과 완전 일치(F1 = 1)한 문항 비율"', md)   # 범례 ⓘ 정의 (툴팁은 스크립트가)
        self.assertIn("막대 전체 = 답한 문항 수 (60문항 중, 빈 답 제외)", md)
        self.assertNotIn("유형 구분 없음", md)   # 모든 단계에 환각 목록이 있음
        self.assertIn("주요 발견", md)


    def test_tab4_model_compare(self):
        at = self.at.button(key="tab_3").click().run()
        self.assertEqual(list(at.exception), [])
        md = self.md(at)
        # 1위 카드 (L4 · fp16 기준, 와이어프레임과 같은 값)
        for card in ['🥇</span>1.5B</div><div class="kv">0.862점(F1)</div>',
                     '<div class="kl">조건 검색</div><div class="km"><span class="md">🥇</span>1.5B</div><div class="kv">0.483점(F1)</div>',
                     '🥇</span>1.5B · 3B</div><div class="kv">1.0점(F1)</div>',
                     '🥇</span>1.5B</div><div class="kv">1.142초</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 5)
        self.assertNotIn("흐린 막대 = T4", md)   # c4d·c4e는 범례 없음 (와이어프레임)
        # 결과 표: 8개 조합, 3B 두 줄 강조
        self.assertEqual(md.count('<tr class="hl"><td>3B</td>'), 2)
        self.assertIn("<td>7B</td><td>T4 · fp16</td><td>0.808</td><td>0.975</td><td>0.342</td><td>12.648초</td>", md)
        self.assertIn('data-tip="조건 검색 16문항에서 답한 이름 수 평균"', md)
        for box in ["현재 문제점 및 개선 방향", "팀 결정 사항", "다음 과제"]:
            self.assertIn(box, md)


    def test_tab1_performance(self):
        at = self.at.button(key="tab_0").click().run()   # 다른 테스트가 탭을 바꿨을 수 있어서 ①을 직접 누른다
        md = self.md(at)
        for card in ['<div class="k" style="border-left-color:#7F77DD"><div class="kl">전체</div><div class="kn">0.817</div>'
                     '<div class="kc">121문항</div></div>',
                     '<div class="kl">캐릭터 조회</div><div class="kn">0.989</div><div class="kc">87문항</div>',
                     '<div class="kl">조건 검색</div><div class="kn">0.262</div><div class="kc">26문항</div>',
                     '<div class="kl">데이터 없음</div><div class="kn">0.75</div><div class="kc">8문항</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 1)
        self.assertIn('<tr class="hl"><td>rag_v4</td><td>성급·지역 예시, 규칙 2줄</td>', md)
        self.assertNotIn("데이터 없음 오답", md)            # 오답 목록 상자는 뺐음
        for box in ["요약", "다음 과제"]:
            self.assertIn(f"<span>{box}</span>", md)


if __name__ == "__main__":
    unittest.main()
