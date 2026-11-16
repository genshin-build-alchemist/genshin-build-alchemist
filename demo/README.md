# demo (웹 화면, 서비스 담당)

"여행자 가이드봇" 챗봇 화면입니다. 질문을 챗봇 API(`POST /ask`)에 보내고, 답(`message`), 출처(`evidence`), 응답 시간을 보여 줍니다.
디자인은 와이어프레임 v10을 그대로 따르고, Streamlit **Custom Components v2**(`st.components.v2.component`)로 HTML/CSS/JS를 띄웁니다.
파이썬과 화면은 데이터만 주고받습니다.

## 파일

| 파일 | 역할 |
|---|---|
| `app.py` | 컴포넌트 등록, Streamlit 기본 화면 숨기기, 화면 이벤트 처리, 서버 호출 |
| `ui/chat.html` · `ui/chat.css` · `ui/chat.js` | 화면 (와이어프레임 v10에서 옮김) |
| `chat_logic.py` | 메시지 만들기, 한국 시간 표시, UID 검사, 서버 결과 → 답 카드 (streamlit 없음) |
| `client.py` | API 호출과 오류 안내 (streamlit 없음) |
| `fake.py` | 가짜 모드 답변 (와이어프레임 예시, 실제 데이터 아님) |
| `requirements.txt` | 웹 화면에만 필요한 라이브러리 (streamlit 1.67 이상, httpx) |

테스트: `tests/test_demo_client.py`, `tests/test_demo_chat_logic.py` (`python -m unittest discover -s tests -t .`)

## 로컬에서 실행

1. 프로젝트 루트에 `.streamlit/secrets.toml` 파일을 만들고 서버 주소를 넣습니다 (`.gitignore`에 있어 깃에 안 올라감)

   ```toml
   API_URL = "http://127.0.0.1:8000"
   ```

2. 터미널 1: API 서버 `uvicorn api.main:app --reload` (이 터미널은 닫지 않음)
3. 터미널 2: `pip install -r demo/requirements.txt` 후 `streamlit run demo/app.py` → 브라우저가 열림

`demo/ui/` 파일을 고치면 Streamlit을 껐다 켜야 반영됩니다 (컴포넌트를 한 번만 등록하도록 캐시함).

### 가짜 모드 (서버 없이 화면 확인)

```
CHAT_UI_FAKE=1 streamlit run demo/app.py
```

- 와이어프레임의 가짜 답변을 씁니다. 기본은 꺼져 있습니다.
- 질문에 "서버"가 들어가면 서버 무응답을 흉내 냅니다.
- UID 끝이 `000`이면 "확인 안 된 UID"(주황) 안내가 나오고, 그 밖의 UID는 예시 파티 카드가 나옵니다.

## 화면 ↔ 파이썬

- **화면 → 파이썬** (`setTriggerValue`): `ask`(질문 글자), `build`(UID), `help`(사용법), `build_guide`(빌드 안내)
- **파이썬 → 화면** (`data`): `{"messages": [...], "busy": bool, "examples": [...]}`
  - 메시지 `role`: `user` / `assistant` / `guide`. 칸 설명은 `chat_logic.py` 맨 위
  - `guide`(사용법·빌드 안내·"준비 중")는 대화 기록 DB에 저장하지 않습니다 → `chat_logic.saveable()`
- 질문 흐름: 질문과 대기 카드("답을 찾고 있어요…")를 먼저 그림 → 서버 답을 받아 대기 카드를 바꿈
- 서버 답과 근거는 화면에서 escape해서 글자로만 보여 줍니다 (HTML로 해석하지 않음)

| 서버 결과 | 화면 |
|---|---|
| 정상 | 답 + 📚 출처 N개 + ⏱ 응답 시간 |
| 꺼짐 / 120초 초과 | 🚨 서버 응답이 없어요. 서버 상태를 확인해 주세요. (빨강) |
| 그 밖의 오류 (500, 잘못된 주소 등) | 🚨 + `client.py` 안내 문구 (빨강) |
| `found=false` | ⚠️ 찾지 못했어요… (노랑) + 출처 없음 |
| `needs_recheck=true` | ℹ️ 재확인 필요… (회색) |
| `API_URL` 없음 | 🚨 서버 주소가 설정되지 않았어요… (빨강) |

빌드·파티 추천은 서버 기능이 없어서, 실제 모드에서는 올바른 UID에 "맞춤 빌드·파티 추천은 준비 중이에요" 안내만 보여 줍니다.

## 와이어프레임과 다른 점

- 서버 답에는 굵은 글씨 강조가 없습니다 (서버 `message`는 일반 글자)
- 예시 칩 질문은 와이어프레임 그대로라서, 서버가 답하지 못하는 질문이 있을 수 있습니다 (예: 여러 항목을 한 번에 묻는 질문)
- "원신 7.2 패치 기준"은 고정 글자입니다

## Streamlit Community Cloud 배포

1. 저장소, 브랜치를 고르고 실행 파일(Main file path)을 `demo/app.py`로 지정
2. Advanced settings → Secrets에 `API_URL = "https://xxxx.ngrok-free.app"` 입력 (코랩 + ngrok 주소)
3. 배포 로그에서 `demo/requirements.txt`가 쓰이고 streamlit 1.67 이상이 설치되는지 확인

주의: ngrok 주소가 바뀌면 Cloud의 Secrets에서 `API_URL`을 새 주소로 고칩니다.
