// 여행자 가이드봇 화면 (와이어프레임 v10의 JS를 옮김)
// 파이썬 -> JS: data = {messages, busy, examples}
// JS -> 파이썬: setTriggerValue("ask"|"build"|"help"|"build_guide", 값)
// data가 바뀔 때마다 이 함수가 다시 불린다 -> 화면 상태는 parentElement.__gb에 두고, 새로 생긴/바뀐 메시지만 다시 그린다.

// Chrome·Edge 등도 user agent에 "Safari"가 들어 있어서, 크롬 계열 표시가 없을 때만 Safari로 본다
const isSafari = (ua) => /safari/i.test(ua) && !/chrome|chromium|crios|fxios|edg|opr|android/i.test(ua);
const isUid = (s) => /^\d{9,10}$/.test(String(s || "").trim());
// 서버 답·근거는 LLM이 만든 글이라 HTML로 해석되지 않게 바꾼다
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

const HERO = `<div class="hero"><div class="big">✦</div>
  <h1>여행자 가이드봇</h1>
  <p>캐릭터·무기·성유물·패치 정보·빌드 조합 추천까지! 원신에 대해 궁금한 모든 것을 물어보세요.</p>
  <div class="tips">
    <div class="tip-card"><b><span class="ti">💬</span>원신 지식 Q&amp;A</b>캐릭터, 무기, 성유물, 재료, 원소 반응 등 원신에 관한 모든 것을 질문하고 답변을 받아 보세요.</div>
    <div class="tip-card"><b><span class="ti">👥</span>나만의 파티 추천</b>내가 보유한 캐릭터를 기반으로 최고의 4인 파티를 추천받아 보세요.</div>
    <div class="tip-card"><b><span class="ti">⚔️</span>캐릭터 최적 빌드</b>캐릭터별 추천 무기, 성유물 세트, 주옵션, 부옵션 및 육성 우선순위 확인해 보세요.</div>
    <div class="tip-card"><b><span class="ti">📰</span>최신 패치 브리핑</b>신규 캐릭터, 이벤트, 업데이트, 밸런스 변경 등 최신 소식 확인해 보세요.</div>
  </div>
  </div>`;

