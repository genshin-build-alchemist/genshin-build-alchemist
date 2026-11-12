"""lib/charts.py 테스트 (그래프 구성 · 툴팁 굵게 · 값 라벨).

실행 (저장소 루트에서): python -m unittest discover -s dashboard/tests
"""
import sys
import unittest
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(DASHBOARD))

from lib import charts  # noqa: E402

ROWS = [
    {"stage": "baseline", "change": "질문만 넣음", "f1": 0.0111, "empty": 11, "avg": 1.895, "median": 1.1,
     "max": 8.437, "type_avg": {"lookup": 1.112, "filter": 4.01, "unknown": 1.275}, "n": 60},
    {"stage": "rag_v4", "change": "성급·지역 예시", "f1": 0.7958, "empty": 4, "avg": 2.384, "median": 1.482,
     "max": 6.59, "type_avg": {"lookup": 1.548, "filter": 4.713, "unknown": 1.42}, "n": 60},
]


class TimeChartsTest(unittest.TestCase):
    def test_tooltip_html(self):
        """우리 HTML 툴팁: 제목 / 값 줄(숫자 <b>) / 구분선 상자(.c) 안의 개선점."""
        lines, footer = charts.time_tip_parts(ROWS[1])
        html = charts.tip_html(lines, footer)
        self.assertTrue(html.startswith('<div class="h"><b>rag_v4</b></div>'))
        self.assertIn("<div>Macro F1 <b>0.796</b> · 빈 답 <b>4개</b></div>", html)
        self.assertIn("평균 <b>2.384초</b>", html)
        self.assertTrue(html.endswith('<div class="c">개선점: 성급·지역 예시</div>'))
        self.assertNotIn('class="c"', charts.tip_html(["제목"]))           # 개선점 없으면 구분선도 없음

    def test_tooltip_escapes_text(self):
        lines, footer = charts.time_tip_parts(dict(ROWS[1], stage="<x>", change="a&b"))
        self.assertIn("&lt;x&gt;", lines[0])
        self.assertEqual(footer, "개선점: a&amp;b")

    def test_hover_has_both(self):
        """customdata = 우리 툴팁, hovertext = Plotly 기본 툴팁(스크립트가 안 돌 때)."""
        h = charts.hover([(["<b>t</b>", "v"], "f")])
        self.assertEqual(h["customdata"], ['<div class="h"><b>t</b></div><div>v</div><div class="c">f</div>'])
        self.assertEqual(h["hovertext"], ["<b>t</b><br>v<br>f"])

    def test_f1_and_time(self):
        fig = charts.f1_and_time(ROWS)
        self.assertEqual([t.type for t in fig.data], ["scatter", "bar", "bar"])
        self.assertEqual(list(fig.data[0].text), ["0.011", "0.796"])        # 점 위 값 라벨
        self.assertEqual(list(fig.data[2].text), ["1.1", "1.482"])          # 중앙값 막대 라벨
        self.assertFalse(fig.layout.showlegend)                             # 범례는 HTML로 따로
        # 두 칸이 x축 하나를 같이 씀 -> 점선 하나, 툴팁 하나 (막대는 툴팁 건너뜀)
        self.assertEqual([t.yaxis for t in fig.data], ["y", "y2", "y2"])
        self.assertEqual((fig.layout.hovermode, fig.layout.hoversubplots), ("x", "axis"))
        self.assertFalse(fig.layout.xaxis.showspikes)                       # 점선은 스크립트가 그림
        self.assertEqual(fig.layout.meta, {"spike": True})
        self.assertEqual(fig.data[0].customdata[1], charts.tip_html(*charts.time_tip_parts(ROWS[1])))
        self.assertEqual([t.hoverinfo for t in fig.data[1:]], ["skip", "skip"])
        # 칸 구분은 선이 아니라 둥근 박스 두 개
        self.assertEqual([s.yref for s in fig.layout.shapes], ["y domain", "y2 domain"])
        self.assertFalse(fig.layout.xaxis.showline)

    def test_trend_line(self):
        slope, icpt = charts.trend_line([0, 1, 2], [1, 3, 5])
        self.assertAlmostEqual(slope, 2.0)
        self.assertAlmostEqual(icpt, 1.0)

    def test_empty_vs_time(self):
        fig = charts.empty_vs_time(ROWS, -0.904, 60)
        self.assertEqual(len(fig.data), 2)                                  # 추세선 + 점
        self.assertIn("r ≈ -0.904 (2개 단계)", fig.layout.annotations[0].text)
        self.assertEqual(fig.layout.xaxis.title.text, "빈 답 (개, 60문항 중)")
        self.assertEqual(list(fig.layout.xaxis.range), [0, 60])             # 0이 맨 왼쪽
        self.assertFalse(fig.layout.xaxis.showgrid)                         # 세로 눈금선 없음
        self.assertTrue(fig.layout.yaxis.showgrid)                          # 가로 눈금선은 남김
        self.assertEqual(len(fig.layout.shapes), 1)                         # 테두리 대신 둥근 박스
        self.assertFalse(fig.layout.xaxis.showline)

    def test_time_by_type(self):
        fig = charts.time_by_type(ROWS)
        self.assertEqual(len(fig.data), 2)                                  # 조회 · 조건 (데이터 없음 제외)
        self.assertEqual(list(fig.data[1].y), [4.01, 4.713])
        self.assertEqual(fig.layout.barmode, "group")
        self.assertIsNone(fig.layout.yaxis.title.text)                      # 왼쪽 축 제목 없음
        self.assertEqual(fig.layout.yaxis.ticksuffix, "초")                 # '2초' 형식
        self.assertTrue(fig.layout.yaxis.showgrid)                          # 가로 눈금선

    def test_common_look(self):
        a, c = charts.f1_and_time(ROWS), charts.time_by_type(ROWS)
        self.assertEqual(a.layout.plot_bgcolor, "rgba(0,0,0,0)")            # 바탕 투명 (둥근 패널이 보임)
        self.assertFalse(a.layout.yaxis.showgrid)                           # 눈금선 없음
        self.assertFalse(a.layout.yaxis.showticklabels)                     # 눈금 숫자 없음
        self.assertEqual((a.layout.bargap, a.layout.margin.l), (c.layout.bargap, c.layout.margin.l))   # 막대 너비 같게
        self.assertFalse(a.layout.hoverlabel.showarrow)

    def test_c2c_bottom_margin_smaller(self):
        self.assertLess(charts.time_by_type(ROWS).layout.margin.b, charts.f1_and_time(ROWS).layout.margin.b)

