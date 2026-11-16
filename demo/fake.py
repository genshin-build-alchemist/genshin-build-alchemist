"""가짜 모드 (환경변수 CHAT_UI_FAKE=1일 때만): 서버 대신 와이어프레임 v10의 가짜 답변을 쓴다.

화면 확인·시연 연습용. 답의 숫자와 빌드 결과는 예시이고 실제 데이터가 아니다.
streamlit을 import하지 않는다 -> unittest로 검사한다 (tests/test_demo_fake.py).
"""
try:                                    # tests: from demo import fake
    from . import chat_logic as cl
except ImportError:                     # streamlit run demo/app.py: import fake
    import chat_logic as cl

# 기다리는 척하는 시간(초): 와이어프레임 setTimeout과 같게
DELAY_QA = 0.8
DELAY_SERVER_DOWN = 1.2

# 와이어프레임 QA (답은 고정 HTML이라 rich=True)
QA = {
    "카즈하의 원소와 무기 종류는 뭐야?": {
        "a": "카즈하의 원소는 <b>바람</b>, 무기 종류는 <b>한손검</b>이에요.", "rt": 1.12,
        "src": [{"k": "캐릭터", "t": "카즈하 · 기본 정보", "id": "char_kazuha#basic",
                 "x": "원소: 바람 · 무기: 한손검 · 소속: 이나즈마 · 성급: 5성"}]},
    "천공의 검의 기초 공격력과 부옵션은 뭐야?": {
        "a": "천공의 검은 90레벨 기준 기초 공격력 <b>608</b>, 부옵션은 <b>원소 충전 효율</b>이에요.", "rt": 1.41,
        "src": [{"k": "무기", "t": "천공의 검 · 기본 정보", "id": "weapon_skyward_blade#basic",
                 "x": "5성 한손검 · 기초 공격력 608(90레벨) · 부옵션: 원소 충전 효율"},
                {"k": "무기", "t": "천공의 검 · 효과", "id": "weapon_skyward_blade#passive",
                 "x": "치명타 확률 증가, 원소폭발 후 이동 속도·공격 속도 증가…"}]},
    "청록색 그림자 4세트 효과는 뭐야?": {
        "a": "청록색 그림자 4세트는 <b>확산 반응 피해가 증가</b>하고, 확산된 원소에 대한 <b>적의 원소 내성을 낮춰요</b>.",
        "rt": 1.28,
        "src": [{"k": "성유물", "t": "청록색 그림자 · 세트 효과", "id": "artifact_viridescent#set",
                 "x": "2세트: 바람 원소 피해 증가 · 4세트: 확산 반응 피해 증가, 확산된 원소의 내성 감소…"}]},
    "7.2 패치에서 새로 추가된 캐릭터는 누구야?": {
        "a": "제공된 자료에서는 7.2 패치에 추가된 캐릭터 목록을 찾을 수 없어요.", "rt": 0.95,
        "warn": cl.NOT_FOUND, "src": []},
}
DEFAULT = {"a": "(와이어프레임) 실제 앱에서는 서버 답변이 들어가요.", "rt": 1.48,
           "src": [{"k": "예시", "t": "예시 문서 · 근거 조각", "id": "doc_example#1",
                    "x": "검색된 근거 문장이 여기에 보여요."}]}


DELAY_BUILD = 1.7
# 빌드 추천 대기 중 단계 표시 (화면에서 0.5초마다 한 줄씩)
BUILD_STEPS = ["🔎 프로필을 불러오는 중…", "✔ 진열장 캐릭터 확인", "⚙️ 파티 조합과 성유물을 계산하는 중…"]
UID_CHECK = "⚠️ UID 또는 캐릭터 진열장 공개를 다시 확인해 주세요."
BUILD_INFO = "ℹ️ 7.2 패치 자료 기준이에요. 진열장에 추가되지 않은 캐릭터는 추천에 포함되지 않았어요."

