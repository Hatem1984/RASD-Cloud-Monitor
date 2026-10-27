"use strict";
/* MA'AL V0.3 — brand book decision workspace, read-only local preview. */
const VIEWS = Object.freeze({
  overview: ["ملخص اليوم", "ماذا حدث؟ وما القرار التالي؟", "ملخص ملموس لنشاط رقمي افتراضي، بأدلة وحدود واضحة."],
  monitor: ["الإشارات المهمة", "الأخبار التي تهم نشاطك.", "نتائج محدودة بالمصادر المتاحة وتواريخها، وليست رصدًا حيًا شاملًا."],
  report: ["التقرير الكامل", "حقائق قبل القرارات.", "تقرير استخبارات أعمال عربي وتوصيات مشروطة قابلة للمراجعة."],
  evidence: ["غرفة الأدلة", "كل استنتاج يبدأ بدليل.", "مصدر أصلي وصورة موثقة وبصمة قابلة للمراجعة."],
  impact: ["تحليل الأثر", "لماذا يهم هذا التغيير؟", "نُميّز بين حقيقة منشورة وفرصة محتملة ومعلومات لم تثبت."],
  decisions: ["القرارات والمتابعة", "اختر ما يستحق المتابعة.", "هذه توصيات وليست مهام منفذة أو موافقات إنتاجية."],
  operations: ["التشغيل والأمان", "الشفافية جزء من المنتج.", "قدرات مثبتة وحدود تشغيل صريحة، بلا ادعاءات إنتاجية."]
});
const state = { snapshot: null, caseData: null, currentView: "overview", expandedSources: false };
const $ = id => document.getElementById(id);
const selectors = document.querySelectorAll(".nav-link");
let toastTimeout = null;

function navigate(view, updateHistory=true) {
  if (!Object.hasOwn(VIEWS, view)) view = "overview";
  state.currentView = view;
  document.querySelectorAll(".view").forEach(section =>
    section.classList.toggle("hidden", section.id !== "view-" + view));
  selectors.forEach(button => {
    const selected = button.dataset.view === view;
    button.classList.toggle("active", selected);
    if (selected) button.setAttribute("aria-current", "page");
    else button.removeAttribute("aria-current");
  });
  $("current-view-label").textContent = VIEWS[view][0];
  $("current-heading").textContent = VIEWS[view][1];
  $("current-subheading").textContent = VIEWS[view][2];
  document.title = "مَآل | " + VIEWS[view][0];
  if (updateHistory) history.replaceState(null, "", "#" + view);
  window.scrollTo({top:0,behavior:"instant"});
}

function notify(message) {
  const toast = $("toast");
  toast.textContent = message;
  toast.hidden = false;
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => {toast.hidden = true;}, 3000);
}
function text(selector, value) {
  document.querySelectorAll(selector).forEach(el => { el.textContent = String(value); });
}