AUX = [
    {"stage": "baseline", "change": "질문만 넣음", "acc": 0.0, "ref": 0.0, "hal": 0.9184, "answered": 49, "hn": 45,
     "n": 60, "types": {"lookup": 25, "filter": 16, "unknown": 4, "other": 0}},
    {"stage": "rag_v4", "change": "성급·지역 예시", "acc": 0.7167, "ref": 0.75, "hal": 0.0893, "answered": 56, "hn": 5,
     "n": 60, "types": None},
]


class AuxChartsTest(unittest.TestCase):
    def test_rates(self):
        fig = charts.aux_rates(AUX)
        self.assertEqual([t.name for t in fig.data], ["정답률", "거절 정확도", "환각률"])
        self.assertEqual({t.marker.symbol for t in fig.data}, {None})   # 점은 모두 기본 동그라미
        self.assertEqual(fig.layout.meta, {"spike": True})
        self.assertIsNotNone(fig.data[0].customdata)            # 툴팁은 첫 선에만
        self.assertEqual(fig.data[1].hoverinfo, "skip")
        tip = fig.data[0].customdata[1]
        self.assertIn("정답률 <b>0.717</b>", tip)
        self.assertIn("환각 <b>5건</b> / 답한 문항 <b>56개</b>", tip)
        self.assertIn('<div class="c">개선점: 성급·지역 예시</div>', tip)

    def test_answered_stack(self):
        fig = charts.answered_stack(AUX)
        self.assertEqual(fig.layout.barmode, "stack")
        self.assertEqual(list(fig.data[0].y), [4, 51])             # 근거 안에서 답함 = 답함 - 환각
        self.assertEqual(list(fig.data[1].y), [45, 5])
        self.assertEqual(list(fig.data[1].text), ["45 / 49", "5 / 56"])
        self.assertIn("빈 답 <b>4개</b>", fig.data[1].customdata[1])

    def test_hal_by_type(self):
        fig = charts.hal_by_type(AUX)
        lookup, filt, unknown, total = fig.data
        self.assertAlmostEqual(lookup.x[0] + filt.x[0] + unknown.x[0], 0.9184)   # 유형 칸을 합치면 환각률
        self.assertAlmostEqual(filt.x[0], 0.9184 * 16 / 45)
        self.assertEqual(list(total.text), ["  <b>0.918</b>", "  <b>0.089</b>"])
        self.assertEqual(len(fig.layout.shapes), 2)              # 둥근 박스 + 유형 없는 단계의 점선 테두리
        self.assertIn("유형별 내역 없음", total.customdata[1])
        self.assertIn("조건 검색 <b>16건</b>", total.customdata[0])