# 와이어프레임 파티 예시 (실제 계정 정보가 아님)
PARTY = [
    {"n": "라이덴 쇼군", "c": "#9b7be0", "el": "번개", "role": "메인 딜러", "lv": 90, "set": "절연의 기치 4세트",
     "w": "예시 무기 A", "ms": "원충 / 번개 피해 / 치명", "sub": "원충 250%+ 목표", "now": 62,
     "tip": "원소 충전 효율이 목표보다 18% 낮아요. 시계를 원충 옵션으로 바꾸면 원소폭발을 더 자주 쓸 수 있어요."},
    {"n": "카즈하", "c": "#4fb8a4", "el": "바람", "role": "서포터", "lv": 90, "set": "청록색 그림자 4세트",
     "w": "예시 무기 B", "ms": "원마 / 원마 / 원마", "sub": "원소 마스터리 900+ 목표", "now": 84,
     "tip": "원소 마스터리가 812로 목표에 가까워요. 부옵션 원마를 조금만 더 올리면 돼요."},
    {"n": "향릉", "c": "#e0785a", "el": "불", "role": "서브 딜러", "lv": 80, "set": "절연의 기치 4세트",
     "w": "예시 무기 C", "ms": "원충 / 불 피해 / 치명", "sub": "원충 200%+ 목표", "now": 71,
     "tip": "레벨이 80이에요. 90으로 올리는 것이 성유물 교체보다 효과가 커요."},
    {"n": "베넷", "c": "#e0a64f", "el": "불", "role": "힐러·버퍼", "lv": 90, "set": "고난의 연극 4세트",
     "w": "예시 무기 D", "ms": "원충 / HP / 치유 보너스", "sub": "기초 공격력이 높은 무기 추천", "now": 90,
     "tip": "이미 잘 맞춰져 있어요! 지금 그대로 써도 좋아요."},
]


def build_answer(mid, uid):
    """가짜 빌드 추천 카드와 기다릴 시간(초). UID 끝이 000이면 '확인 안 된 UID'를 흉내 낸다."""
    question = f"UID {uid} 빌드 추천"
    if uid.endswith("000"):
        return cl.assistant_message(mid, question, kind="build", uid=uid, seconds=1.04,
                                    notes=[cl.note("orange", UID_CHECK)]), DELAY_BUILD
    sources = [
        {"k": "내 정보", "t": f"내 진열장 (UID {uid})", "id": f"enka:uid/{uid}",
         "x": "공개 진열장 캐릭터 8명 · 레벨·성유물·무기·최종 스탯"},
        {"k": "성유물", "t": "절연의 기치 · 세트 효과", "id": "artifact_emblem#set",
         "x": "2세트: 원소 충전 효율 증가 · 4세트: 원소 충전 효율에 비례해 원소폭발 피해 증가"},
        {"k": "성유물", "t": "청록색 그림자 · 세트 효과", "id": "artifact_viridescent#set",
         "x": "4세트: 확산 반응 피해 증가, 확산된 원소의 내성 감소"},
    ]
    # uid는 숫자만 통과한 값(cl.is_uid)이라 HTML 안에 넣어도 안전하다
    message = (f"여행자 <b>{uid}</b>님의 최적의 추천 파티는 <b>번개·불 과부하+확산 파티</b>입니다. "
               "캐릭터를 누르면 빌드를 자세히 볼 수 있어요.")
    return cl.assistant_message(mid, question, kind="build", uid=uid, message=message, rich=True,
                                party=PARTY, notes=[cl.note("info", BUILD_INFO)], sources=sources,
                                seconds=3.82), DELAY_BUILD


def answer(mid, question):
    """가짜 답 카드와 기다릴 시간(초). 질문에 '서버'가 있으면 서버 무응답을 흉내 낸다."""
    if "서버" in question:
        return cl.error_message(mid, question), DELAY_SERVER_DOWN
    r = QA.get(question.strip(), DEFAULT)
    notes = [cl.note("warn", r["warn"])] if r.get("warn") else []
    msg = cl.assistant_message(mid, question, message=r["a"], rich=True, notes=notes,
                               sources=r["src"], seconds=r["rt"])
    return msg, DELAY_QA