// 사용법·안내 카드 (고정 문구, 기록·DB 저장 안 함)
const GUIDE = {
  help: () => `<span class="gtag">사용법</span>
   <div class="ans">👋🏻 반가워요, 여행자님! 여행자 가이드봇은 이렇게 사용해 주세요.</div>
   <div class="gsec">
     <div class="gbox"><b>💬 원신 지식 Q&amp;A</b>캐릭터, 무기, 성유물, 재료, 원소 반응 등 원신에 관한 모든 것을 질문하고 답변을 받아 보세요.</div>
     <div class="gbox"><b>👥 나만의 파티 추천</b>내가 보유한 캐릭터를 기반으로 최고의 4인 파티를 추천받아 보세요.</div>
     <div class="gbox"><b>⚔️ 캐릭터 최적 빌드</b>캐릭터별 추천 무기, 성유물 세트, 주옵션, 부옵션 및 육성 우선순위 확인해 보세요.</div>
     <div class="gbox"><b>📰 최신 패치 브리핑</b>신규 캐릭터, 이벤트, 업데이트, 밸런스 변경 등 최신 소식 확인해 보세요.</div>
   </div>
   <div class="actions"><button class="act primary" data-act="ex">💬 예시 질문 해 보기</button><button class="act" data-act="build-on">⚔️ 맞춤 빌드·파티 추천 시작</button></div>`,
  build_guide: () => `<span class="gtag">안내</span>
   <div class="ans">⚔️ <b>맞춤 빌드·파티 추천</b>을 시작할게요! 내가 보유한 캐릭터와 아이템 정보를 불러오려면 <b class="gr">UID 확인</b>이 필요해요. 아래와 같이 진행해 주세요.</div>
   <div class="whatuid"><div class="wi">🪪</div><div>
     <span class="wt">UID가 뭔가요?</span>
     <p>원신 계정마다 하나씩 붙는 <b>9자리 고유 번호</b>예요.<br>게임 속 ‘내 회원 번호’라고 생각하면 돼요. 친구 추가할 때 쓰는 그 번호이고, 비밀번호가 아니라서 안심해도 돼요. <span class="eg">예) 812345678</span></p>
   </div></div>
   <div class="stepcards">
     <div class="sc"><div class="top"><span class="no">STEP 1</span></div><b>캐릭터 진열장 공개</b><em>닉네임 우측 수정 아이콘 📝 클릭 → 프로필 설정 → 캐릭터 진열장</em>에 추천받을 캐릭터를 추가하고 <em>캐릭터 상세정보 보기</em>를 켜 주세요.</div>
     <div class="sc"><div class="top"><span class="no">STEP 2</span></div><b>내 UID 확인</b>게임 화면 오른쪽 아래 또는 좌측&nbsp;상단&nbsp;<em>페이몬 메뉴 → 프로필</em> 바로 밑에 있는 <em>9자리 숫자</em>를 복사해 주세요.</div>
     <div class="sc"><div class="top"><span class="no">STEP 3</span></div><b>UID 입력</b>아래 입력창에 복사한 UID를 붙여넣고 <em>추천받기</em>를 눌러 주세요.</div>
   </div>
   <div class="safe"><span>🔐</span><span>로그인이나 비밀번호는 필요 없어요. UID로 공개된 <b style="display:inline;color:var(--g-text)">게임 캐릭터·아이템 정보만</b> 가져오고, 이름·연락처·계정 정보 같은 개인정보는 수집하지 않아요.</span></div>
   <div class="actions"><button class="act primary" data-act="demo-uid">예시 UID로 체험하기</button><button class="act" data-act="qa-mode">질문 모드로 돌아가기</button></div>`,
  // 서버에 빌드 기능이 없을 때: 올바른 UID에 대한 안내
  build_ready: (m) => `<span class="gtag">안내</span>
   <div class="ans">UID <b>${esc(m.uid)}</b>를 확인했어요. ⚔️ <b>맞춤 빌드·파티 추천</b>은 준비 중이에요. 그동안 캐릭터·무기·성유물·패치 정보를 질문해 보세요!</div>
   <div class="actions"><button class="act primary" data-act="qa-mode">💬 질문 모드로 돌아가기</button></div>`,
};

function srcFoot(src, extra = "") {
  if (!src.length) return `<div class="foot"><span class="src-none">출처 없음 — 자료에서 찾지 못했어요</span>${extra}</div>`;
  return `<div class="foot"><button class="src-btn" data-act="src">📚 출처 ${src.length}개 ›</button>${extra}</div>`;
}

function partyHtml(party) {
  return `<div class="party">${party.map((p, i) => `<div class="pc${i === 0 ? " on" : ""}" data-act="pc" data-i="${i}"><div class="face" style="background:${esc(p.c)}">${esc(p.n[0])}</div><b>${esc(p.n)}</b><small>${esc(p.el)} · Lv.${esc(p.lv)}</small><br><span class="role">${esc(p.role)}</span></div>`).join("")}</div>
        <div class="detail"></div>`;
}

function partyDetail(card, party, i) {
  card.querySelectorAll(".pc").forEach((x, j) => x.classList.toggle("on", j === i));
  const p = party[i];
  card.querySelector(".detail").innerHTML = `<h5>${esc(p.n)} <span class="role">${esc(p.role)}</span></h5>
        <div class="drow"><span>성유물</span><span>${esc(p.set)}</span></div><div class="drow"><span>무기</span><span>${esc(p.w)}</span></div>
        <div class="drow"><span>주옵션</span><span>${esc(p.ms)}</span></div><div class="drow"><span>목표</span><span>${esc(p.sub)}</span></div>
        <div class="drow"><span>💡 한마디</span><span>${esc(p.tip)}</span></div>`;
}

