let radarChart = null;
let selectedFile = null;
let padletCsvCache = "";
let padletConverted = false;

const STORAGE_KEY = "gemini_api_key";
const PADLET_KEY = "padlet_api_key";

const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

function loadApiKey() {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved) $("#apiKeyInput").value = saved;
  const padlet = localStorage.getItem(PADLET_KEY);
  if (padlet) $("#padletApiKey").value = padlet;
  updateStatus();
}

function saveApiKey() {
  const key = $("#apiKeyInput").value.trim();
  if (key) localStorage.setItem(STORAGE_KEY, key);
  else localStorage.removeItem(STORAGE_KEY);
  updateStatus();
}

function savePadletKey() {
  const key = $("#padletApiKey").value.trim();
  if (key) localStorage.setItem(PADLET_KEY, key);
  else localStorage.removeItem(PADLET_KEY);
}

function getApiKey() {
  return $("#apiKeyInput").value.trim();
}

function getPadletKey() {
  return $("#padletApiKey").value.trim();
}

$("#apiKeyInput").addEventListener("input", saveApiKey);
$("#padletApiKey").addEventListener("input", savePadletKey);

$("#toggleKeyBtn").addEventListener("click", () => {
  const input = $("#apiKeyInput");
  input.type = input.type === "password" ? "text" : "password";
});

$("#togglePadletKeyBtn").addEventListener("click", () => {
  const input = $("#padletApiKey");
  input.type = input.type === "password" ? "text" : "password";
});

$("#clearKeyBtn").addEventListener("click", () => {
  $("#apiKeyInput").value = "";
  localStorage.removeItem(STORAGE_KEY);
  updateStatus();
});

$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => t.classList.remove("active"));
    $$(".tab-panel").forEach((p) => p.classList.remove("active"));
    tab.classList.add("active");
    $(`#panel-${tab.dataset.tab}`).classList.add("active");
  });
});

function updateStatus() {
  const badge = $("#statusBadge");
  const text = $("#statusText");
  const hasKey = !!getApiKey();
  const useLlm = $("#useLlm").checked;

  if (hasKey && useLlm) {
    text.textContent = "Gemini 분석 준비됨";
    badge.classList.remove("offline");
  } else if (useLlm) {
    text.textContent = "키워드 분석 모드";
    badge.classList.remove("offline");
  } else {
    text.textContent = "키워드 분석만";
    badge.classList.remove("offline");
  }
}

$("#useLlm").addEventListener("change", updateStatus);

async function checkHealth() {
  try {
    const res = await fetch("/api/health");
    if (!res.ok) throw new Error("health check failed");
    updateStatus();
  } catch {
    $("#statusText").textContent = "서버 연결 실패";
    $("#statusBadge").classList.add("offline");
  }
}

const dropzone = $("#dropzone");
const fileInput = $("#fileInput");

$("#browseBtn").addEventListener("click", (e) => {
  e.stopPropagation();
  fileInput.click();
});

dropzone.addEventListener("click", () => fileInput.click());

dropzone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropzone.classList.add("dragover");
});

dropzone.addEventListener("dragleave", () => dropzone.classList.remove("dragover"));

dropzone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropzone.classList.remove("dragover");
  if (e.dataTransfer.files.length) setFile(e.dataTransfer.files[0]);
});

fileInput.addEventListener("change", () => {
  if (fileInput.files.length) setFile(fileInput.files[0]);
});

function setFile(file) {
  selectedFile = file;
  dropzone.querySelector("p").innerHTML =
    `선택됨: <strong>${file.name}</strong> — <button type="button" class="link-btn" id="changeFile">변경</button>`;
  $("#analyzeBtn").disabled = false;
  $("#changeFile")?.addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });
}

function showError(msg) {
  const el = $("#errorBanner");
  el.textContent = msg;
  el.classList.remove("hidden");
}

function hideError() {
  $("#errorBanner").classList.add("hidden");
}

function showLoading(show, message) {
  $("#loading").classList.toggle("hidden", !show);
  if (message) $("#loading p").textContent = message;
  else $("#loading p").textContent = "감상평을 분석하고 있어요…";
}

function rankList(obj) {
  return Object.entries(obj)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1]);
}

function methodLabel(method) {
  if (method === "gemini") return "Gemini + 키워드 분석";
  if (method === "llm") return "LLM + 키워드 분석";
  return "키워드 분석";
}

function appendAnalysisOptions(form) {
  form.append("use_llm", $("#useLlm").checked);
  form.append("gemini_api_key", getApiKey());
}