function sourceNode(item) {
  const row = document.createElement("div"); row.className = "source-item";
  const avatar = document.createElement("div"); avatar.className = "source-icon";
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class","icon"); svg.setAttribute("aria-hidden","true");
  const use = document.createElementNS("http://www.w3.org/2000/svg","use");
  use.setAttribute("href","#i-globe"); svg.append(use); avatar.append(svg);
  const info = document.createElement("div"); info.className = "source-info";
  const name = document.createElement("strong"); name.textContent = item.domain;
  const domain = document.createElement("small"); domain.textContent = item.name;
  info.append(name, domain);
  const tag = document.createElement("span"); tag.className="source-tag"; tag.textContent="مكوّن فقط";
  const inspect=document.createElement("button");
  inspect.type="button"; inspect.className="source-inspect";
  inspect.textContent="التفاصيل"; inspect.setAttribute("aria-label","تفاصيل مصدر "+item.name);
  inspect.addEventListener("click",()=>showSourceDetails(item));
  row.append(avatar,info,tag,inspect);
  return row;
}
function renderSources() {
  const list = $("source-list"); list.replaceChildren();
  const query = $("source-search").value.trim().toLocaleLowerCase();
  const rows = state.snapshot?.sources || [];
  const matched = rows.filter(row => (row.name + " " + row.domain).toLocaleLowerCase().includes(query));
  const showAll = state.expandedSources || query.length > 0;
  const visible = showAll ? matched : matched.slice(0,6);
  $("search-count").textContent = visible.length + " معروض من " + rows.length + " مصدر";
  const toggle=$("toggle-source-list");
  toggle.hidden = query.length>0 || rows.length<=6;
  toggle.textContent = state.expandedSources ? "عرض أول 6 مصادر" : "عرض المصادر الـ"+rows.length;
  toggle.setAttribute("aria-expanded",String(state.expandedSources));
  if (!rows.length) {
    const empty = document.createElement("p"); empty.className="empty-state";
    empty.textContent="لم يتوفر جرد معتمد؛ لا نعرض أسماء غير متحققة.";
    list.append(empty); return;
  }
  if (!matched.length) {
    const empty=document.createElement("p"); empty.className="empty-state";
    empty.textContent="لم تُعثر على مصادر تطابق البحث.";
    list.append(empty); return;
  }
  for(const row of visible) list.append(sourceNode(row));
}
function renderSnapshot(data) {
  if(data.live!==false || data.mode!=="LOCAL_PREVIEW" ||
      !Number.isInteger(data.active_feeds) || !Number.isInteger(data.keywords) ||
      !Number.isInteger(data.research_sources) || !Array.isArray(data.sources))
    throw new Error("Unexpected snapshot contract");
  state.snapshot = data;
  $("count-feeds").textContent=String(data.active_feeds);
  $("count-keywords").textContent=String(data.keywords);
  $("count-research").textContent=String(data.research_sources);
  const at = "26 أكتوبر 2026";
  $("snapshot-date").textContent = "آخر جرد: " + at;
  $("foot-date").textContent = "جرد " + at + " · غير حي";
  renderSources();
}
function renderCase(item) {
  if(item.record_type!=="HISTORICAL_VERIFIED_DEMO" ||
     item.synthetic_company!==true || item.verified_receipt!==true ||
     item.actions_enabled!==false || item.email_sent!==false ||
     item.published_day!=="2026-10-17" || item.publication_precision!=="DATE_ONLY" ||
     !/^([0-9a-f]{64})$/.test(item.evidence_digest) || !Array.isArray(item.proposals))
    throw new Error("Unexpected official-case contract");
  state.caseData=item;
  $("count-demo").textContent="01";
  text(".case-headline",item.headline);
  text(".case-finding",item.finding);
  text(".case-publisher",item.publisher);
  $("executive-headline").textContent=item.headline;
  $("executive-hypothesis").textContent=item.hypothesis;
  $("observed-date").textContent=displayObserved(item.observed_at);
  $("case-report-link").classList.remove("hidden");
  $("case-context").textContent = "سياق افتراضي: " + item.sector + " — " + item.market + ".";
  $("case-fact").textContent = item.finding;
  $("case-hypothesis").textContent=item.hypothesis;
  $("evidence-hash").textContent=item.evidence_digest;
  $("original-link").href=item.original_url;
  const unknowns=$("case-unknowns"); unknowns.replaceChildren();
  for(const line of item.unknowns) {
    const li=document.createElement("li");li.textContent=line;unknowns.append(li);
  }
  const list=$("proposals-list");list.replaceChildren();
  item.proposals.forEach((rec,i) => {
    const card=document.createElement("article");card.className="proposal-item";
    const num=document.createElement("div");num.className="proposal-num";num.textContent=String(i+1).padStart(2,"0");
    const body=document.createElement("div");body.className="proposal-body";
    const title=document.createElement("h4");
    title.textContent=rec.kind==="draft_task"?"مهمة للمراجعة":rec.kind==="draft_report"?"تقرير مقترح":"مسودة توصية";
    const desc=document.createElement("p");desc.textContent=rec.description;
    const meta=document.createElement("div");meta.className="proposal-meta";
    const labels=["مرتبطة بالدليل الأصلي","لم يُعتمد التنفيذ","بلا تكلفة مالية مقدرة"];
    for(const label of labels){const s=document.createElement("span");s.textContent=label;meta.append(s);}
    body.append(title,desc,meta);card.append(num,body);list.append(card);
  });
}