// 답 카드 안쪽 HTML
function answerBody(m) {
  const notes = (m.notes || []).map((n) => `<div class="note ${esc(n.level)}">${esc(n.text)}</div>`).join("");
  if (m.status === "pending") {
    return `<div class="loading">${m.steps ? `<span>${esc(m.steps[0])}</span>` : "답을 찾고 있어요…"}</div>`;
  }
  if (m.status === "error") return notes;
  const orange = (m.notes || []).some((n) => n.level === "orange");
  if (orange) {
    return `${notes}<div class="actions"><button class="act primary" data-act="retry" data-uid="${esc(m.uid)}">다시 시도</button><button class="act" data-act="how">진열장 설정 방법 보기</button></div>`;
  }
  const ans = m.message ? `<div class="ans">${m.rich ? m.message : esc(m.message)}</div>` : "";
  const party = m.party ? partyHtml(m.party) : "";
  const extra = m.party ? `<button class="act" data-act="again">⚔️ 다른 UID로 추천받기</button><button class="act" data-act="qa-mode">💬 질문 모드로 돌아가기</button>` : "";
  return ans + party + notes + srcFoot(m.sources || [], extra);
}

function init(root) {
  const $ = (id) => root.getElementById ? root.getElementById(id) : root.querySelector("#" + id);
  const S = {
    root, $, el: $("gbRoot"), col: $("col"), scroll: $("scroll"), box: $("box"), inp: $("inp"), send: $("send"),
    build: false, busy: false, localBusy: false, started: false,
    nodes: new Map(), msgs: [], examples: [], activeSrc: null, trigger: () => {},
  };
  const { inp, send } = S;

  S.fire = (name, value) => S.trigger(name, value);
  S.refresh = () => {
    const v = inp.value.trim();
    send.disabled = S.busy || (S.build ? !isUid(v) : !v);
    $("cnt").textContent = S.build ? `${inp.value.length} / 9` : `${inp.value.length} / 300`;
  };
  S.renderEx = () => {
    $("exRow").innerHTML = S.examples.map((e, i) => `<button class="ex${e.build ? " build" : ""}${e.build && S.build ? " on" : ""}" data-i="${i}">${e.cat ? `<span class="cat">${esc(e.cat)}</span>` : ""}${esc(e.q)}</button>`).join("");
  };
  // 질문 모드 / UID 입력 모드 (화면 안에서만 바뀜)
  S.setBuild = (on, showGuide = true) => {
    S.build = on; S.box.classList.toggle("build", on);
    inp.value = ""; inp.maxLength = on ? 10 : 300; inp.setAttribute("inputmode", on ? "numeric" : "text");
    inp.placeholder = on ? "복사한 UID 9자리를 붙여넣어 주세요" : "원신에 대해 무엇이든 물어보세요";
    send.textContent = on ? "추천받기" : "질문하기";
    S.renderEx(); S.refresh(); inp.focus();
    if (on && showGuide && !S.busy) S.fire("build_guide", true);
  };
  S.lock = () => { S.localBusy = true; S.busy = true; S.refresh(); };
  S.askQA = (text) => {
    text = String(text || "").trim(); if (!text || S.busy) return;
    if (S.build) S.setBuild(false);
    inp.value = ""; S.lock(); S.fire("ask", text);
  };
  S.askBuild = (uid) => {
    uid = String(uid || "").trim(); if (S.busy || !isUid(uid)) return;
    if (!S.build) S.setBuild(true, false);
    inp.value = ""; S.lock(); S.fire("build", uid);
  };
  S.submit = () => { const v = inp.value.trim(); if (S.build || isUid(v)) S.askBuild(v); else S.askQA(v); };

  inp.oninput = () => { if (S.build) inp.value = inp.value.replace(/\D/g, ""); S.refresh(); };
  inp.onkeydown = (e) => { if (e.key === "Enter" && !e.isComposing && !send.disabled) { e.preventDefault(); S.submit(); } };
  send.onclick = S.submit;
  $("preX").onclick = () => S.setBuild(false);
  $("exRow").onclick = (e) => {
    const b = e.target.closest(".ex"); if (!b) return;
    const ex = S.examples[+b.dataset.i]; ex.build ? S.setBuild(true) : S.askQA(ex.q);
  };
  $("helpBtn").onclick = () => { if (!S.busy) S.fire("help", true); };
  $("spClose").onclick = () => closeSrc(S);
  root.querySelectorAll(".theme-sw button").forEach((b) => b.onclick = () => {
    S.el.classList.toggle("dark", b.dataset.theme === "dark");
    root.querySelectorAll(".theme-sw button").forEach((x) => x.classList.toggle("on", x === b));
  });

  // 카드 안 버튼들 (다시 그려도 동작하도록 한 곳에서 받음)
  S.col.onclick = (e) => {
    const t = e.target.closest("[data-act]"); if (!t) return;
    const wrap = t.closest("[data-mid]"); const m = wrap && S.msgs.find((x) => String(x.id) === wrap.dataset.mid);
    switch (t.dataset.act) {
      case "ex": S.askQA(S.examples.find((x) => !x.build)?.q); break;
      case "build-on": S.setBuild(true); break;
      case "demo-uid": S.askBuild("812345678"); break;
      case "qa-mode": S.setBuild(false); break;
      case "retry": S.askBuild(t.dataset.uid); break;
      case "how": if (!S.busy) S.fire("build_guide", true); break;
      case "again": S.setBuild(true, false); break;
      case "src": if (m) toggleSrc(S, m, wrap); break;
      case "pc": if (m) partyDetail(wrap.querySelector(".card"), m.party, +t.dataset.i); break;
    }
  };

  S.col.innerHTML = HERO;
  inp.placeholder = "원신에 대해 무엇이든 물어보세요";
  // Safari는 같은 굵기도 진하게 보여서 따로 조정 (chat.css의 .is-safari)
  if (isSafari(navigator.userAgent)) S.el.classList.add("is-safari");
  return S;
}

