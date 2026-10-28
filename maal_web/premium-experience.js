"use strict";
/* Premium orchestration changes PRESENTATION only. Original V0.3 elements,
   event handlers, IDs, security API, stored drafts and reports are preserved. */
document.addEventListener("DOMContentLoaded",()=>{
 const $=id=>document.getElementById(id);
 document.body.classList.add("maal-premium");
 const nav=document.querySelector(".sidebar .main-nav");
 const labels={overview:"لوحة القيادة",monitor:"الإشارات",impact:"التحليل الذكي",
  decisions:"مركز القرارات",operations:"المهام والمتابعة",report:"التقارير",evidence:"الأدلة"};
 const links=[...document.querySelectorAll(".nav-link[data-view]")];
 for(const view of Object.keys(labels)){
  const b=links.find(x=>x.dataset.view===view);
  if(b){const s=b.querySelector("span");if(s)s.textContent=labels[view];nav.append(b)}
 }
 document.querySelector(".advanced-menu")?.setAttribute("hidden","");
 const logo=document.querySelector(".brand-icon");
 if(logo){logo.src="/brand-symbol-approved.png";logo.alt="رمز مَآل المعتمد";}
 const top=document.querySelector(".topbar");
 const sidebar=document.querySelector(".sidebar");
 const backdrop=document.createElement("button");
 backdrop.type="button";backdrop.id="premium-navigation-backdrop";
 backdrop.className="premium-navigation-backdrop";backdrop.hidden=true;
 backdrop.setAttribute("aria-label","إغلاق قائمة الأقسام");
 document.body.append(backdrop);
 const closeNav=(returnFocus=false)=>{
  if(!sidebar)return;
  sidebar.classList.remove("premium-drawer-open");backdrop.hidden=true;
  sidebar.removeAttribute("role");sidebar.removeAttribute("aria-modal");
  navButton?.setAttribute("aria-expanded","false");
  navButton?.setAttribute("aria-label","فتح قائمة أقسام مَآل");
  if(returnFocus && navButton?.offsetParent!==null)navButton.focus();
 };
 let navButton=null;
 if(top){const mark=document.createElement("div");mark.className="premium-mobile-brand";
  const img=document.createElement("img");img.src="/brand-symbol-approved.png";img.alt="";
  const label=document.createElement("span");label.textContent="مَآل";
  mark.append(img,label);top.prepend(mark);
  navButton=document.createElement("button");navButton.type="button";
  navButton.id="premium-navigation-toggle";navButton.className="premium-navigation-toggle";
  navButton.setAttribute("aria-controls","premium-navigation");
  navButton.setAttribute("aria-label","فتح قائمة أقسام مَآل");
  navButton.setAttribute("aria-expanded","false");
  const icon=document.createElement("span");icon.setAttribute("aria-hidden","true");icon.textContent="☰";
  const txt=document.createElement("span");txt.textContent="الأقسام";
  navButton.append(icon,txt);mark.after(navButton);
  sidebar.id="premium-navigation";
  navButton.addEventListener("click",()=>{
   const opening=!sidebar.classList.contains("premium-drawer-open");
   if(opening){
    sidebar.classList.add("premium-drawer-open");backdrop.hidden=false;
    sidebar.setAttribute("role","dialog");sidebar.setAttribute("aria-modal","true");
    navButton.setAttribute("aria-expanded","true");
    navButton.setAttribute("aria-label","إغلاق قائمة أقسام مَآل");
    sidebar.querySelector(".nav-link.active")?.focus();
   }else closeNav(true);
  });
  backdrop.addEventListener("click",()=>closeNav(true));
  document.addEventListener("keydown",event=>{
   if(!sidebar.classList.contains("premium-drawer-open"))return;
   if(event.key==="Escape"){event.preventDefault();closeNav(true);return}
   if(event.key==="Tab"){
    const visible=[...sidebar.querySelectorAll(".nav-link:not([disabled])")];
    if(!visible.length)return;
    const first=visible[0],last=visible[visible.length-1];
    if(event.shiftKey && document.activeElement===first){
     event.preventDefault();last.focus();
    }else if(!event.shiftKey && document.activeElement===last){
     event.preventDefault();first.focus();
    }
   }
  });
  window.addEventListener("resize",()=>{if(innerWidth>1040)closeNav()});
  links.forEach(button=>button.addEventListener("click",()=>closeNav()));
 }
 const go=view=>links.find(x=>x.dataset.view===view)?.click();
 const overview=$("view-overview"),monitor=$("view-monitor"),impact=$("view-impact");
 const decision=$("view-decisions"),operations=$("view-operations"),report=$("view-report");
 if(!overview||!monitor||!impact||!decision||!operations||!report)return;
 const move=(id,to,prepend=false)=>{const node=$(id);if(node){if(prepend)to.prepend(node);else to.append(node)}};
 move("new-signal-workspace",monitor,true);
 move("paired-ai-benchmark",impact,true);
 move("agent-journey-board",decision,true);
 move("business-value-study",report);
 move("new-signal-demo-download",report,true);
 const home=document.createElement("section");home.id="premium-executive";home.className="premium-executive";
 home.innerHTML="<section class=\"premium-hero\" aria-labelledby=\"premium-welcome\">\n <div><p class=\"premium-kicker\" dir=\"ltr\">MAAL / BUSINESS DECISION INTELLIGENCE</p>\n <h2 id=\"premium-welcome\">من الإشارة <span>إلى القرار.</span></h2>\n <p>افهم التطور الذي يهم شركتك، افتح دليله الأصلي، ثم راجع حدود توصية الذكاء الاصطناعي قبل أي إجراء.</p>\n <div class=\"premium-actions\"><button type=\"button\" id=\"premium-go-signals\">الإشارات الموثقة</button><button type=\"button\" id=\"premium-go-decisions\">قراراتي</button></div></div>\n <aside class=\"premium-hero-aside\"><div><strong>حالة الوكيل الحالية</strong><p id=\"premium-stage-statement\" aria-live=\"polite\">جارٍ التحقق من المصدر والتحليل.</p></div><small>نسخة محلية · أدلة تاريخية · لا رصد حي مثبت · لا موافقة آلية</small></aside>\n </section>\n <div class=\"premium-status-grid\" aria-label=\"مؤشرات مصدرها البيانات المحلية\">\n <div class=\"premium-stat\"><span>مصادر رسمية محفوظة</span><strong id=\"premium-source-count\">—</strong><small>صور أصلية وبصمات قابلة للفحص</small></div>\n <div class=\"premium-stat\"><span>تحليلات غير معتمدة</span><strong id=\"premium-hold-count\">—</strong><small>ليست توصيات تنفيذ جاهزة</small></div>\n <div class=\"premium-stat\"><span>قراراتي</span><strong id=\"premium-owner-count\">—</strong><small id=\"premium-owner-sub\">يلزم تسجيل دخول المالك</small></div></div>\n <section class=\"premium-panel\" aria-labelledby=\"premium-signal-heading\">\n <div class=\"premium-panel-head\"><h3 id=\"premium-signal-heading\">إشارة مختارة من الأدلة المتاحة</h3><span id=\"premium-signal-status\" class=\"premium-pill\" data-tone=\"historical\">تاريخية محفوظة</span></div>\n <div class=\"premium-featured\"><div><p class=\"premium-muted\" id=\"premium-signal-meta\">الناشر وتاريخ النشر والتحقق</p><h4 id=\"premium-signal-title\">جارٍ قراءة المصدر…</h4><p id=\"premium-signal-desc\">مصدر مثبت، لكن أثره التجاري ما زال خاضعًا للتقييم.</p></div>\n <div class=\"premium-insight\"><strong>هل توجد توصية جاهزة؟</strong><p id=\"premium-signal-impact\">لا اعتماد قبل المراجعة التحريرية.</p><button type=\"button\" id=\"premium-inspect-signal\">افتح المصدر والتحليل</button></div></div></section>\n <section class=\"premium-panel\" aria-labelledby=\"premium-path-heading\"><div class=\"premium-panel-head\"><h3 id=\"premium-path-heading\">من الدليل إلى الإجراء</h3><span class=\"premium-pill\" data-tone=\"historical\">خطوات مثبتة وحدود واضحة</span></div>\n <ol class=\"premium-flow\"><li data-phase=\"done\"><strong>01 · الإشارة</strong><small>صفحة ناشر محفوظة</small></li><li data-phase=\"done\"><strong>02 · الدليل</strong><small>صورة وبصمة</small></li><li data-phase=\"hold\"><strong>03 · التحليل</strong><small>HOLD في الجودة</small></li><li data-phase=\"pending\"><strong>04 · المراجعة</strong><small>لم تُقبل تحريرياً</small></li><li data-phase=\"pending\"><strong>05 · موافقة المالك</strong><small>قرار بشري</small></li><li data-phase=\"pending\"><strong>06 · التنفيذ</strong><small>لا مهمة جديدة</small></li></ol></section>";
 overview.prepend(home);
 const legacy=document.createElement("details");legacy.id="premium-historical-details";legacy.className="premium-legacy";
 const summary=document.createElement("summary");summary.textContent="الدراسة التاريخية السابقة والتفاصيل الفنية — عرض عند الطلب";
 const legacyBody=document.createElement("div");legacyBody.className="premium-legacy-body";
 for(const node of [...overview.children])if(node!==home)legacyBody.append(node);
 legacy.append(summary,legacyBody);overview.append(legacy);
 const dec=document.createElement("section");dec.className="premium-decision-summary";
 dec.innerHTML='<h3>مركز قرارات المالك</h3><p id="premium-decision-message" role="status">سجّل الدخول لعرض مسوداتك.</p><span class="premium-pill" data-tone="historical">اقتراح AI ≠ موافقة بشرية</span>';
 decision.prepend(dec);
 const lab=document.getElementById("advanced-operator-review");
 if(lab){
  const drawer=document.createElement("details");drawer.className="premium-owner-console";
  drawer.id="premium-owner-console";
  const opener=document.createElement("summary");
  opener.textContent="افتح مسوداتك والمراجعة والموافقة المحمية";
  drawer.append(opener);
  lab.before(drawer);drawer.append(lab);lab.open=true;
  document.getElementById("account-entry")?.addEventListener("click",()=>{
   if(!document.getElementById("header-logout")?.hidden)drawer.open=true;
  });
  document.getElementById("agent-journey-review")?.addEventListener("click",()=>{drawer.open=true});
  document.getElementById("new-signal-draft")?.addEventListener("click",()=>{drawer.open=true});
  window.addEventListener("maal:benchmark-review-selected",()=>{drawer.open=true});
 }
 const activity=document.createElement("section");activity.className="premium-timeline";
 activity.innerHTML='<h3>المهام وسجل القرارات</h3><div id="premium-audit-events" role="status">سجّل الدخول لعرض السجل الخاص بحسابك.</div>';
 operations.prepend(activity);
 const reports=document.createElement("div");reports.className="premium-reports-head";
 reports.innerHTML='<h3>التقارير والأدلة</h3><p>مخرجات محفوظة من حالات سابقة، وليست تقارير أخبار حية. الروابط لا تظهر إلا عندما يتوفر الملف في التطبيق.</p>';
 report.prepend(reports);
 $("premium-go-signals")?.addEventListener("click",()=>go("monitor"));
 $("premium-go-decisions")?.addEventListener("click",()=>go("decisions"));
 $("premium-inspect-signal")?.addEventListener("click",()=>go("monitor"));
 const set=(id,v)=>{const n=$(id);if(n)n.textContent=String(v)};
 function parseDate(v){
  const d=new Date(v);return !v||isNaN(+d)?"غير مثبت":
   new Intl.DateTimeFormat("ar-EG",{timeZone:"Africa/Cairo",dateStyle:"medium"}).format(d)
 }
 const fetchVerifiedSources=async()=>{
  // The source gateway re-checks original screenshots and SHA-256 for every
  // request. Never substitute stale data if a transient read fails.
  let lastError;
  for(let attempt=0;attempt<3;attempt++){
   try{
    const response=await fetch("/api/new-signals",{cache:"no-store",credentials:"same-origin"});
    if(!response.ok)throw new Error("source gateway HTTP "+response.status);
    const data=await response.json();
    if(data.schema!=="MAAL_NEW_OFFICIAL_SIGNALS_V1")throw new Error("source contract HOLD");
    return data;
   }catch(e){
    lastError=e;
    if(attempt<2)await new Promise(resolve=>setTimeout(resolve,(attempt+1)*650));
   }
  }
  throw lastError;
 };
 fetchVerifiedSources()
 .then(data=>{
  if(data.schema!=="MAAL_NEW_OFFICIAL_SIGNALS_V1")throw Error("unsafe data");
  const items=data.items||[],pending=items.filter(x=>x.editorial_review?.status!=="APPROVED");
  set("premium-source-count",items.length);set("premium-hold-count",pending.length);
  set("premium-stage-statement",pending.length+" من "+items.length+" إشارات محفوظة لم تحصل على قبول تحريري للتنفيذ.");
  const chosen=items.find(x=>x.case.source_key==="fpt")||items[0];
  if(!chosen)return;
  const c=chosen.case,r=chosen.editorial_review||{};
  set("premium-signal-title",c.headline);
  set("premium-signal-meta",c.publisher+" · نُشر: "+(c.published_day||"غير مثبت")+" · رُصد: "+parseDate(c.observed_at));
  set("premium-signal-desc","حدث منشور ومثبت، أما أثره على الشركة الافتراضية فمشروط ببيانات لم تُثبت بعد.");
  set("premium-signal-impact",r.status==="APPROVED"?"مراجعة مسجلة؛ قرار المالك مستقل.":"HOLD — لا توصية تنفيذية مقبولة لهذه الإشارة.");
  const pill=$("premium-signal-status");
  if(pill){pill.textContent=r.status==="APPROVED"?"دليل محفوظ ومراجعة مثبتة":"دليل محفوظ · التوصية غير مقبولة";pill.dataset.tone=r.status==="APPROVED"?"verified":"hold"}
 }).catch(()=>{set("premium-stage-statement","المصدر غير متاح حاليًا؛ لا يمكن تقييم إشارة أو اعتماد قرار.");
  set("premium-signal-title","تعذّر التحقق من مصدر الإشارة.");
  set("premium-source-count","—");set("premium-hold-count","—");
  const pill=$("premium-signal-status");
  if(pill){pill.textContent="المصدر غير متاح";pill.dataset.tone="hold"}
 });
 async function refreshOwner(){
  try{
   const r=await fetch("/api/operator/state",{cache:"no-store",credentials:"same-origin"});
   if(r.status===401||r.status===403){
    set("premium-owner-count","—");set("premium-owner-sub","يلزم تسجيل الدخول");
    set("premium-decision-message","الدخول من أعلى الصفحة مطلوب لعرض مسوداتك وقراراتك الخاصة.");
    set("premium-audit-events","سجّل الدخول لعرض أحداث حسابك.");return
   }
   if(!r.ok)throw Error("owner state unavailable");
   const data=await r.json(),drafts=data.drafts||[],audit=data.audit||[];
   const waiting=drafts.filter(x=>x.state==="DRAFT");
   const executed=drafts.filter(x=>x.state==="EXECUTED");
   set("premium-owner-count",drafts.length);
   set("premium-owner-sub",waiting.length+" مسودة للمراجعة · "+executed.length+" مهمة منفذة في السجل");
   set("premium-decision-message",waiting.length?
    "لديك "+waiting.length+" مسودة، منها "+waiting.filter(x=>x.can_approve!==true).length+" محجوبة لحين إكمال مراجعة الجودة.":"لا توجد مسودات معلقة لهذا الحساب.");
   const root=$("premium-audit-events");root.replaceChildren();
   if(!audit.length){root.textContent="لا توجد أحداث مثبتة في هذا الحساب.";return}
   const map={DRAFT_CREATED:"إنشاء مسودة",HUMAN_APPROVED:"اعتماد بشري",HUMAN_REJECTED:"رفض بشري",
    INTERNAL_TASK_EXECUTED:"تنفيذ مهمة داخلية",OWNER_CHALLENGE_ISSUED:"تأكيد المالك",
    OWNER_EDITORIAL_SIGNED:"إقرار تحريري"};
   for(const ev of audit.slice(0,12)){
    const item=document.createElement("div");item.className="premium-event";
    const title=document.createElement("strong");title.textContent=map[ev.event]||ev.event;
    const meta=document.createElement("small");meta.textContent=ev.timestamp?parseDate(ev.timestamp):"وقت غير مثبت";
    item.append(title,meta);root.append(item);
   }
  }catch(_){set("premium-owner-sub","تعذر التحقق");
   set("premium-decision-message","تعذر قراءة القرارات المحفوظة. لا نفترض أي موافقة.");
   set("premium-audit-events","تعذر إثبات سجل التدقيق.")}
 }
 window.addEventListener("maal:auth-changed",refreshOwner);
 refreshOwner();
});