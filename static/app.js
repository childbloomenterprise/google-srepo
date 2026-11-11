const app = document.getElementById("app");
let language = localStorage.getItem("claimback-language") || "en";
let currentCase = null;
let mediaRecorder = null;
let audioChunks = [];
let noteText = "";
let busy = false;
let rulesText = "";

const copy = {
  en: {
    headline: "Insurer cut your claim? Get it back.",
    subhead: "We check every cut against IRDAI rules. You choose what to do next.",
    upload: "Upload rejection / settlement letter",
    uploadHint: "Add your policy and hospital papers too",
    voice: "Tell us in Hindi or English",
    demos: "Try a demo case",
    partial: "Wrong deductions",
    ped: "Pre-existing disease rejection",
    analyzing: "Checking your claim",
    step1: "Reading documents",
    step2: "Checking 15 IRDAI rules",
    step3: "Calculating your money",
    analyze: "Checking every cut against the rulebook…",
    appeals: "Generate my appeal",
    generating: "Writing your drafts…",
    letters: "Your appeal drafts",
    grievance: "Insurer grievance",
    ombudsman: "Ombudsman complaint",
    copy: "Copy",
    download: "Download .txt",
    sent: "Mark as sent",
    timeline: "Your next steps",
    interest: "Your reimbursement was decided late. You may also be owed interest under R07.",
    eligible: "You may take an unresolved claim up to ₹50 lakh to the Insurance Ombudsman.",
    disclaimer: "ClaimBack prepares drafts you send in your own name. Not legal advice.",
    home: "Start another claim",
    back: "Back to result",
    error: "Something went wrong. Please try again.",
    record: "Tap to record",
    stop: "Stop recording",
    transcript: "Transcript added to your notes",
    dashboard: "Dashboard",
  },
  hi: {
    headline: "बीमा कंपनी ने क्लेम काटा? वापस पाएं।",
    subhead: "हम हर कटौती को IRDAI नियमों से जांचते हैं। आगे क्या करना है, आप चुनें।",
    upload: "अस्वीकृति / सेटलमेंट पत्र अपलोड करें",
    uploadHint: "पॉलिसी और अस्पताल के कागज़ भी जोड़ें",
    voice: "हिंदी या अंग्रेज़ी में बताएं",
    demos: "डेमो केस देखें",
    partial: "गलत कटौती",
    ped: "पहले से बीमारी बताकर अस्वीकृति",
    analyzing: "आपका क्लेम जांच रहे हैं",
    step1: "दस्तावेज़ पढ़ रहे हैं",
    step2: "15 IRDAI नियम जांच रहे हैं",
    step3: "आपकी राशि जोड़ रहे हैं",
    analyze: "नियमों के अनुसार हर कटौती जांच रहे हैं…",
    appeals: "मेरी अपील तैयार करें",
    generating: "आपके ड्राफ्ट तैयार हो रहे हैं…",
    letters: "आपके अपील ड्राफ्ट",
    grievance: "बीमा कंपनी को शिकायत",
    ombudsman: "ओम्बड्समैन शिकायत",
    copy: "कॉपी",
    download: ".txt डाउनलोड",
    sent: "भेज दिया — दर्ज करें",
    timeline: "आपके अगले कदम",
    interest: "आपका रीइम्बर्समेंट देर से तय हुआ। R07 के तहत ब्याज भी मिल सकता है।",
    eligible: "अनसुलझे ₹50 लाख तक के क्लेम को इंश्योरेंस ओम्बड्समैन तक ले जा सकते हैं।",
    disclaimer: "ClaimBack आपके नाम से भेजने के लिए ड्राफ्ट बनाता है। यह कानूनी सलाह नहीं है।",
    home: "नया क्लेम शुरू करें",
    back: "नतीजे पर लौटें",
    error: "कुछ गड़बड़ हुई। कृपया फिर कोशिश करें।",
    record: "रिकॉर्ड करने के लिए दबाएं",
    stop: "रिकॉर्डिंग रोकें",
    transcript: "ट्रांसक्रिप्ट नोट्स में जुड़ गया",
    dashboard: "डैशबोर्ड",
  },
};
const t = (key) => copy[language][key] || copy.en[key] || key;
const safe = (value) => String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const money = (value) => `₹${Math.round(Number(value || 0)).toLocaleString("en-IN")}`;
const modelName = (model) => `Gemini ${String(model || "").replace(/^gemini-/i, "").split("-").map((part) => part[0]?.toUpperCase() + part.slice(1)).join(" ")}`;
const savedResultBanner = (caseData) => caseData.cached
  ? `<div class="mb-4 rounded-2xl border border-amber-200 bg-amber-50 p-3 text-xs leading-5 text-amber-900">Live Gemini busy — showing the saved result of a live Gemini run from ${safe(new Date(caseData.cached_at).toLocaleDateString())}</div>`
  : "";