function customerNode(tag,css,content){
 const n=document.createElement(tag);
 if(css)n.className=css;
 if(content!==undefined)n.textContent=String(content);
 return n;
}
function sourceLink(url){
 const parsed=new URL(url);
 if(parsed.protocol!=="https:" || !["mped.gov.eg","www.mped.gov.eg"].includes(parsed.hostname))
  throw Error("unverified_report_link");
 const a=customerNode("a","external-link","اقرأ البيان الأصلي على موقع الوزارة");
 a.href=url;a.target="_blank";a.rel="noopener noreferrer";
 return a;
}
const customerSignals={rows:[],stories:[]};
function renderCustomerSignals(){
 const list=$("customer-signal-list"),report=$("customer-report-stories");
 const p=$("filter-priority").value,s=$("filter-sector").value,
       v=$("filter-verification").value;
 const rows=customerSignals.rows.filter(row=>
  (p==="ALL"||row.priority===p)&&(s==="ALL"||row.sector===s)&&
  (v==="ALL"||row.verification===v));
 list.replaceChildren();report.replaceChildren();
 $("filter-results").textContent="المعروض "+rows.length+" من "+customerSignals.rows.length+
  " إشارتين مُجمعتين من 3 بيانات رسمية؛ ليست تغطية حية.";
 for(const item of rows){
  const small=customerNode("article","customer-signal-item");
  const flag=customerNode("span","customer-priority"+(item.priority==="HIGH"?" high":" low"),item.priority_label);
  const title=customerNode("h3","",item.title);
  const provenance=customerNode("p","customer-scope",item.published+" · "+item.sector_label+" · "+item.verification_label);
  const details=customerNode("details","customer-expand");
  const summary=customerNode("summary","","لماذا يهمني؟ التفاصيل والأدلة");
  details.append(summary,customerNode("p","",item.why),
    customerNode("p","",item.hypothesis),
    customerNode("p","",item.missing));
  small.append(flag,title,provenance,details);
  const open=customerNode("button","btn btn-secondary","افتح التحليل");
  open.type="button";open.addEventListener("click",()=>navigate("report"));
  small.append(open);list.append(small);

  const full=customerNode("article","customer-story");
  full.id=item.id;
  full.append(customerNode("p","customer-scope",item.published+" · "+item.sector_label),
    customerNode("span","customer-priority"+(item.priority==="HIGH"?" high":" low"),item.priority_label),
    customerNode("h3","",item.title));
  const fields=[
    ["الحقائق المعلنة",item.facts.join(" | ")],
    ["أهميته بالنسبة للشركة",item.why],
    ["الفرصة المحتملة (ليست حقيقة)",item.hypothesis],
    ["المخاطر",item.risk],
    ["الإجراء المقترح",item.recommendation],
    ["معلومات ناقصة",item.missing],
    ["المسؤول المقترح",item.suggested_owner],
    ["موعد المتابعة",item.follow_up],
    ["حالة الإثبات",item.verification_label]
  ];
  const cardDetails=customerNode("details","customer-expand");
  cardDetails.append(customerNode("summary","","الحقائق والتحليل والشروط — افتح التفاصيل"));
  for(const [label,value] of fields){
   const para=customerNode("p","customer-story-row");
   para.append(customerNode("strong","",label+" · "),document.createTextNode(value));
   cardDetails.append(para);
  }
  cardDetails.append(customerNode("h4","", "المصادر المرتبطة بهذه الإشارة"));
  for(const sourceId of item.source_ids){
   const source=customerSignals.stories.find(x=>x.id===sourceId);
   if(!source) throw Error("missing_deduplicated_source");
   const container=customerNode("p","customer-source-proof",
     source.published_day+" · "+source.evidence_status+" — ");
   container.append(sourceLink(source.source_url));
   cardDetails.append(container);
  }
  full.append(cardDetails);report.append(full);
 }
 if(!rows.length){
  list.append(customerNode("p","customer-scope","لا توجد إشارات تطابق هذه الفلاتر. غير الفلاتر لعرض النتائج."));
  report.append(customerNode("p","customer-scope","لا توجد نتائج مطابقة."));
 }
}
async function checkOwnerReportDownloads(){
 const links=[...document.querySelectorAll(".customer-downloads a")];
 const checks=await Promise.all(links.map(async a=>{
  a.hidden=true;
  try {
   const response=await fetch(a.getAttribute("href"),{cache:"no-store"});
   if(!response.ok) return false;
   const mime=response.headers.get("content-type")||"";
   const ok=(a.pathname.endsWith(".pdf")&&mime.includes("pdf"))||
            (a.pathname.endsWith(".docx")&&mime.includes("wordprocessingml"));
   if(ok)a.hidden=false;
   return ok;
  }catch{return false;}
 }));
 const ready=checks.filter(Boolean).length;
 $("customer-download-status").textContent=ready
  ?("ملفات المراجعة الجاهزة للتنزيل: "+ready+" من "+links.length+"؛ نسخ محلية وليست إرسالًا بالبريد.")
  :"تنزيل التقرير غير متاح في هذه البيئة. اقرأ المحتوى أدناه، ولا تفترض وجود ملف لم يُنشأ.";
}
function renderCustomerReport(data){
 const cov=data.coverage;
 if(data.schema!=="MAAL_PRODUCT_REVIEW_V1" || data.mode!=="HISTORICAL_LIMITED_REPORT" ||
    data.live_monitoring!==false || data.auto_execution!==false || data.email_sent!==false ||
    cov.active_feeds_configured!==13 || cov.research_catalog!==50 ||
    data.signal_count!==2 || !Array.isArray(data.signals) || data.signals.length!==2 ||
    !Array.isArray(data.stories) || data.stories.length!==3 ||
    !Array.isArray(data.decisions) || data.decisions.length!==3 ||
    !Array.isArray(data.limitations)) throw Error("customer_report_contract_refused");
 for(const story of data.stories)sourceLink(story.source_url);
 for(const signal of data.signals){
   if(!signal.id||!signal.facts.length||signal.eligible_for_execution!==false||
     !signal.source_ids.every(id=>data.stories.some(a=>a.id===id)))
     throw Error("unapproved_customer_signal");
 }
 customerSignals.rows=data.signals;customerSignals.stories=data.stories;
 $("customer-summary").textContent=data.headline_summary+" "+data.summary;
 $("customer-report-period").textContent="الفترة: "+data.period+" · آخر مراجعة: "+data.as_of+" · تاريخية محدودة المصدر";
 $("customer-report-company").textContent="شركة التحليل: "+data.company+" — "+data.company_warning;
 $("customer-report-coverage").textContent=cov.note+" "+cov.not_observed;
 const lead=data.signals[0];
 const answers=[
  ["ماذا حدث؟",lead.facts[0]],
  ["ما مدى أهميته؟",lead.priority_label+"؛ الأثر النقدي المباشر غير مثبت."],
  ["لماذا يهمني؟",lead.why],
  ["ما الدليل؟",lead.verification_label],
  ["ما الإجراء المقترح؟",lead.recommendation],
  ["ما البيانات الناقصة؟",lead.missing]
 ];
 const grid=$("customer-answers");grid.replaceChildren();
 for(const [question,answer] of answers){
  const card=customerNode("article","customer-answer");
  card.append(customerNode("h3","",question),customerNode("p","",answer));
  grid.append(card);
 }
 renderCustomerSignals();
 const limitations=$("customer-report-limitations");limitations.replaceChildren();
 for(const line of data.limitations)limitations.append(customerNode("li","",line));
 const decisions=$("customer-decision-list");decisions.replaceChildren();
 for(const d of data.decisions){
  const card=customerNode("article","customer-decision");
  card.append(customerNode("strong","",d.priority+" — "+d.title),
              customerNode("p","", "المسؤول: "+d.owner),
              customerNode("p","", "المتابعة: "+d.follow_up),
              customerNode("p","", "شرط اتخاذ القرار: "+d.condition),
              customerNode("p","customer-scope",d.approval));
  decisions.append(card);
 }
 checkOwnerReportDownloads();
}
async function getJSON(url) {
  const response=await fetch(url,{cache:"no-store"});
  if(!response.ok) throw new Error(url + ":" + response.status);
  return response.json();
}
let lastReviewRevision=null;
function renderSnapshotReview(data){
 const meta=data.snapshot_meta;
 if(meta){
  if(meta.kind!=="HISTORICAL_READONLY_QA" || meta.source_live_connected!==false ||
     meta.no_email_sent!==true || meta.source_new_verified_news_count!==0 ||
     typeof meta.revision!=="string")throw Error("unapproved_snapshot_review");
  if(meta.revision===lastReviewRevision)return;
  const d=new Date(meta.generated_utc);
  if(!Number.isFinite(d.getTime()))throw Error("missing_generation_clock");
  renderCustomerReport(data);
  lastReviewRevision=meta.revision;
  $("customer-snapshot-status").textContent=
     "آخر تحديث لحزمة المراجعة التاريخية: "+new Intl.DateTimeFormat("ar-EG",{
      dateStyle:"medium",timeStyle:"medium",timeZone:"Africa/Cairo"
     }).format(d)+" · مستجدات موثّقة جديدة: صفر · آخر دليل صورة أصلية مؤكد: 17 أكتوبر. هذا ليس فحص RSS حيًا.";
  return;
 }
 lastReviewRevision=null;
 renderCustomerReport(data);
 $("customer-snapshot-status").textContent=
   "نسخة تقرير مؤرشفة؛ لا توجد مزامنة أخبار حية مؤكدة.";
}
async function pollSafeReview(){
 try {const data=await getJSON("/product_report.json");renderSnapshotReview(data);}
 catch{$("customer-snapshot-status").textContent=
  "HOLD: تعذّر التحقق من حزمة المراجعة. لا يُفترض وجود أخبار جديدة.";}
}
async function loadData() {
  const [snapshot, caseResult] = await Promise.allSettled([
    getJSON("/api/snapshot"),getJSON("/api/case")
  ]);
  if(snapshot.status==="fulfilled"){
    try {renderSnapshot(snapshot.value);}
    catch(err){notify("بيانات الجرد لا تطابق العقد المعتمد.");}
  } else {
    $("snapshot-date").textContent="الجرد غير متاح";
    $("foot-date").textContent="لم يتم تحميل أي أرقام غير مثبتة";
    renderSources();
  }
  if(caseResult.status==="fulfilled") {
    try{renderCase(caseResult.value);}
    catch(err){showCaseUnavailable();}
  }else showCaseUnavailable();
  getJSON("/product_report.json").then(renderSnapshotReview).catch(()=>{
    $("customer-summary").textContent="هذا التقرير قيد المراجعة: تعذر تحميل نسخة بيانات مؤرخة ومطابقة للعقد.";
    $("customer-report-period").textContent="HOLD — لا توجد نسخة تقرير مؤكدة للعرض الآن.";
    $("customer-report-coverage").textContent="لا يتم إنشاء بدائل تخمينية عند غياب المصدر.";
  });
  getJSON("/api/ai-analysis").then(renderLocalAI).catch(()=>{
    $("ai-run-status").textContent="لا توجد نتيجة نموذج فعلية مطابقة للدليل لعرضها الآن.";
    $("ai-run-badge").textContent="HOLD";
    $("ai-use-draft").disabled=true;
  });
}
function showCaseUnavailable() {
  state.caseData=null;
  $("count-demo").textContent="—";
  $("executive-headline").textContent="لم يتم تأكيد الدليل؛ التحليل موقوف.";
  $("executive-hypothesis").textContent="لا توصية دون مستند موثوق.";
  $("observed-date").textContent="غير متاح";
  $("case-report-link").classList.add("hidden");
  text(".case-headline","حالة الدليل غير متاحة للتحقق الآن");
  text(".case-finding","لا يمكن إظهار تحليل أو توصيات بغير دليل أصلي مطابق.");
  $("evidence-hash").textContent="UNVERIFIED";
  $("proposals-list").textContent="لا توصيات متاحة حتى عودة الدليل المتحقق.";
  $("case-fact").textContent="التحقق متوقف بسبب غياب دليل مطابق.";
  $("case-hypothesis").textContent="لا تحليل متاح.";
  $("case-unknowns").replaceChildren();
  document.querySelectorAll(".feature-image, #evidence-image").forEach(image => {image.hidden=true;});
  document.querySelectorAll(".badge-teal").forEach(badge => {badge.textContent="التحقق غير متاح";});
  notify("لا يمكن اعتماد الدليل: فشل فحص النسخة المحلية.");
}
function displayObserved(iso) {
  const d=new Date(iso);
  if (!Number.isFinite(d.getTime())) return "تاريخ التحقق غير متاح";
  return new Intl.DateTimeFormat("ar-EG",{
    dateStyle:"medium",timeStyle:"short",timeZone:"Africa/Cairo"
  }).format(d)+" (القاهرة) — وقت الفحص، لا وقت النشر";
}

