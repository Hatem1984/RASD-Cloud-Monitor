"use strict";
/* MA'AL Gate F operator lab; intentionally test-only and authenticated.
   This browser never receives owner challenge secrets or raw SQLite files. */
document.addEventListener("DOMContentLoaded", () => {
 const by=id=>document.getElementById(id);
 const app={csrf:"", selected:null,rows:[],actor:null,role:null,busy:false};
 const feedback=(message,ok=false)=>{let el=by("operator-feedback");el.textContent=message;el.dataset.ok=String(ok);};
 async function loadGuestPreview(){
   const root=by("operator-guest-summary");root.replaceChildren();
   try{
     const r=await fetch("/api/demo/preview",{cache:"no-store",credentials:"omit"});
     let data;
     if(r.ok) data=await r.json();
     else if(r.status===404){
       // Existing already-open server may have the new static frontend but not
       // the preview API until its next controlled restart.
       const [caseR,modelR]=await Promise.all([
         fetch("/api/case",{cache:"no-store"}),
         fetch("/api/ai-analysis",{cache:"no-store"})]);
       if(!caseR.ok||!modelR.ok)throw new Error("البيانات الموثقة غير متاحة");
       const source=await caseR.json(),model=await modelR.json();
       data={mode:"LOCAL_GUEST_READ_ONLY",authenticated:false,
         can_approve:false,can_execute:false,
         publisher:source.publisher,source_day:source.published_day,
         model_run_id:model.run_id,model_seconds:model.inference_seconds,
         recommendation_unapproved:model.recommendation,
         drafts:[],audit_events:"غير معروض في الإصدار الحالي",
         audit_integrity:"يتطلب تحديث الخادم"};
     }else throw new Error("HTTP "+r.status);
     if(data.mode!=="LOCAL_GUEST_READ_ONLY"||data.authenticated||data.can_execute||data.can_approve)throw new Error("unsupported_demo_security_mode");
     const field=(label,value)=>{
       const row=document.createElement("p");row.className="context-hint";
       const title=document.createElement("strong");title.textContent=label+" ";
       const val=document.createElement("span");val.textContent=String(value);
       row.append(title,val);root.append(row);
     };
     field("المصدر الموثق:",data.publisher+" · "+data.source_day+" (خبر تاريخي)");
     field("معرف تشغيل Qwen3 الحقيقي:",data.model_run_id);
     field("مدة تشغيل النموذج:",data.model_seconds+" ثانية · نتيجة محفوظة وليست تشغيلًا حيًا الآن");
     field("التوصية غير المعتمدة:",data.recommendation_unapproved);
     for(const item of data.drafts){
       field("المسودة "+item.draft_id+":",item.state+" — "+item.description);
     }
     field("سجل التدقيق:",data.audit_events+" حدث · "+data.audit_integrity);
     field("حدود الصلاحيات:","عرض فقط؛ لا موافقات ولا تنفيذ ولا إرسال بريد.");
   }catch(err){
     const p=document.createElement("p");p.textContent="تعذر فتح العرض التجريبي: "+err.message;root.append(p);
   }
 }

 const dialog=by("login-dialog");
 const accountButton=by("account-entry");
 const accountLabel=by("account-entry-label");
 const headerLogout=by("header-logout");
 const loginFeedback=by("login-feedback");
 function announceLogin(message,error=false){
   loginFeedback.hidden=!message;
   loginFeedback.textContent=message;
   loginFeedback.dataset.error=String(error);
 }
 function showLogin(){
   if(app.actor)return goToMyDecisions();
   announceLogin("");
   if(!dialog.open)dialog.showModal();
   by("operator-username").focus();
 }
 function goToMyDecisions(){
   const nav=document.querySelector('.nav-link[data-view="decisions"]');
   if(nav)nav.click();
   const advanced=by("advanced-operator-review");
   if(advanced)advanced.open=true;
   const target=by("operator-drafts");
   if(target)target.scrollIntoView({behavior:"smooth",block:"center"});
 }
 function syncAccountHeader(){
   const signedIn=Boolean(app.actor);
   accountLabel.textContent=signedIn?"قراراتي"+(app.rows.filter(r=>r.state==="DRAFT").length?" ("+app.rows.filter(r=>r.state==="DRAFT").length+")":""):"تسجيل الدخول";
   accountButton.classList.toggle("signed-in",signedIn);
   accountButton.setAttribute("aria-haspopup",signedIn?"false":"dialog");
   accountButton.setAttribute("aria-label",signedIn?"فتح قرارات حساب "+app.actor:"تسجيل الدخول إلى مَآل");
   headerLogout.hidden=!signedIn;
 }
 async function getState(){
   try{
     const r=await fetch("/api/operator/state",{cache:"no-store",credentials:"same-origin"});
     if(r.status===401){loggedOut();return false;}
     if(!r.ok)throw new Error("state_unavailable");
     const data=await r.json();
     app.csrf=data.csrf;app.actor=data.operator;app.role=data.role;app.rows=data.drafts;
     by("operator-guest-demo").hidden=true;
     by("operator-authenticated").hidden=false;
     by("operator-whoami").textContent="مستخدم: "+data.operator+" · بيئة: "+data.tenant+" · "+data.role;
     syncAccountHeader();
     renderDrafts();renderAudit(data.audit,data.audit_integrity);
     window.dispatchEvent(new Event("maal:auth-changed"));
     return true;
   }catch(e){
     feedback("تعذّر الاتصال بمخزن المهام التجريبي. لم نفترض نجاح الدخول.");
     return false;
   }
 }
 function loggedOut(){
   app.csrf="";app.actor=null;app.role=null;app.selected=null;app.rows=[];
   by("operator-guest-demo").hidden=false;by("operator-authenticated").hidden=true;
   by("operator-password").value="";by("operator-stepup").value="";
   by("login-reveal-password").checked=false;
   by("operator-password").type="password";
   syncAccountHeader();
   window.dispatchEvent(new Event("maal:auth-changed"));
 }
 async function post(path,data){
  const headers={"Content-Type":"application/json"};
  if(path!=="/api/operator/login")headers["X-CSRF-Token"]=app.csrf;
  const r=await fetch(path,{method:"POST",headers,credentials:"same-origin",
                            body:JSON.stringify(data),cache:"no-store"});
  if(!r.ok)throw new Error(r.status===403?"غير مصرح: تحقق من بيانات الدخول أو الصلاحية.":(
      r.status===400?"بيانات غير صحيحة أو دليل لم يُعتمد.":"تعذر إكمال العملية؛ لم يتم افتراض النجاح."));
  return r.json();
 }
 const svgSvg=()=>{
  const span=document.createElement("span");span.className="operator-state-symbol";
  span.textContent="◈";return span;
 };
 function renderDrafts(){
  const root=by("operator-drafts");root.replaceChildren();
  if(!app.rows.length){const p=document.createElement("p");p.className="operator-empty";p.textContent="لا توجد مهام داخلية لهذا المستخدم.";root.append(p);}
  app.rows.forEach(item=>{
    const btn=document.createElement("button");btn.type="button";btn.className="operator-draft-item";
    btn.dataset.draftId=item.draft_id;
    btn.classList.toggle("chosen",app.selected===item.draft_id);
    btn.setAttribute("aria-pressed",String(app.selected===item.draft_id));
    btn.append(svgSvg());
    const info=document.createElement("span");info.className="operator-draft-info";
    const title=document.createElement("strong");title.textContent=item.description;
    const meta=document.createElement("small");
    meta.textContent="معرّف المسودة: "+item.draft_id+" · الحالة: "+item.state+" · دليل: "+item.evidence_id+(item.approved_by?" · المعتمد: "+item.approved_by:"");
    const states=document.createElement("span");
    states.className="premium-decision-states";
    const addStage=(label,tone)=>{
      const chip=document.createElement("span");chip.className="premium-decision-stage";
      chip.dataset.tone=tone;chip.textContent=label;states.append(chip);
    };
    addStage(item.state==="EXECUTED"?"حالة تاريخية منفذة":"اقتراح للمراجعة","neutral");
    addStage(item.can_approve===true || item.can_execute===true?
      "مراجعة تحريرية مثبتة":"لا قبول تحريري لهذه المسودة","hold");
    addStage(item.state==="DRAFT"?"ينتظر قرار المالك":
      item.state==="EXECUTED"?"قرار بشري سابق وتنفيذ داخلي":
      item.state==="REJECTED"?"رفضه المالك":item.state,
      item.state==="EXECUTED"?"verified":"neutral");
    info.append(title,states,meta);btn.append(info);
    btn.addEventListener("click",()=>{app.selected=item.draft_id;renderDrafts();feedback("المسودة المختارة: "+item.draft_id+" · الحالة: "+item.state,false);});
    root.append(btn);
  });
  const chosen=app.rows.find(r=>r.draft_id===app.selected);
  const isEditorialHold=Boolean(chosen&&chosen.state==="DRAFT"&&!chosen.can_approve);
  if(isEditorialHold){
    const banner=document.createElement("p");
    banner.className="operator-audit-integrity";
    banner.style.color="#f0b78b";
    banner.textContent="HOLD تحريري: المسودة المختارة لم تحصل على قبول متطابق للمصدر وتشغيل النموذج وإصدار معيار الجودة ومراجعة المالك. يمكن رفضها؛ لا اعتماد أو تنفيذ قبل إكمال المراجعة.";
    root.prepend(banner);
  }
  by("operator-approve").disabled=app.role!=="OWNER"||!chosen||chosen.can_approve!==true;
  by("operator-reject").disabled=app.role!=="OWNER"||!chosen||chosen.state!=="DRAFT";
  by("operator-execute").disabled=app.role!=="OWNER"||!chosen||chosen.can_execute!==true;
 }
 function renderAudit(audit,integrity){
  const root=by("operator-audit");root.replaceChildren();
  const hdr=document.createElement("p");hdr.className="operator-audit-integrity";
  hdr.textContent=integrity==="CHAIN_VERIFIED"?"سلسلة التدقيق سليمة":"تعذر إثبات سلامة سجل التدقيق";
  root.append(hdr);
  if(!audit.length){const p=document.createElement("p");p.textContent="السجل فارغ لهذا المستخدم.";root.append(p);}
  audit.forEach(e=>{
    const row=document.createElement("div");row.className="operator-audit-row";
    const event=document.createElement("strong");event.textContent=e.event;
    const meta=document.createElement("small");
    meta.textContent=e.actor+" · "+new Intl.DateTimeFormat("ar-EG",{timeZone:"Africa/Cairo",dateStyle:"short",timeStyle:"medium"}).format(new Date(e.timestamp));
    row.append(event,meta);root.append(row);
  });
 }
 accountButton.addEventListener("click",()=>app.actor?goToMyDecisions():showLogin());
 by("operator-show-login").addEventListener("click",showLogin);
 by("login-close").addEventListener("click",()=>dialog.close());
 dialog.addEventListener("close",()=>{
   by("operator-password").value="";
   by("login-reveal-password").checked=false;
   by("operator-password").type="password";
   announceLogin("");
 });
 by("login-reveal-password").addEventListener("change",()=>{
   by("operator-password").type=by("login-reveal-password").checked?"text":"password";
 });
 by("operator-login").addEventListener("submit",async e=>{
   e.preventDefault();
   if(app.busy)return;
   const submit=by("login-submit");app.busy=true;submit.disabled=true;
   submit.textContent="جارٍ التحقق من بياناتك…";
   announceLogin("");
   try{
     await post("/api/operator/login",{
       login:by("operator-username").value.trim(),
       password:by("operator-password").value
     });
     const confirmed=await getState();
     if(!confirmed)throw new Error("تعذر إثبات جلسة الدخول. جرّب مجددًا.");
     dialog.close();
     feedback("تم تسجيل الدخول. قراراتك ومسوداتك ظاهرة هنا.",true);
     goToMyDecisions();
   }catch(error){
     announceLogin(error.message,true);
     by("operator-password").focus();
   }finally{
     by("operator-password").value="";
     submit.disabled=false;submit.textContent="الدخول إلى مساحة قراراتي";app.busy=false;
   }
 });
 async function signOut(){
   if(app.busy)return;
   try{
     await post("/api/operator/logout",{});
     loggedOut();
     if(dialog.open)dialog.close();
     feedback("تم تسجيل الخروج بأمان.",true);
   }catch(e){feedback("تعذر تأكيد تسجيل الخروج. لم نفترض إنهاء الجلسة.");}
 }
 // Independent owner editorial signoff, not the final approval of a draft.
 window.addEventListener("maal:benchmark-review-selected",e=>{
   const item=e.detail||{};
   if(!/^maal-paired-[0-9a-f]{32}$/.test(item.run_id||""))return;
   by("operator-editorial-review").hidden=false;
   by("operator-editorial-run").value=item.run_id;
   by("operator-editorial-summary").textContent=
     "تشغيل "+item.run_id+" · "+item.model+" · دليل "+item.evidence_id+
     " · نتيجة آلية "+item.score.score+"/"+item.score.max_score+
     ". راجع الوقائع والمخاطر والبدائل وعقد المهمة بنفسك قبل الإقرار بصلاحيتها.";
 });
 by("operator-editorial-sign").addEventListener("click",async()=>{
   if(app.role!=="OWNER"){feedback("يجب تسجيل دخول حساب المالك لإتمام المراجعة التحريرية.");return;}
   const runId=by("operator-editorial-run").value;
   const password=by("operator-editorial-password").value;
   if(!runId||!password){feedback("حدّد تشغيلًا مؤهلًا وأدخل كلمة مرور المالك أولًا.");return;}
   if(!window.confirm("هل راجعت حقائق المصدر وصلة الأعمال وشروط الأثر والمخرج المطلوب، وترى أن هذه التوصية صالحة للمراجعة كمسودة مستقلة؟ لن تُعتمد المهمة بهذا الإجراء."))return;
   by("operator-editorial-password").value="";
   try{
      const r=await post("/api/operator/editorial-signoff",
         {model_run_id:runId,stepup_password:password});
      by("operator-description").value=r.task_description;
      by("operator-description").dataset.modelRunId=runId;
      by("operator-description").dataset.newEvidenceId=r.evidence_id;
      feedback("تم تسجيل مراجعة المالك التحريرية. يمكنك الآن إنشاء مسودة جديدة، ثم اتخاذ قرار مستقل بالاعتماد أو الرفض.",true);
      by("operator-description").focus();
   }catch(error){feedback(error.message);}
 });
 by("operator-logout").addEventListener("click",signOut);
 headerLogout.addEventListener("click",signOut);
 by("operator-description").addEventListener("input",()=>{ delete by("operator-description").dataset.modelRunId; delete by("operator-description").dataset.newEvidenceId; });
 by("operator-create").addEventListener("click",async()=>{
  const description=by("operator-description").value.trim();
  if(description.length<8){feedback("اكتب وصفًا للمهمة التجريبية أولًا.");return;}
  try{
   const linkedRun=by("operator-description").dataset.modelRunId||null;
   const newEvidenceId=by("operator-description").dataset.newEvidenceId||null;
   const data=await post("/api/operator/draft",{
      description,idempotency_key:crypto.randomUUID()+"|"+Date.now(),model_run_id:linkedRun,new_evidence_id:newEvidenceId});
   app.selected=data.draft_id;by("operator-description").value="";
   delete by("operator-description").dataset.modelRunId;
   delete by("operator-description").dataset.newEvidenceId;
   feedback("تم إنشاء مسودة مرتبطة بالدليل الموثّق فقط.",true);
   await getState();
  }catch(e){feedback(e.message);}
 });
 by("operator-approve").addEventListener("click",async()=>{
  if(!app.selected)return;
  if(!by("operator-stepup").value){feedback("أعد إدخال كلمة المرور لتسجيل موافقتك.");return;}
  const secret=by("operator-stepup").value;
  by("operator-stepup").value="";
  try{
   const data=await post("/api/operator/approve",{
      draft_id:app.selected,stepup_password:secret});
   feedback("تم توثيق موافقة حساب الاختبار "+data.approved_by+" داخل بيئة E.",true);
   await getState();
  }catch(e){feedback(e.message);}
 });
 by("operator-reject").addEventListener("click",async()=>{
  if(!app.selected)return;
  const choice=app.rows.find(r=>r.draft_id===app.selected);
  if(!choice||choice.state!=="DRAFT")return;
  if(!by("operator-stepup").value){
    feedback("أدخل كلمة مرور المالك لتأكيد رفض المسودة.");return;
  }
  if(!window.confirm("هل تؤكد رفض المسودة المحددة؟ سيتم تسجيل قرار الرفض ولا تنشأ أي مهمة."))
    return;
  const secret=by("operator-stepup").value;
  by("operator-stepup").value="";
  try{
    const data=await post("/api/operator/reject",{
      draft_id:app.selected,stepup_password:secret,reason:"EDITORIAL_NOT_ACCEPTED"});
    feedback("تم تسجيل رفض بشري موثق للمسودة، دون تنفيذ أي مهمة. · "+data.state,true);
    await getState();
  }catch(e){feedback(e.message);}
 });
 by("operator-execute").addEventListener("click",async()=>{
  if(!app.selected)return;
  try{
   const data=await post("/api/operator/execute",{draft_id:app.selected});
   feedback("النتيجة المثبتة: "+data.state+" · معرف المهمة: "+data.task_id,true);
   await getState();
  }catch(e){feedback(e.message);}
 });
 loggedOut();
 loadGuestPreview();
 getState();
});