const sourceFor = (id) => {
  const line = rulesText.split("\n").find((item) => item.startsWith(`${id} `));
  return line ? line.split("|").slice(3, 4).join("|").trim() : "Curated IRDAI rulebook";
};

function shell(content) {
  return `<main class="mx-auto min-h-screen max-w-xl px-5 pb-8 pt-5 sm:px-7">
    <header class="mb-8 flex items-center justify-between">
      <button class="brand flex items-center gap-2 text-lg font-extrabold tracking-tight" onclick="showHome()">
        <span class="grid h-9 w-9 place-items-center rounded-xl bg-emerald-900 text-sm font-bold text-white">CB</span>
        <span>ClaimBack</span>
      </button>
      <div class="flex items-center gap-3">
        <a href="/dashboard" class="text-xs font-semibold text-slate-500">${t("dashboard")}</a>
        <button class="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold" onclick="toggleLanguage()">${language === "en" ? "EN / हिं" : "हिं / EN"}</button>
      </div>
    </header>${content}
    <footer class="safe-bottom mt-10 text-center text-xs leading-5 text-slate-400">${t("disclaimer")}</footer>
  </main>`;
}

async function loadRules() {
  try { rulesText = (await (await fetch("/api/rules")).json()).rulebook || ""; } catch (_) { rulesText = ""; }
}

function showHome() {
  currentCase = null;
  app.innerHTML = shell(`<section class="pt-5">
    <div class="mb-5 inline-flex items-center gap-2 rounded-full bg-emerald-50 px-3 py-1.5 text-xs font-bold text-emerald-800">
      <span class="step-dot"></span> Built for Indian health-insurance claims
    </div>
    <h1 class="max-w-md text-[2.45rem] font-extrabold leading-[1.08] tracking-tight">${t("headline")}</h1>
    <p class="mt-4 max-w-sm text-base leading-7 text-slate-500">${t("subhead")}</p>
    <section class="soft-shadow mt-8 rounded-[28px] border border-emerald-100 bg-white p-5">
      <input id="file-input" type="file" accept="image/jpeg,image/png,application/pdf" multiple capture="environment" class="hidden">
      <button onclick="document.getElementById('file-input').click()" class="flex min-h-[72px] w-full items-center justify-center gap-3 rounded-2xl bg-emerald-900 px-4 py-4 text-center text-base font-bold text-white shadow-sm active:scale-[.99]">
        <span class="text-xl">＋</span><span>${t("upload")}</span>
      </button>
      <p class="mt-3 text-center text-xs text-slate-400">${t("uploadHint")} · JPG, PNG or PDF</p>
      <div id="selected-files" class="mt-2 text-center text-xs text-slate-600"></div>
      <div class="my-5 flex items-center gap-3"><span class="h-px flex-1 bg-slate-100"></span><span class="text-xs text-slate-400">or</span><span class="h-px flex-1 bg-slate-100"></span></div>
      <button id="voice-button" onclick="toggleRecording()" class="flex w-full items-center justify-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 py-3.5 text-sm font-bold text-emerald-900">
        <span>🎙</span><span>${t("voice")}</span>
      </button>
      <p id="voice-status" class="mt-2 hidden text-center text-xs text-emerald-800"></p>
    </section>
    <div id="home-error" class="mt-3 hidden rounded-xl bg-rose-50 p-3 text-sm text-rose-700"></div>
    <section class="mt-9">
      <p class="mb-3 text-xs font-bold uppercase tracking-[.15em] text-slate-400">${t("demos")}</p>
      <div class="grid grid-cols-2 gap-3">
        <button onclick="runDemo('partial-cut')" class="rounded-2xl border border-slate-200 bg-white p-4 text-left">
          <span class="mb-3 grid h-9 w-9 place-items-center rounded-xl bg-amber-50 text-lg">↘</span>
          <span class="block text-sm font-bold">${t("partial")}</span><span class="mt-1 block text-xs text-slate-400">₹55,500 cut · demo</span>
        </button>
        <button onclick="runDemo('ped-rejection')" class="rounded-2xl border border-slate-200 bg-white p-4 text-left">
          <span class="mb-3 grid h-9 w-9 place-items-center rounded-xl bg-violet-50 text-lg">✳</span>
          <span class="block text-sm font-bold">${t("ped")}</span><span class="mt-1 block text-xs text-slate-400">₹3,40,000 · demo</span>
        </button>
      </div>
    </section>
  </section>`);
  document.getElementById("file-input").addEventListener("change", onFilesSelected);
}

