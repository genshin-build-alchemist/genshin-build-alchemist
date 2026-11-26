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

    def test_header(self):
        self.assertEqual(ui.header_html("제목"), '<p class="brand">제목</p>')

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
        self.assertEqual(html.count("<li>"), 2)        # 한 줄에 불릿 하나
        self.assertEqual(ui.summary_html([]), "")

    def test_delta(self):
        self.assertEqual(ui.delta(2.384, 1.895, higher_is_better=False, unit="초"), ("▲ +0.489초", "bad"))
        self.assertEqual(ui.delta(4, 11, higher_is_better=False, unit="개"), ("▼ −7개", "good"))
        self.assertEqual(ui.delta(0.796, 0.011), ("▲ +0.785", "good"))
        self.assertIsNone(ui.delta(None, 1))

    def test_cards(self):
        html = ui.cards_html([{"label": "평균", "value": "2.384", "unit": "초", "delta": ("▲ 0.489초", "bad")},
                              {"label": "Macro F1", "medal": "1.5B", "value_text": "0.862점(F1)"}])
        self.assertIn("repeat(2,", html)
        self.assertIn('<div class="dl bad">▲ 0.489초</div>', html)
        self.assertIn("🥇</span>1.5B", html)
        self.assertIn("0.862점(F1)", html)

    def test_insight_under_chart_parts(self):
        self.assertIn("💡", ui.insight_html(["**굵게**"]))
        html = ui.insight_html(["**소제목** 첫 문장입니다. 둘째 문장입니다."])
        self.assertIn('<div class="it">소제목</div>', html)          # 굵은 소제목은 따로 한 줄
        self.assertEqual(html.count("<li>"), 2)                        # 문장마다 불릿
        self.assertEqual(ui.insight_html([]), "")

    def test_sentences_keep_parenthesis(self):
        # 마침표 뒤에 오는 '(보충)'은 앞 문장과 같은 줄, 숫자(0.817) 안에서는 나누지 않는다
        self.assertEqual(ui.sentences("집계되지 않았습니다. (112건 중 0건)"), ["집계되지 않았습니다. (112건 중 0건)"])
        self.assertEqual(ui.sentences("0.817로 올랐습니다. 다음입니다."), ["0.817로 올랐습니다.", "다음입니다."])

    def test_result_table(self):
        html = ui.result_table_html(["단계", "평균"], [["rag", "1.0초"], ["rag_v4", "2.384초"]],
                                    highlight=1, widths={0: "90px"})
        self.assertIn("📊 결과", html)
        self.assertIn('<th style="width:90px">단계</th>', html)
        self.assertIn('<tr class="hl"><td>rag_v4</td>', html)

    def test_result_table_class_and_sub(self):
        # cls는 상자에 붙는다 (줄 강조 클래스에 덮어써지지 않음), (본문, 회색 글) 칸은 아래에 작은 글
        html = ui.result_table_html(["지표", "측정 기준"], [["환각률", ("근거 밖 ÷ 응답", "ex) <오타>")]], cls="lh15")
        self.assertTrue(html.startswith('<div class="res lh15">'))
        self.assertIn('<td>근거 밖 ÷ 응답<div class="csub">ex) &lt;오타&gt;</div></td>', html)
        self.assertIn('class="note tip"', ui.result_table_html(["a"], [["b"]], note="설명"))   # 표 아래 설명은 💡
    def test_box_items(self):
        html = ui.box_html("팀 결정 사항", [{"title": "모델", "items": ["a", "b"]}, {"title": "GPU", "desc": "속도"}])
        self.assertIn("<b>모델</b><ul><li>a</li>", html)
        self.assertIn("<b>GPU</b> → 속도", html)
        self.assertIn("다음", ui.box_html("다음", "한 줄"))
        self.assertEqual(ui.box_html("x", []), "")
        sub = ui.box_html("측정 기준", [{"desc": "식", "sub": "(문항 수)"}])
        self.assertIn('<li>식<br><span class="sub">(문항 수)</span></li>', sub)   # 제목 없이 설명 + 회색 줄



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
        self.assertEqual(labels, ["성능 변화", "응답 시간", "보조 지표", "모델 비교"])
        stages = [b.key for b in self.at.button if b.key and b.key.startswith("fab_")]
        self.assertEqual(stages, ["fab_rag_v5_data", "fab_rag_v5", "fab_rag_v4"])   # 최신 단계가 맨 위

    def test_first_tab(self):
        md = self.md(self.at)
        self.assertIn("원신 챗봇 성능 개선 대시보드", md)
        self.assertIn('<span class="sn">rag_v5_data 실험 결과</span>', md)   # 처음엔 가장 최근 단계
        self.assertIn("Info_v2 · 평가 121문항 · 데이터 7.2", md)
        self.assertNotIn(ui.text.STALE_MSG, md)     # based_on이 최신
        self.assertNotIn("**", md)                  # 굵게 표시가 모두 <b>로 바뀜
        self.assertNotIn('class="chk"', md)         # 검증 경고 없음
        self.assertEqual(len(self.at.expander), 1)  # 고른 탭만 그린다

    def test_layout_keys(self):
        """회색 상자는 key를 붙인 container에 CSS로 칠한다 (st-key-dk, st-key-panel_*)."""
        self.assertTrue({"dk", "panel_c2a", "panel_c2b", "panel_c2c"} <= self.keys(self.tab(1)))

    @staticmethod
    def keys(at):
        """화면의 container key 목록 (블록 id 끝에 '-{key}'가 붙는다)."""
        out = set()

        def walk(node):
            for child in getattr(node, "children", {}).values():
                block_id = getattr(getattr(child, "proto", None), "id", "")
                if isinstance(block_id, str) and "-" in block_id:
                    out.add(block_id.rsplit("-", 1)[1])
                walk(child)
        walk(at.main)
        return out

    def tab(self, i, stage=None):
        """탭(과 실험 단계)을 눌러 다시 그린 화면. 다른 테스트가 바꾼 상태를 덮어쓰려고 둘 다 직접 누른다."""
        at = self.at.button(key=f"fab_{stage or 'rag_v5_data'}").click().run()
        at = at.button(key=f"tab_{i}").click().run()
        self.assertEqual(list(at.exception), [])
        return at

    def test_tab1_performance(self):
        at = self.tab(0)
        md = self.md(at)
        for card in ['<div class="kl">전체</div><div class="kn">0.992</div><div class="dl good">▲ +0.040</div>',
                     '<div class="kl">캐릭터 조회</div><div class="kn">0.989</div><div class="dl same">= 0.000</div>',
                     '<div class="kl">조건 검색</div><div class="kn">1.000</div><div class="dl good">▲ +0.110</div>',
                     '<div class="kl">데이터 없음</div><div class="kn">1.000</div><div class="dl good">▲ +0.250</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 1)
        # 실험 기록: 측정 기준이 맨 앞, 단계별 프롬프트 버튼은 단계마다 하나
        self.assertLess(md.index("<span>측정 기준</span>"), md.index("단계별 프롬프트"))
        self.assertIn("(캐릭터 조회는 87문항, 조건 검색은 26문항, 데이터 없음은 8문항)", md)
        self.assertEqual(len([b for b in at.button if b.key and b.key.startswith("pbtn_")]), 7)
        self.assertTrue({"ptab", "phead", "prow_rag_v5_data"} <= self.keys(at))   # 머리줄과 행이 한 표 상자 안에
        self.assertIn("검색 근거에 ‘한손검’이 있었지만 모델이 빈 배열을 반환했습니다.", md)
        self.assertIn('<div class="res lh15">', md)    # 문제점 표 줄 간격

    def test_tab2_response_time(self):
        at = self.tab(1)
        md = self.md(at)
        self.assertIn("Dev · 60문항", md)              # 응답 시간은 DEV 60문항 (한 런타임 측정)
        for card in ['<div class="kn">1.004<small>초</small></div><div class="dl good">▼ −0.659초</div>',
                     '<div class="kn">1.368<small>초</small></div><div class="dl good">▼ −0.037초</div>',
                     '<div class="kn">2.062<small>초</small></div><div class="dl good">▼ −1.323초</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 3)
        self.assertIn('<tr class="hl"><td>rag_v5_data</td><td class="num">1.004</td><td class="num">1.368</td>'
                      '<td class="num">2.062</td><td class="num">1.000</td><td class="num">4</td></tr>', md)
        self.assertIn("올바른 거절은 3 → 4건으로 늘었고", md)

    def test_tab3_aux(self):
        at = self.tab(2)
        md = self.md(at)
        for card in ['<div class="kn">99.2%</div><div class="dl good">▲ +8.3%p</div>',
                     '<div class="kn">100.0%</div><div class="dl good">▲ +25.0%p</div>',
                     '<div class="kn">0.0%</div><div class="dl good">▼ −3.5%p</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 3)
        self.assertIn('<tr class="hl"><td>rag_v5_data</td><td class="num">99.2%</td><td class="num">100.0%</td>'
                      '<td class="num">0.0%</td><td class="num">0 / 112</td></tr>', md)
        self.assertNotIn("판정 기준", md)                # '측정 기준'으로 바꿈
        self.assertIn('<div class="csub">ex) 지어낸 이름, 오타, 언어 오류, 근거와 상관 없는 값, 답 형식이 깨진 것</div>', md)
        self.assertIn("(비어있지 않은 답변 112건 중 근거 밖 항목 0건)", md)
        self.assertNotIn("유형 구분 없음", md)           # 모든 단계에 환각 목록이 있음

    def test_tab4_model_compare_v5_data(self):
        at = self.tab(3)
        md = self.md(at)
        for card in ['<div class="kl">Macro F1</div><div class="km"><span class="md">🥇</span>3B</div><div class="kv">1.0점(F1)</div>',
                     '🥇</span>1.5B · 3B · 7B</div><div class="kv">1.0점(F1)</div>',
                     '<div class="kl">캐릭터 조회 평균 응답 시간</div><div class="km"><span class="md">🥇</span>1.5B</div>'
                     '<div class="kv">1.077초</div>']:
            self.assertIn(card, md)
        self.assertEqual(len(at.get("plotly_chart")), 4)   # 1.5B 설명 그래프(c4b)는 rag_v4에서만
        self.assertEqual(md.count('<tr class="hl"><td>3B</td>'), 2)
        for gone in ["현재 문제점 및 개선 방향", "팀 결정 사항", "🔴", "🟠", "🟡"]:
            self.assertNotIn(gone, md)
        self.assertNotIn('class="chk"', md)

    def test_tab4_model_compare_v4(self):
        at = self.tab(3, "rag_v4")
        md = self.md(at)
        self.assertIn('<div class="kl">평균 응답 시간</div>', md)
        self.assertEqual(len(at.get("plotly_chart")), 5)
        self.assertIn("panel_c4b_accent", self.keys(at))   # 예외 강조 배경
        self.assertIn("1.5B 0.500 &lt; 3B 0.750", md)
        self.assertNotIn("정답이 많은 질문은 3B가 유리함", md)
        self.assertIn("현재 문제점 및 개선 방향", md)
        for gone in ["팀 결정 사항", "🔴", "🟠", "🟡"]:
            self.assertNotIn(gone, md)
        self.assertIn("<td>7B</td><td>T4 · fp16</td>", md)


if __name__ == "__main__":
    unittest.main()
