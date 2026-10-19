/* Mock EWM UI — ewm-state.json을 읽어 렌더링한다.
   상태 파일은 샘플 warehouse_gadget.py run의 EWM 전송 단계가 갱신한다. */

"use strict";

let STATE = null;

const $ = (sel) => document.querySelector(sel);

function pill(status) {
  if (status === "match") return '<span class="status-pill pill-ok">일치</span>';
  if (status === "shortage") return '<span class="status-pill pill-err">부족</span>';
  if (status === "overage") return '<span class="status-pill pill-warn">초과</span>';
  return '<span class="status-pill pill-neutral">대기</span>';
}

function fmtDiff(d) {
  if (d === 0) return '<span class="mono">0</span>';
  const cls = d < 0 ? "diff-neg" : "diff-pos";
  return '<span class="mono ' + cls + '">' + (d > 0 ? "+" + d : d) + "</span>";
}

function esc(s) {
  return String(s == null ? "" : s)
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

/* ── 뷰 전환 ─────────────────────────── */
const VIEWS = ["home", "count", "detail", "monitor", "diff"];

function currentRoute() {
  const h = location.hash.replace(/^#\//, "") || "home";
  const [name, arg] = h.split("/");
  return { name: VIEWS.includes(name) ? name : "home", arg: arg || "" };
}

function show(view) {
  VIEWS.forEach((v) => {
    const el = $("#view-" + v);
    if (el) el.hidden = v !== view;
  });
  const navName = view === "detail" ? "count" : view;
  document.querySelectorAll("[data-nav]").forEach((a) =>
    a.classList.toggle("active", a.dataset.nav === navName));
}

function route() {
  const { name, arg } = currentRoute();
  if (!STATE) { show("home"); return; }
  if (name === "detail") renderDetail(arg);
  show(name);
  window.scrollTo(0, 0);
}

/* ── 렌더링 ──────────────────────────── */
function renderAll() {
  const s = STATE;
  const wh = s.warehouse;
  const countedBins = s.tasks.length;

  $("#home-sub").textContent =
    "창고번호 " + wh.warehouse_no + " · 최근 전송 " + s.generated_at.replace("T", " ") +
    " · 실사 요약: 지시 " + s.summary.total + "건 중 일치 " + s.summary.match +
    "건, 불일치 " + s.summary.mismatch + "건";
  $("#tile-count-kpi").innerHTML = s.summary.total + ' <small>건 지시</small>';
  $("#tile-count-sub").textContent =
    "전 건 전송 · 확정 완료 — 일치 " + s.summary.match + " · 부족 " + s.summary.shortage +
    " · 초과 " + s.summary.overage;
  $("#tile-monitor-kpi").innerHTML = countedBins + ' <small>/ ' + s.bin_count + ' 빈 실사 완료</small>';
  $("#tile-diff-kpi").innerHTML = s.differences.length + ' <small>건</small>';
  $("#tile-diff-sub").textContent = s.differences.length
    ? s.differences.map((d) => d.bin + " " + (d.diff > 0 ? "+" : "") + d.diff).join(" · ")
    : "차이 없음";

  $("#count-sub").textContent =
    "실사문서 " + (s.tasks[0] ? s.tasks[0].pi_doc : "-") + " · 행을 선택하면 상세를 봅니다";
  const tbody = $("#task-table tbody");
  tbody.innerHTML = s.tasks.map((t) =>
    '<tr class="clickable" data-task="' + t.task_id + '">' +
    '<td class="mono">' + esc(t.wt_no) + "</td>" +
    '<td class="mono">' + esc(t.pi_doc) + "</td>" +
    "<td>" + esc(t.storage_type) + " · " + esc(t.storage_type_name) + "</td>" +
    '<td class="mono">' + esc(t.bin) + "</td>" +
    '<td class="mono">' + esc(t.product_no) + "</td>" +
    "<td>" + esc(t.product_name) + "</td>" +
    '<td class="mono">' + esc(t.hu) + "</td>" +
    '<td class="num">' + t.expected_qty + "</td>" +
    '<td class="num">' + t.counted_qty + "</td>" +
    '<td class="num">' + fmtDiff(t.diff) + "</td>" +
    "<td>" + pill(t.status) + " " + esc(t.ui_status) + "</td>" +
    "</tr>").join("");
  tbody.querySelectorAll("tr.clickable").forEach((tr) =>
    tr.addEventListener("click", () => { location.hash = "#/detail/" + tr.dataset.task; }));

  $("#monitor-sub").textContent =
    "전체 " + s.bin_count + "빈 · 실사 완료 " + countedBins + "빈 · 구역 " +
    s.monitor.zones.length + "개";
  $("#monitor-zones").innerHTML = s.monitor.zones.map((z) =>
    '<h2 class="zone-title">' + esc(z.name) + " (" + esc(z.id) + '구역)</h2>' +
    '<div class="rack-row">' + z.racks.map((r) =>
      '<div class="card rack-card">' +
        '<div class="rack-head"><span class="rack-name">랙 ' + esc(r.id) + "</span>" +
        '<span class="rack-type">' + esc(r.storage_type) + " · " + esc(r.storage_type_name) + "</span></div>" +
        '<div class="progress"><div style="width:' + Math.round(r.progress * 100) + '%"></div></div>' +
        '<div class="bin-grid">' + r.bins.map((b) =>
          '<div class="bin-cell ' + b.count_status + '">' +
            '<div class="bin-code">' + esc(b.bin) + "</div>" +
            '<div class="bin-name">' + esc(b.product_name) + "</div>" +
            '<div class="bin-qty">장부 ' + b.expected_qty +
              (b.counted_qty == null ? " · 미실사" : " · 계수 " + b.counted_qty) + "</div>" +
          "</div>").join("") + "</div>" +
      "</div>").join("") + "</div>").join("");

  $("#diff-sub").textContent = "불일치 " + s.differences.length + "건 — 차이 사유 코드와 조정 상태";
  $("#diff-table tbody").innerHTML = s.differences.map((d) =>
    "<tr>" +
    '<td class="mono">' + esc(d.bin) + "</td>" +
    '<td class="mono">' + esc(d.product_no) + "</td>" +
    "<td>" + esc(d.product_name) + "</td>" +
    '<td class="num">' + d.expected_qty + "</td>" +
    '<td class="num">' + d.counted_qty + "</td>" +
    '<td class="num">' + fmtDiff(d.diff) + "</td>" +
    '<td class="mono">' + esc(d.reason_code) + "</td>" +
    "<td>" + esc(d.reason_name) + "</td>" +
    "<td>" + esc(d.adjustment_status) + "</td>" +
    "<td>" + esc(d.note || "-") + "</td>" +
    "</tr>").join("");

  $("#footer-state").textContent = "상태 기준 시각: " + s.generated_at.replace("T", " ");
}

function renderDetail(taskId) {
  const t = STATE.tasks.find((x) => x.task_id === taskId) || STATE.tasks[0];
  if (!t) return;
  $("#detail-title").textContent = "저장빈 " + t.bin + " · " + t.product_name;
  $("#detail-sub").textContent =
    "창고작업 " + t.wt_no + " · 실사문서 " + t.pi_doc + " · 저장유형 " +
    t.storage_type + " (" + t.storage_type_name + ")";
  const p = $("#detail-pill");
  p.outerHTML = pill(t.status).replace('class="status-pill', 'id="detail-pill" class="status-pill');
  const rows = (pairs) => pairs.map(([k, v]) => "<dt>" + k + "</dt><dd>" + v + "</dd>").join("");
  $("#detail-result").innerHTML = rows([
    ["품목번호", esc(t.product_no) + " (" + esc(t.sku) + ")"],
    ["HU 번호", '<span class="mono">' + esc(t.hu) + "</span>"],
    ["장부수량", t.expected_qty + " 박스"],
    ["계수수량", t.counted_qty + " 박스"],
    ["확정수량", t.final_qty + " 박스"],
    ["처리 방식", esc(t.action)],
  ]);
  $("#detail-diff").innerHTML = rows([
    ["차이", fmtDiff(t.diff) + " 박스"],
    ["사유 코드", t.reason_code ? esc(t.reason_code) + " — " + esc(t.reason_name) : "없음"],
    ["조정 상태", esc(t.adjustment_status)],
    ["메모", esc(t.note || "-")],
  ]);
  $("#detail-transfer").innerHTML = rows([
    ["백엔드", esc(STATE.backend)],
    ["전송 상태", esc(t.ui_status)],
    ["전송 시각", STATE.generated_at.replace("T", " ")],
    ["서비스", '<span class="mono">API_PHYSICAL_INVENTORY_SRV</span>'],
  ]);
}

$("#detail-back").addEventListener("click", () => { location.hash = "#/count"; });
window.addEventListener("hashchange", route);

fetch("ewm-state.json", { cache: "no-store" })
  .then((r) => { if (!r.ok) throw new Error(r.status); return r.json(); })
  .then((data) => { STATE = data; renderAll(); route(); })
  .catch(() => { $("#load-error").hidden = false; show("home"); });