/* ----- 출처 패널 ----- */
function toggleSrc(S, m, wrap) {
  if (S.activeSrc === m.id) { closeSrc(S); return; }
  closeSrc(S);
  const src = m.sources || [];
  wrap.querySelector(".card").classList.add("active");
  wrap.querySelector(".src-btn")?.classList.add("on");
  S.activeSrc = m.id;
  S.$("spT").textContent = `출처 ${src.length}개`;
  S.$("spQ").textContent = `질문: ${m.question || ""}`;
  S.$("spList").innerHTML = src.map((s, i) => `<details class="si-item"${i === 0 ? " open" : ""} name="src"><summary><span class="n">${i + 1}</span><span>${esc(s.t)}</span><span class="k">${esc(s.k)}</span><span class="cv">▾</span></summary>
    <div class="si-body"><div class="id">${esc(s.id)}</div>${esc(s.x)}</div></details>`).join("");
  S.$("sp").classList.add("open");
}
function closeSrc(S) {
  S.$("sp").classList.remove("open");
  S.root.querySelectorAll(".card.active").forEach((c) => c.classList.remove("active"));
  S.root.querySelectorAll(".src-btn.on").forEach((c) => c.classList.remove("on"));
  S.activeSrc = null;
}

/* ----- 메시지 1개 -> 화면 요소 ----- */
function buildNodes(m, showDate) {
  const out = [];
  if (showDate) {
    const d = document.createElement("div"); d.className = "divider"; d.textContent = m.date; out.push(d);
  }
  const w = document.createElement("div");
  w.dataset.mid = m.id;
  if (m.role === "user") {
    w.className = "q"; w.id = "q" + m.id;
    const body = m.kind === "build" ? `<span class="tag">⚔️ 맞춤 빌드·파티 추천</span>UID ${esc(m.uid)}` : esc(m.text);
    w.innerHTML = `<div class="bubble">${body}</div><div class="stamp">${esc(m.time)}</div>`;
  } else {
    const guide = m.role === "guide";
    const html = guide ? (GUIDE[m.kind] || (() => ""))(m) : answerBody(m);
    const meta = !guide && m.status === "ok" && typeof m.seconds === "number" ? `⏱ 응답 ${m.seconds.toFixed(2)}초` : "";
    w.innerHTML = `<div class="a${guide ? " guide" : ""}"><div class="avatar">✦</div><div class="card">${html}</div></div><div class="meta${guide ? " nosave" : ""}">${meta}</div>`;
    if (m.party) partyDetail(w.querySelector(".card"), m.party, 0);
    if (m.status === "pending" && m.steps) animateSteps(w, m.steps);
  }
  out.push(w);
  return out;
}

