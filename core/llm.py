"""실제 LLM 연결 (Hugging Face transformers). 평가 노트북 셀 6의 generate()와 같은 방식이라 평가와 같은 답이 나온다.

쓰는 곳
  - 챗봇 API : 환경변수 GBA_ANSWERER=llm 이면 api/main.py 가 answerer_from_env()로 모델을 불러온다
  - 코랩      : from core.llm import load_generate; generate = load_generate()

환경변수 (api/main.py 가 읽는다. 없으면 기본값)
  GBA_ANSWERER       mock(기본, 규칙 기반 모의 답변기, GPU 필요 없음) / llm(실제 모델)
  GBA_MODEL          Qwen/Qwen2.5-3B-Instruct
  GBA_DEVICE         비우면 자동: cuda(코랩 T4) > mps(애플 실리콘 맥) > cpu(느림)
  GBA_METHOD         rag_v5 (core/answer.py build_prompt의 방식 이름. rag_v4도 가능: 프롬프트 같음)
  GBA_POSTPROCESS    1(기본, 근거 이름으로 맞추기) / 0(끄기)
  GBA_MAX_NEW_TOKENS 160

설치: pip install -r requirements-llm.txt  (torch는 컴퓨터마다 설치 방법이 달라서 requirements.txt와 따로 둔다)
"""
import os
import threading

from core.answer import LLMAnswerer, MockAnswerer

DEFAULT_MODEL = "Qwen/Qwen2.5-3B-Instruct"
MAX_NEW_TOKENS = 160          # 노트북과 같다 (filter 질문은 이름이 최대 10개)
ANSWERERS = ("mock", "llm")


def pick_device(torch, device=None):
    """장치 고르기. 지정하면 그대로, 아니면 cuda > mps > cpu."""
    if device:
        return device
    if torch.cuda.is_available():
        return "cuda"
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        return "mps"
    return "cpu"


def make_generate(tokenizer, model, torch, max_new_tokens=MAX_NEW_TOKENS):
    """프롬프트 -> 모델 답변 함수. 샘플링 끔(매번 같은 답), ']'가 나오면 멈춘다 (노트북 셀 6과 같다).
    API에 질문이 동시에 와도 GPU 메모리가 넘치지 않게 한 번에 하나씩 생성한다."""
    lock = threading.Lock()

    def generate(prompt, max_new_tokens=max_new_tokens, stop_strings=("]",)):
        """stop_strings: 이 글자가 나오면 멈춘다. 이름 목록은 ']'(기본), 문장 답은 None(배열이 여러 겹일 수 있어 끝까지)."""
        messages = [{"role": "user", "content": prompt}]
        text = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = tokenizer(text, return_tensors="pt").to(model.device)
        kwargs = dict(max_new_tokens=max_new_tokens, do_sample=False, pad_token_id=tokenizer.eos_token_id)
        with lock, torch.no_grad():
            out = None
            if stop_strings:
                try:
                    out = model.generate(**inputs, **kwargs, stop_strings=list(stop_strings), tokenizer=tokenizer)
                except (TypeError, ValueError):   # 오래된 transformers는 stop_strings를 모른다
                    out = None
            if out is None:
                out = model.generate(**inputs, **kwargs)
        return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)

    return generate


def load_generate(model_id=DEFAULT_MODEL, device=None, max_new_tokens=MAX_NEW_TOKENS):
    """모델을 불러와 generate 함수를 돌려준다. 처음 한 번은 내려받느라 몇 분 걸린다 (3B 모델 약 6GB)."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = pick_device(torch, device)
    dtype = torch.float16 if device in ("cuda", "mps") else torch.float32   # T4는 bf16이 안 된다
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    extra = {"device_map": "auto"} if device == "cuda" else {}
    try:
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype, **extra)
    except TypeError:   # transformers 버전에 따라 인자 이름이 다르다
        model = AutoModelForCausalLM.from_pretrained(model_id, torch_dtype=dtype, **extra)
    if device != "cuda":
        model = model.to(device)
    model.eval()
    print(f"모델 준비: {model_id} ({device}, {str(dtype).replace('torch.', '')})")
    return make_generate(tokenizer, model, torch, max_new_tokens)


def answerer_from_env(env=None):
    """환경변수 -> 답변기. 기본은 모의 답변기라 GPU·torch 없이도 API가 뜬다."""
    env = os.environ if env is None else env
    kind = (env.get("GBA_ANSWERER") or "mock").strip().lower()
    if kind not in ANSWERERS:
        raise ValueError(f"GBA_ANSWERER는 {ANSWERERS} 중 하나: {kind!r}")
    if kind == "mock":
        return MockAnswerer()
    model_id = env.get("GBA_MODEL") or DEFAULT_MODEL
    generate = load_generate(model_id, env.get("GBA_DEVICE") or None,
                             int(env.get("GBA_MAX_NEW_TOKENS") or MAX_NEW_TOKENS))
    return LLMAnswerer(generate, name=model_id, method=env.get("GBA_METHOD") or "rag_v5",
                       postprocess=(env.get("GBA_POSTPROCESS") or "1") != "0")