function showProgress() {
  app.innerHTML = shell(`<section class="pt-16 text-center">
    <div class="mx-auto grid h-16 w-16 place-items-center rounded-3xl bg-emerald-100"><div class="loader"></div></div>
    <h1 class="mt-6 text-2xl font-extrabold">${t("analyzing")}</h1>
    <p class="mt-2 text-sm text-slate-500">${t("analyze")}</p>
    <div class="mx-auto mt-9 max-w-xs space-y-4 text-left">
      ${[t("step1"), t("step2"), t("step3")].map((step) => `<div class="flex items-center gap-3 rounded-xl bg-white p-3 text-sm font-semibold"><span class="step-dot"></span>${safe(step)}</div>`).join("")}
    </div>
  </section>`);
}

function showCase(caseData, view = "result") {
  currentCase = caseData;
  if (view === "letters") return showLetters(caseData);
  const amount = caseData.recoverable_amount || 0;
  const strengthStyle = { STRONG: "bg-emerald-100 text-emerald-900", MEDIUM: "bg-amber-100 text-amber-900", WEAK: "bg-rose-100 text-rose-900" }[caseData.case_strength] || "bg-slate-100 text-slate-800";
  const why = language === "hi" ? "why_simple_hi" : "why_simple_en";
  const refusals = (caseData.refusals || []).map((cut) => `<article class="border-b border-slate-100 py-4 last:border-0">
    <div class="flex items-start justify-between gap-3">
      <div><h3 class="text-sm font-bold leading-5">${safe(cut.item)}</h3><p class="mt-1 text-xs text-slate-400">${safe(cut.insurer_reason)}</p></div>
      <div class="shrink-0 text-sm font-extrabold">${money(cut.amount)}</div>
    </div>
    <div class="mt-3 flex flex-wrap items-center gap-2">
      <span class="rounded-full px-2.5 py-1 text-[10px] font-extrabold ${cut.verdict === "WRONGFUL" ? "bg-emerald-100 text-emerald-900" : cut.verdict === "QUESTIONABLE" ? "bg-amber-100 text-amber-900" : "bg-slate-100 text-slate-600"}">${safe(cut.verdict)}</span>
      ${(cut.rule_ids || []).map((id) => `<details class="text-xs"><summary class="cursor-pointer rounded-full border border-slate-200 px-2.5 py-1 font-bold text-slate-600">${safe(id)} · source</summary><p class="mt-2 max-w-xs rounded-lg bg-slate-50 p-2 text-[11px] leading-4 text-slate-500">${safe(sourceFor(id))}</p></details>`).join("")}
    </div>
    <p class="mt-3 text-sm leading-5 text-slate-600">${safe(cut[why])}</p>
    <details class="mt-2 text-xs text-slate-400"><summary class="cursor-pointer font-semibold">Evidence from your document</summary><blockquote class="mt-2 border-l-2 border-emerald-300 pl-3 text-slate-500">“${safe(cut.evidence_quote)}”</blockquote></details>
  </article>`).join("");
  const timeline = [...(caseData.timeline || []), ...(caseData.tracker_events || [])];
  app.innerHTML = shell(`<section class="pt-1">
    <button class="mb-4 text-xs font-bold text-emerald-800" onclick="showHome()">← ${t("home")}</button>
    ${savedResultBanner(caseData)}
    <div class="soft-shadow rounded-[28px] bg-emerald-950 p-6 text-white">
      <div class="flex items-center justify-between gap-2"><span class="rounded-full px-3 py-1 text-[11px] font-extrabold ${strengthStyle}">${safe(caseData.case_strength)} CASE</span><span class="text-xs text-emerald-100/70">${caseData.model_used ? `Analysed by ${safe(modelName(caseData.model_used))}` : "ClaimBack review"}</span></div>
      <div class="mt-7 text-4xl font-extrabold tracking-tight">${money(amount)}</div>
      <p class="mt-2 text-sm leading-6 text-emerald-50">${safe(language === "hi" ? caseData.headline_hi : caseData.headline_en)}</p>
      <div class="mt-5 flex justify-between border-t border-white/15 pt-4 text-xs text-emerald-100/80"><span>Claim refused</span><strong class="text-white">${money(caseData.refused_total)}</strong></div>
    </div>
    ${caseData.interest_due ? `<div class="mt-4 rounded-2xl border border-blue-100 bg-blue-50 p-4 text-sm leading-5 text-blue-900"><strong>Interest may be due · R07</strong><p class="mt-1">${t("interest")} (${safe(caseData.interest_days_late)} days beyond 15 days)</p></div>` : ""}
    ${caseData.ombudsman_eligible ? `<div class="mt-3 rounded-2xl border border-violet-100 bg-violet-50 p-4 text-sm leading-5 text-violet-900">${t("eligible")} <span class="font-bold">R14</span></div>` : ""}
    <section class="mt-7 rounded-[24px] border border-slate-100 bg-white px-4 py-1">
      <div class="flex items-center justify-between py-4"><h2 class="text-lg font-extrabold">Every cut</h2><span class="text-xs text-slate-400">${(caseData.refusals || []).length} items</span></div>
      ${refusals || `<p class="pb-4 text-sm text-slate-500">No individual deduction was identified. Check the missing details below.</p>`}
    </section>
    ${(caseData.missing_info || []).length ? `<p class="mt-3 rounded-2xl bg-amber-50 p-4 text-sm text-amber-900">Still needed: ${caseData.missing_info.map(safe).join(", ")}</p>` : ""}
    <button onclick="generateLetters()" class="mt-5 w-full rounded-2xl bg-emerald-900 py-4 text-base font-extrabold text-white">${t("appeals")} <span aria-hidden="true">→</span></button>
    ${caseData.ombudsman_reply_deadline ? `<div class="mt-3 rounded-2xl border border-violet-100 bg-violet-50 p-4 text-sm text-violet-900">File with the Ombudsman within one year of the insurer's reply · deadline ${safe(caseData.ombudsman_reply_deadline)}</div>` : ""}
    <section class="mt-7 rounded-[24px] border border-slate-100 bg-white p-5">
      <h2 class="text-lg font-extrabold">${t("timeline")}</h2>
      <div class="mt-4 space-y-4">${timeline.map((event) => `<div class="flex items-center gap-3 text-sm"><span class="step-dot"></span><span class="flex-1 capitalize">${safe(event.label || event.event.replaceAll("_", " "))}</span><span class="text-xs text-slate-400">${safe(event.date)}</span></div>`).join("")}</div>
      <div class="mt-5 grid grid-cols-2 gap-2">${statusButtons()}</div>
    </section>
  </section>`);
}

function statusButtons() {
  return [["grievance_sent", "Grievance sent"], ["insurer_replied", "Insurer replied"], ["ombudsman_filed", "Ombudsman filed"], ["paid", "Paid"]].map(([event, label]) => `<button onclick="markStatus('${event}')" class="rounded-xl border border-slate-200 px-2 py-2 text-[11px] font-bold text-slate-600">${label}</button>`).join("");
}

function showLetters(caseData) {
  const letters = caseData.letters || {};
  const lettersModel = letters.model_used || caseData.letters_model_used;
  const panel = (key, title, icon) => `<section class="mt-5 rounded-[24px] border border-slate-100 bg-white p-4">
    <div class="flex items-center gap-2"><span>${icon}</span><h2 class="font-extrabold">${title}</h2></div>
    <textarea id="${key}" readonly class="mt-3 h-64 w-full resize-y rounded-xl border border-slate-100 bg-slate-50 p-3 text-xs leading-5 text-slate-700">${safe(letters[key] || "")}</textarea>
    <div class="mt-3 grid grid-cols-2 gap-2">
      <button onclick="copyLetter('${key}')" class="rounded-xl border border-slate-200 py-2.5 text-xs font-bold">${t("copy")}</button>
      <button onclick="downloadLetter('${key}')" class="rounded-xl border border-slate-200 py-2.5 text-xs font-bold">${t("download")}</button>
    </div>
    <a href="mailto:?subject=${encodeURIComponent(title)}" class="mt-2 block rounded-xl bg-emerald-50 py-2.5 text-center text-xs font-bold text-emerald-900">Open email draft</a>
  </section>`;
  app.innerHTML = shell(`<section class="pt-1">
    <button class="mb-4 text-xs font-bold text-emerald-800" onclick="showCase(currentCase, 'result')">← ${t("back")}</button>
    ${savedResultBanner(caseData)}
    <p class="text-xs font-bold uppercase tracking-[.15em] text-emerald-700">Ready to send</p>
    <h1 class="mt-2 text-3xl font-extrabold">${t("letters")}</h1>
    ${lettersModel ? `<p class="mt-2 text-xs text-slate-400">Generated by ${safe(modelName(lettersModel))}</p>` : ""}
    ${panel("grievance_letter", t("grievance"), "✉")}
    ${panel("ombudsman_complaint", t("ombudsman"), "⚖")}
    <button onclick="markStatus('grievance_sent')" class="mt-4 w-full rounded-2xl bg-emerald-900 py-4 text-base font-extrabold text-white">${t("sent")}</button>
  </section>`);
}

async function onFilesSelected(event) {
  const files = [...event.target.files];
  if (!files.length) return;
  if (files.length > 8 || files.reduce((sum, file) => sum + file.size, 0) > 20 * 1024 * 1024) {
    showHomeError("Choose up to 8 files (20 MB total).");
    return;
  }
  const display = document.getElementById("selected-files");
  display.textContent = files.map((file) => file.name).join(", ");
  const body = new FormData();
  files.forEach((file) => body.append("files[]", file));
  body.append("notes", noteText);
  body.append("lang", language);
  showProgress();
  try {
    const response = await fetch("/api/cases", { method: "POST", body });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || t("error"));
    showCase(data);
  } catch (error) { showHomeError(error.message); }
}

async function runDemo(id) {
  showProgress();
  try {
    const response = await fetch(`/api/demo/${id}?lang=${language}`, { method: "POST" });
    const data = await response.json();
    if (!response.ok) throw new Error(data.detail || t("error"));
    showCase(data);
  } catch (error) { showHomeError(error.message); }
}

async function generateLetters() {
  if (!currentCase) return;
  app.innerHTML = shell(`<section class="pt-20 text-center"><div class="mx-auto grid h-16 w-16 place-items-center rounded-3xl bg-emerald-100"><div class="loader"></div></div><p class="mt-5 font-bold">${t("generating")}</p></section>`);
  try {
    const response = await fetch(`/api/cases/${currentCase.id}/letters`, { method: "POST" });
    const letters = await response.json();
    if (!response.ok) throw new Error(letters.detail || t("error"));
    currentCase.letters = letters;
    showLetters(currentCase);
  } catch (error) { alert(error.message); showCase(currentCase); }
}

async function markStatus(event) {
  if (!currentCase) return;
  try {
    const response = await fetch(`/api/cases/${currentCase.id}/status`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ event }),
    });
    currentCase = await response.json();
    if (!response.ok) throw new Error(currentCase.detail || t("error"));
    showCase(currentCase, currentCase.letters ? "letters" : "result");
  } catch (error) { alert(error.message); }
}

async function copyLetter(id) {
  await navigator.clipboard.writeText(document.getElementById(id).value);
}
function downloadLetter(id) {
  const blob = new Blob([document.getElementById(id).value], { type: "text/plain;charset=utf-8" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob); link.download = `${id}.txt`; link.click(); URL.revokeObjectURL(link.href);
}
function toggleLanguage() {
  language = language === "en" ? "hi" : "en";
  localStorage.setItem("claimback-language", language);
  if (currentCase) showCase(currentCase); else showHome();
}
function showHomeError(message) {
  showHome();
  const node = document.getElementById("home-error");
  node.textContent = message || t("error");
  node.classList.remove("hidden");
}

async function toggleRecording() {
  const status = document.getElementById("voice-status");
  const button = document.getElementById("voice-button");
  if (mediaRecorder?.state === "recording") { mediaRecorder.stop(); button.lastElementChild.textContent = t("voice"); return; }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(stream);
    audioChunks = [];
    mediaRecorder.ondataavailable = (event) => audioChunks.push(event.data);
    mediaRecorder.onstop = async () => {
      const blob = new Blob(audioChunks, { type: mediaRecorder.mimeType || "audio/webm" });
      stream.getTracks().forEach((track) => track.stop());
      status.textContent = "Transcribing…"; status.classList.remove("hidden");
      try {
        const response = await fetch("/api/voice", { method: "POST", headers: { "Content-Type": blob.type }, body: blob });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || t("error"));
        noteText = [noteText, result.transcript].filter(Boolean).join("\n");
        status.textContent = `${t("transcript")}: ${result.transcript}`;
      } catch (error) { status.textContent = error.message; }
    };
    mediaRecorder.start();
    button.lastElementChild.textContent = t("stop");
    status.textContent = t("record"); status.classList.remove("hidden");
  } catch (_) { status.textContent = "Microphone permission is needed."; status.classList.remove("hidden"); }
}

async function showDashboard() {
  try {
    const data = await (await fetch("/api/dashboard")).json();
    app.innerHTML = shell(`<section class="pt-2">
      <p class="text-xs font-bold uppercase tracking-[.15em] text-emerald-700">BigQuery export in production</p>
      <h1 class="mt-2 text-3xl font-extrabold">ClaimBack dashboard</h1>
      <div class="mt-6 grid grid-cols-2 gap-3">
        ${[["Cases analysed", data.cases_analysed], ["₹ refused", money(data.amount_refused)], ["₹ recoverable flagged", money(data.amount_recoverable_flagged)]].map(([label, value]) => `<div class="rounded-2xl border border-slate-100 bg-white p-4"><p class="text-xs text-slate-500">${label}</p><p class="mt-2 text-xl font-extrabold">${value}</p></div>`).join("")}
      </div>
      <section class="mt-5 rounded-2xl border border-slate-100 bg-white p-5"><h2 class="font-extrabold">Most-cited rules</h2><div class="mt-3 space-y-3">${(data.most_cited_rules || []).map((item) => `<div class="flex justify-between text-sm"><strong>${safe(item.rule_id)}</strong><span>${item.count} citations</span></div>`).join("") || '<p class="text-sm text-slate-400">No claims analysed yet.</p>'}</div></section>
      <button onclick="showHome()" class="mt-6 w-full rounded-xl bg-emerald-900 py-3 font-bold text-white">${t("home")}</button>
    </section>`);
  } catch (_) { showHome(); }
}

loadRules().then(() => { if (location.pathname === "/dashboard") showDashboard(); else showHome(); });