// 빌드 추천 대기 중 단계 표시 (가짜 모드)
function animateSteps(w, st) {
  const L = w.querySelector(".loading");
  st.forEach((_, i) => setTimeout(() => {
    if (!L.isConnected) return;
    L.innerHTML = st.slice(0, i + 1).map((x, j) => `<span class="${j < i ? "ok" : ""}">${esc(x)}</span>`).join("");
  }, i * 500));
}

/* ----- data -> 화면 ----- */
function update(S, data) {
  const msgs = Array.isArray(data.messages) ? data.messages : [];
  S.msgs = msgs;
  S.localBusy = false;
  S.busy = !!data.busy;
  const ex = JSON.stringify(data.examples || []);
  if (ex !== S.exSig) { S.exSig = ex; S.examples = data.examples || []; S.renderEx(); }

  // 지금 그려진 메시지 중 data에 없는 것이 있으면 처음부터 다시 그림
  const ids = new Set(msgs.map((m) => String(m.id)));
  const stale = [...S.nodes.keys()].some((id) => !ids.has(id));
  if (!msgs.length || stale) {
    S.nodes.clear(); closeSrc(S);
    S.col.innerHTML = msgs.length ? "" : HERO;
    S.started = msgs.length > 0;
  } else if (!S.started) {
    S.col.innerHTML = ""; S.started = true;
  }

  let lastDate = null, changed = false;
  for (const m of msgs) {
    const key = String(m.id), sig = JSON.stringify(m);
    const showDate = !!m.date && m.date !== lastDate;
    if (m.date) lastDate = m.date;
    const old = S.nodes.get(key);
    if (old && old.sig === sig) continue;
    const els = buildNodes(m, showDate);
    if (old) { old.els[0].before(...els); old.els.forEach((e) => e.remove()); }
    else S.col.append(...els);
    S.nodes.set(key, { sig, els });
    changed = true;
  }
  if (S.activeSrc !== null && !ids.has(String(S.activeSrc))) closeSrc(S);
  if (changed) S.scroll.scrollTop = 1e9;

  renderHist(S, msgs);
  S.refresh();
}

/* ----- 사이드바: 이번 대화 기록 (최신이 위) ----- */
function renderHist(S, msgs) {
  const users = msgs.filter((m) => m.role === "user").reverse();
  const h = S.$("hist");
  const note = S.$("histNote");
  h.innerHTML = "";
  if (!users.length) h.insertAdjacentHTML("beforeend", `<div class="empty">아직 기록이 없어요</div>`);
  users.forEach((m) => {
    const a = document.createElement("a");
    a.textContent = m.kind === "build" ? `⚔️ UID ${m.uid} 빌드 추천` : `💬 ${m.text}`;
    a.onclick = () => S.$("q" + m.id)?.scrollIntoView({ behavior: "smooth" });
    h.append(a);
  });
  note.hidden = !users.length;
  h.append(note);
}

export default function (component) {
  const { parentElement, data, setTriggerValue } = component;
  let S = parentElement.__gb;
  if (!S || !S.el.isConnected) S = parentElement.__gb = init(parentElement);
  S.trigger = setTriggerValue;
  update(S, data || {});
}
