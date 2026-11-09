# demo (웹 화면, 서비스 담당)

질문을 입력하면 챗봇 API(`POST /ask`)의 답(`message`), 근거(`evidence`), 응답 시간을 보여 주는 Streamlit 화면입니다.

- `app.py`: 화면
- `client.py`: API 호출과 오류 안내 (streamlit 없이 테스트: `tests/test_demo_client.py`)
- `requirements.txt`: 웹 화면에만 필요한 라이브러리 (streamlit, httpx)

## 로컬에서 실행

1. 프로젝트 루트에 `.streamlit/secrets.toml` 파일을 만들고 서버 주소를 넣습니다 (이 파일은 `.gitignore`에 있어 깃에 안 올라감)

   ```toml
   API_URL = "http://127.0.0.1:8000"
   ```

2. 터미널 1: API 서버 `uvicorn api.main:app --reload`
3. 터미널 2: `pip install -r demo/requirements.txt` 후 `streamlit run demo/app.py` → 브라우저가 열림

## Streamlit Community Cloud 배포

1. 저장소, 브랜치를 고르고 실행 파일(Main file path)을 `demo/app.py`로 지정
2. Advanced settings → Secrets에 `API_URL = "https://xxxx.ngrok-free.app"` 입력 (코랩 + ngrok 주소)
3. 실행 파일과 같은 폴더의 `demo/requirements.txt`가 쓰이는지 배포 로그에서 확인 (streamlit, httpx만 설치되어야 함)

주의: ngrok 주소가 바뀌면 Cloud의 Secrets에서 `API_URL`을 새 주소로 고칩니다.