function showSourceDetails(item) {
  const dialog=$("source-dialog");
  $("source-dialog-title").textContent=item.name;
  const host=$("source-dialog-content");host.replaceChildren();
  const row=(heading,value)=>{
    const group=document.createElement("div");group.className="source-detail-row";
    const label=document.createElement("strong");label.textContent=heading;
    const v=document.createElement("p");v.textContent=value;
    group.append(label,v);host.append(group);
  };
  row("وضع المصدر","مفعّل في الإعدادات فقط — لم تُفحص سلامة RSS لحظيًا");
  row("النطاق",item.domain);
  row("النطاقات المعتمدة للأخبار",item.allowed_article_hosts.join(" · "));
  const a=document.createElement("a");a.className="external-link";
  a.href=item.feed_url;a.target="_blank";a.rel="noopener noreferrer";
  a.textContent="افتح رابط RSS الرسمي في نافذة جديدة";
  host.append(a);
  dialog.showModal();
}

function fillCommands() {
 const input=$("command-query");
 const query=input.value.trim().toLocaleLowerCase("ar");
 const root=$("command-results");root.replaceChildren();
 for(const [id,[label]] of Object.entries(VIEWS)) {
   if(!label.toLocaleLowerCase("ar").includes(query) &&
      !id.toLowerCase().includes(query))continue;
   const btn=document.createElement("button");btn.type="button";
   btn.className="command-item";btn.textContent=label;
   btn.addEventListener("click",()=>{$("command-dialog").close();navigate(id);});
   root.append(btn);
 }
 if(!root.children.length){
   const p=document.createElement("p");p.className="empty-state";
   p.textContent="لا توجد أقسام مطابقة";root.append(p);
 }
}
function makeReviewMemo(){
 const item=state.caseData;if(!item)return null;
 const note=$("review-note").value.trim() || "لم تُكتب ملاحظات إضافية.";
 const proposals=item.proposals.map((p,i)=>
   String(i+1)+". "+p.description).join("\n");
 return [
   "مَآل | MA'AL — مذكرة استعراض محلية غير معتمدة",
   "التجربة: تاريخية، والشركة المستخدمة افتراضية.",
   "الناشر: "+item.publisher,
   "تاريخ النشر (دون ساعة): "+item.published_day,
   "الرابط الأصلي: "+item.original_url,
   "بصمة الدليل: "+item.evidence_digest,
   "النتيجة المسندة: "+item.finding,
   "الأثر المحتمل المشروط: "+item.hypothesis,
   "ما لم يثبت: "+item.unknowns.join("؛ "),
   "توصيات للمراجعة فقط:\n"+proposals,
   "ملاحظة المراجع: "+note,
   "هذه المذكرة ليست موافقة ولا تتضمن أي إجراء إنتاجي أو تقدير مالي معتمد."
 ].join("\n\n");
}