function showPadletPreview(data) {
  padletCsvCache = data.csv || "";
  padletConverted = true;
  $("#analyzePadletBtn").disabled = false;
  const box = $("#padletPreview");
  box.classList.remove("hidden");
  $("#padletPreviewTitle").textContent = data.title || "변환 완료";
  const src = data.source === "demo" ? "데모 샘플" : "Padlet API";
  $("#padletPreviewMeta").textContent = `${src} · ${data.total_posts}개 게시글 · id ${data.board_id}`;
  $("#padletPreviewList").innerHTML = (data.preview || [])
    .map((t) => `<li>${t}</li>`)
    .join("") || "<li>미리보기 없음</li>";
}

$("#downloadPadletCsv").addEventListener("click", () => {
  if (!padletCsvCache) return;
  const blob = new Blob([padletCsvCache], { type: "text/csv;charset=utf-8" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "padlet_converted.csv";
  a.click();
  URL.revokeObjectURL(a.href);
});

async function convertPadlet(useDemo) {
  hideError();
  showLoading(true, useDemo ? "데모 CSV를 준비하고 있어요…" : "패들렛을 CSV로 변환 중…");

  const form = new FormData();
  form.append("url", useDemo ? "demo" : $("#padletUrl").value.trim() || "demo");
  form.append("padlet_api_key", getPadletKey());
  form.append("use_demo", useDemo ? "true" : "false");

  try {
    const res = await fetch("/api/padlet/convert", { method: "POST", body: form });
    const data = await res.json();
    if (!data.ok) {
      showError(data.error || "변환에 실패했습니다.");
      $("#analyzePadletBtn").disabled = true;
      $("#padletPreview").classList.add("hidden");
      return;
    }
    showPadletPreview(data);
  } catch (e) {
    showError("변환 중 오류: " + e.message);
  } finally {
    showLoading(false);
  }
}

async function analyzePadlet() {
  hideError();
  showLoading(true, "패들렛 → CSV → 분석 진행 중…");

  const useDemo =
    padletConverted &&
    (!$("#padletUrl").value.trim() ||
      $("#padletPreviewMeta").textContent.includes("데모"));

  const form = new FormData();
  const url = $("#padletUrl").value.trim();
  form.append("url", useDemo && !getPadletKey() ? "demo" : url || "demo");
  form.append("padlet_api_key", getPadletKey());
  form.append(
    "use_demo",
    (!url && !getPadletKey()) || $("#padletPreviewMeta").textContent.includes("데모")
      ? "true"
      : "false"
  );
  appendAnalysisOptions(form);

  try {
    const res = await fetch("/api/analyze-padlet", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      showError(data.error);
      return;
    }
    if (data.csv) padletCsvCache = data.csv;
    renderDashboard(data);
  } catch (e) {
    showError("분석 중 오류: " + e.message);
  } finally {
    showLoading(false);
  }
}

$("#convertPadletBtn").addEventListener("click", () => {
  const url = $("#padletUrl").value.trim();
  if (!url && !getPadletKey()) {
    showError("패들렛 URL을 입력하거나 '데모 샘플로 체험'을 눌러 주세요.");
    return;
  }
  convertPadlet(false);
});

$("#demoPadletBtn").addEventListener("click", () => convertPadlet(true));
$("#analyzePadletBtn").addEventListener("click", analyzePadlet);

function renderDashboard(data) {
  hideError();
  $("#uploadSection").classList.add("hidden");
  $("#dashboard").classList.remove("hidden");

  const summary = data.summary || {};
  $("#insightText").textContent =
    summary.insight ||
    `우리 반은 이 곡의 '${summary.top_musical || "—"}'과 '${summary.top_emotion || "—"}'에 가장 집중했어요!`;

  let countLabel = `총 ${data.total_reviews}개 감상평`;
  if (data.padlet_title) countLabel += ` · ${data.padlet_title}`;
  $("#reviewCount").textContent = countLabel;

  let method = methodLabel(data.method);
  if (data.padlet_source) {
    method += data.padlet_source === "demo" ? " · Padlet 데모" : " · Padlet 링크";
  }
  $("#analysisMethod").textContent = method;

  const radar = data.radar;
  if (radarChart) radarChart.destroy();
  const ctx = $("#radarChart").getContext("2d");
  radarChart = new Chart(ctx, {
    type: "radar",
    data: {
      labels: radar.labels,
      datasets: [
        {
          label: "감정 빈도",
          data: radar.normalized,
          backgroundColor: "rgba(127, 90, 240, 0.25)",
          borderColor: "rgba(255, 137, 6, 0.9)",
          borderWidth: 2,
          pointBackgroundColor: "#ff8906",
          pointBorderColor: "#fff",
          pointRadius: 4,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        r: {
          beginAtZero: true,
          max: 100,
          ticks: { display: false },
          grid: { color: "rgba(255,255,255,0.08)" },
          angleLines: { color: "rgba(255,255,255,0.08)" },
          pointLabels: {
            color: "#a7a9be",
            font: { family: "Noto Sans KR", size: 11 },
          },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => {
              const raw = radar.values[ctx.dataIndex];
              return ` ${raw}회 언급 (${ctx.raw}%)`;
            },
          },
        },
      },
    },
  });

  $("#emotionLegend").innerHTML = rankList(data.emotions)
    .map(([k, v]) => `<span class="legend-item">${k} ${v}</span>`)
    .join("");

  const wcEl = $("#wordcloud");
  wcEl.innerHTML = "";
  const words = data.wordcloud || [];
  if (words.length) {
    WordCloud(wcEl, {
      list: words.map((w) => [w.text, w.size]),
      gridSize: 8,
      weightFactor: 1.2,
      fontFamily: "Noto Sans KR, sans-serif",
      color: () => {
        const colors = ["#ff8906", "#e53170", "#7f5af0", "#2cb67d", "#fffffe"];
        return colors[Math.floor(Math.random() * colors.length)];
      },
      rotateRatio: 0.3,
      rotationSteps: 2,
      backgroundColor: "transparent",
      shrinkToFit: true,
    });
  } else {
    wcEl.innerHTML = '<p style="color:#a7a9be">음악 요소 키워드가 없습니다</p>';
  }

  $("#emotionRank").innerHTML =
    rankList(data.emotions)
      .map(([k, v], i) => `<li><span>${i + 1}. ${k}</span><span class="count">${v}</span></li>`)
      .join("") || "<li>데이터 없음</li>";

  $("#musicalRank").innerHTML =
    rankList(data.musical_elements)
      .map(([k, v], i) => `<li><span>${i + 1}. ${k}</span><span class="count">${v}</span></li>`)
      .join("") || "<li>데이터 없음</li>";

  $("#sampleReviews").innerHTML =
    (data.sample_reviews || []).map((t) => `<li>${t}</li>`).join("") || "<li>—</li>";
}

async function analyzeCsv() {
  if (!selectedFile) return;
  hideError();
  showLoading(true);
  const form = new FormData();
  form.append("file", selectedFile);
  appendAnalysisOptions(form);
  try {
    const res = await fetch("/api/analyze", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      showError(data.error);
      return;
    }
    renderDashboard(data);
  } catch (e) {
    showError("분석 중 오류가 발생했습니다: " + e.message);
  } finally {
    showLoading(false);
  }
}

async function analyzeText() {
  const text = $("#textInput").value.trim();
  if (!text) {
    showError("감상평을 입력해 주세요.");
    return;
  }
  hideError();
  showLoading(true);
  const form = new FormData();
  form.append("texts", text);
  appendAnalysisOptions(form);
  try {
    const res = await fetch("/api/analyze-text", { method: "POST", body: form });
    const data = await res.json();
    if (data.error) {
      showError(data.error);
      return;
    }
    renderDashboard(data);
  } catch (e) {
    showError("분석 중 오류가 발생했습니다: " + e.message);
  } finally {
    showLoading(false);
  }
}

$("#analyzeBtn").addEventListener("click", analyzeCsv);
$("#analyzeTextBtn").addEventListener("click", analyzeText);

$("#resetBtn").addEventListener("click", () => {
  $("#dashboard").classList.add("hidden");
  $("#uploadSection").classList.remove("hidden");
  selectedFile = null;
  fileInput.value = "";
  $("#analyzeBtn").disabled = true;
  padletConverted = false;
  $("#analyzePadletBtn").disabled = true;
  $("#padletPreview").classList.add("hidden");
  dropzone.querySelector(".dropzone-content").innerHTML = `
    <span class="dropzone-icon">📂</span>
    <p>CSV 파일을 여기에 끌어다 놓거나 <button type="button" class="link-btn" id="browseBtn">파일 선택</button></p>
    <p class="hint">Google Forms · Padlet Export(Body/Subject) CSV 자동 인식</p>
  `;
  $("#browseBtn").addEventListener("click", (e) => {
    e.stopPropagation();
    fileInput.click();
  });
});

loadApiKey();
checkHealth();