def _model(size, gpu, prec, f1, avg, color="#378ADD"):
    return {"size": size, "gpu": gpu, "precision": prec, "label": f"{size} · {gpu} · {prec}", "f1": f1, "lookup": 1.0,
            "filter": 0.483, "avg": avg, "median": 1.043, "lookup_t": 1.036, "filter_t": 1.462, "precision_v": 0.7528,
            "recall": 0.67, "ans_len": 3.0625, "memory": "2.9GB", "color": color}


MODELS = [_model("1.5B", "L4", "fp16", 0.8621, 1.142), _model("3B", "T4", "fp16", 0.814, 2.543)]


class ModelChartsTest(unittest.TestCase):
    def test_model_f1(self):
        fig = charts.model_f1(MODELS)
        self.assertEqual([t.name for t in fig.data], ["전체", "캐릭터 조회", "조건 검색"])
        self.assertIn("메모리 2.9GB", fig.layout.xaxis.ticktext[0])
        self.assertIn("Qwen2.5-1.5B · L4 · fp16", fig.data[0].customdata[0])

    def test_precision_recall(self):
        fig = charts.precision_recall(MODELS)
        self.assertEqual(list(fig.data[1].text), ["0.753", "0.753"])          # 정밀도 라벨 (위)
        self.assertEqual(fig.data[2].textposition, "bottom center")           # 재현율 라벨은 아래 (겹치지 않게)
        self.assertEqual((fig.data[1].textfont.color, fig.data[2].textfont.color), (charts.PREC_COLOR, charts.RECALL_COLOR))
        self.assertEqual(fig.data[3].text[0], "<b>3.1명</b>")                 # 답 길이는 소수 1자리
        self.assertEqual(fig.data[3].xaxis, "x2")
        self.assertIn("조건 검색 평균 답 길이 <b>3.1명</b>", fig.data[1].customdata[0])

    def test_model_time(self):
        rows = [MODELS[0], dict(MODELS[1], filter_t=3.977)]                   # 실제처럼 7B 조건 검색이 느릴 때
        fig = charts.model_time(rows)
        self.assertEqual(fig.layout.meta, {"spike": True})
        self.assertEqual(fig.data[1].textposition[0], "middle left")          # 전체 평균 라벨이 조건 검색 점과 가까우면 왼쪽
        self.assertEqual(fig.data[0].textfont.color, charts.COLOR["filter"])  # 숫자 색 = 선 색
        self.assertEqual(list(fig.layout.xaxis.range), [-0.35, 1.35])         # 양 끝 여백

    def test_combo_bars_t4_faded(self):
        fig = charts.combo_bars(MODELS, "avg", unit="초", tickvals=[0, 1, 2, 3])
        self.assertEqual(list(fig.data[0].marker.opacity), [1, 0.6])
        self.assertEqual(list(fig.data[0].y), ["1.5B · L4 · fp16", "3B · T4 · fp16"])
        self.assertEqual(fig.data[0].text[1], "  <b>2.543초</b>")
        self.assertIsNone(fig.layout.xaxis.ticktext)                                     # 눈금은 숫자만
        self.assertIsNone(fig.layout.xaxis.ticksuffix)
        self.assertGreater(fig.layout.xaxis.range[1], 2.543)                              # 가장 긴 막대가 안 잘림



class PerfChartsTest(unittest.TestCase):
    def test_perf_lines(self):
        rows = [{"stage": "baseline", "change": "질문만 넣음", "f1": 0.0208, "lookup": 0.0059, "filter": 0.0, "unknown": 0.25},
                {"stage": "rag_v4", "change": "성급·지역 예시", "f1": 0.8165, "lookup": 0.9885, "filter": 0.2616, "unknown": 0.75}]
        fig = charts.perf_lines(rows)
        self.assertEqual([t.name for t in fig.data], ["데이터 없음", "조건 검색", "캐릭터 조회", "전체"])   # 전체가 맨 위
        self.assertEqual(fig.layout.meta, {"spike": True})
        tip = fig.data[3].customdata[1]
        self.assertLess(tip.index("전체"), tip.index("데이터 없음"))     # 툴팁은 전체 → 유형 순
        self.assertIn("전체 <b>0.817</b>", tip)
        self.assertIn("캐릭터 조회 <b>0.989</b>", tip)
        self.assertIn('<div class="c">개선점: 성급·지역 예시</div>', tip)


if __name__ == "__main__":
    unittest.main()