function renderLocalAI(result){
  const record=state.caseData;
  if(!record || result.record_type!=="ACTUAL_MODEL_OUTPUT_AWAITING_HUMAN_REVIEW" ||
     result.source_id!==record.evidence_id ||
     result.source_sha256!==record.evidence_digest ||
     result.actions_executed!==false || result.status!=="AI_DRAFT_UNREVIEWED" ||
     result.quality_approval!=="HOLD_HUMAN_REVIEW" ||
     !Array.isArray(result.unknowns) || !Array.isArray(result.alternatives)){
    throw Error("Untrusted model result");
  }
  $("ai-run-status").textContent="نتيجة استدلال CPU حقيقية، لكنها مسودة لم تُراجع من خبير؛ لا تمثل قرارًا معتمدًا.";
  $("ai-run-badge").textContent="استدلال فعلي · مراجعة مطلوبة";
  $("ai-run-metadata").textContent="النموذج: "+result.model+" · مدة تشغيله: "+result.inference_seconds+
    " ثانية · معرّف التشغيل: "+result.run_id+" · توقيت حفظ النتيجة: "+result.recorded_at+
    " · تكلفة API: $0 · دليل: "+result.source_id;
  $("ai-inference").textContent=result.inference;
  $("ai-recommendation").textContent=result.recommendation;
  for(const [nodeId,values] of [["ai-unknowns",result.unknowns],["ai-alternatives",result.alternatives]]){
    const node=$(nodeId);node.replaceChildren();
    for(const value of values){const li=document.createElement("li");li.textContent=value;node.append(li);}
  }
  $("ai-use-draft").disabled=false;
  $("ai-use-draft").onclick=()=>{
    const target=$("operator-description");
    target.value=result.recommendation;
    target.dataset.modelRunId=result.run_id;
    navigate("decisions");
    $("operator-lab").scrollIntoView({behavior:"smooth",block:"start"});
  };
}

function init() {
  $("ai-fresh-run").addEventListener("click",async()=>{
    const button=$("ai-fresh-run");
    button.disabled=true;
    $("ai-run-badge").textContent="جارٍ الاستدلال الحقيقي";
    $("ai-run-status").textContent="Qwen3 يعمل الآن على CPU المحلي. لا توجد موافقة أو إجراء خلال التحليل.";
    try {
      const operator=await getJSON("/api/operator/state");
      if(!operator.csrf || operator.role!=="OWNER")throw new Error("مطلوب تسجيل دخول مالك حساب المختبر من مركز القرارات.");
      const response=await fetch("/api/ai/run",{
        method:"POST",credentials:"same-origin",cache:"no-store",
        headers:{"Content-Type":"application/json","X-CSRF-Token":operator.csrf},
        body:JSON.stringify({intent:"fresh_historical_demo_only"})
      });
      if(!response.ok)throw new Error("تعذر تشغيل النموذج أو فشل فحص المصدر؛ HTTP "+response.status);
      const payload=await response.json();
      renderLocalAI(payload.analysis);
      notify("اكتمل استدلال فعلي جديد. النتيجة تتطلب مراجعة بشرية.");
    }catch(err){
      $("ai-run-badge").textContent="HOLD";
      $("ai-run-status").textContent=err.message;
      $("ai-use-draft").disabled=true;
    }finally{button.disabled=false;}
  });
  selectors.forEach(button=>button.addEventListener("click",()=>navigate(button.dataset.view)));
  document.querySelectorAll("[data-go]").forEach(button=>button.addEventListener("click",()=>navigate(button.dataset.go)));
  $("source-search").addEventListener("input",renderSources);
  for(const id of ["filter-priority","filter-sector","filter-verification"])
    $(id).addEventListener("change",renderCustomerSignals);
  $("toggle-source-list").addEventListener("click",()=>{state.expandedSources=!state.expandedSources;renderSources();});
  $("source-close").addEventListener("click",()=>{$("source-dialog").close();});
  $("source-done").addEventListener("click",()=>{$("source-dialog").close();});
  $("command-close").addEventListener("click",()=>{$("command-dialog").close();});
  $("quick-open").addEventListener("click",()=>{
    $("command-query").value="";fillCommands();
    $("command-dialog").showModal();$("command-query").focus();
  });
  $("command-query").addEventListener("input",fillCommands);
  document.addEventListener("keydown",e=>{
    if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==="k"){
      e.preventDefault();
      if(!$("command-dialog").open){
        $("command-query").value="";fillCommands();
        $("command-dialog").showModal();$("command-query").focus();
      } else $("command-dialog").close();
    }
  });
  $("copy-review").addEventListener("click",async()=>{
    const memo=makeReviewMemo();
    if(!memo)return notify("لا يوجد دليل معتمد لإعداد المذكرة.");
    try{await navigator.clipboard.writeText(memo);
        notify("تم نسخ مذكرة المراجعة، دون حفظ أو إرسال أي بيانات.");}
    catch(err){notify("تعذّر النسخ؛ تأكد من صلاحيات الحافظة.");}
  });
  $("copy-hash").addEventListener("click",async()=>{
    if(!state.caseData) return notify("البصمة غير متاحة.");
    try {await navigator.clipboard.writeText(state.caseData.evidence_digest);notify("تم نسخ بصمة الصورة الأصلية.");}
    catch(err){notify("تعذر النسخ تلقائيًا؛ يمكن نسخ البصمة الظاهرة يدويًا.");}
  });
  const target=location.hash.slice(1);
  navigate(Object.hasOwn(VIEWS,target)?target:"overview",false);
  window.addEventListener("hashchange",()=>navigate(location.hash.slice(1),false));
  loadData();
  // Existing historical-review UI only: refresh snapshot metadata without build/reload.
  setInterval(pollSafeReview,12000);
}
document.addEventListener("DOMContentLoaded",init);
