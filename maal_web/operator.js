"use strict";
/* MA'AL Gate F operator lab; intentionally test-only and authenticated.
   This browser never receives owner challenge secrets or raw SQLite files. */
document.addEventListener("DOMContentLoaded", () => {
 const by=id=>document.getElementById(id);
 const app={csrf:"", selected:null,rows:[],actor:null,busy:false};
 const feedback=(message,ok=false)=>{let el=by("operator-feedback");el.textContent=message;el.dataset.ok=String(ok);};
 async function getState(){
  try{
   const r=await fetch("/api/operator/state",{cache:"no-store",credentials:"same-origin"});
   if(!r.ok){loggedOut();return;}
   const data=await r.json();
   app.csrf=data.csrf;app.actor=data.operator;app.rows=data.drafts;
   by("operator-login").hidden=true;by("operator-authenticated").hidden=false;
   by("operator-whoami").textContent="مستخدم: "+data.operator+" · بيئة: "+data.tenant+" · "+data.role;
   renderDrafts();renderAudit(data.audit,data.audit_integrity);
  }catch(e){feedback("تعذّر الاتصال بمخزن المهام التجريبي.");}
 }
 function loggedOut(){
   app.csrf="";app.actor=null;app.selected=null;app.rows=[];
   by("operator-login").hidden=false;by("operator-authenticated").hidden=true;
   by("operator-password").value="";by("operator-stepup").value="";
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
    btn.classList.toggle("chosen",app.selected===item.draft_id);
    btn.setAttribute("aria-pressed",String(app.selected===item.draft_id));
    btn.append(svgSvg());
    const info=document.createElement("span");info.className="operator-draft-info";
    const title=document.createElement("strong");title.textContent=item.description;
    const meta=document.createElement("small");
    meta.textContent="الحالة: "+item.state+" · دليل: "+item.evidence_id+(item.approved_by?" · المعتمد: "+item.approved_by:"");
    info.append(title,meta);btn.append(info);
    btn.addEventListener("click",()=>{app.selected=item.draft_id;renderDrafts();});
    root.append(btn);
  });
  const chosen=app.rows.find(r=>r.draft_id===app.selected);
  by("operator-approve").disabled=!chosen||chosen.state!=="DRAFT";
  by("operator-execute").disabled=!chosen||!["APPROVED","EXECUTED"].includes(chosen.state);
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
 by("operator-login").addEventListener("submit",async e=>{
  e.preventDefault();
  try {
   await post("/api/operator/login",{login:by("operator-username").value.trim(),
                                     password:by("operator-password").value});
   feedback("تمت المصادقة مع حساب الاختبار.",true);
   await getState();
  }catch(e){feedback(e.message);}
  finally{by("operator-password").value="";}
 });
 by("operator-logout").addEventListener("click",async()=>{
  try{await post("/api/operator/logout",{});loggedOut();feedback("تم تسجيل الخروج.",true);}
  catch(e){feedback(e.message);}
 });
 by("operator-create").addEventListener("click",async()=>{
  const description=by("operator-description").value.trim();
  if(description.length<8){feedback("اكتب وصفًا للمهمة التجريبية أولًا.");return;}
  try{
   const data=await post("/api/operator/draft",{
      description,idempotency_key:crypto.randomUUID()+"|"+Date.now()});
   app.selected=data.draft_id;by("operator-description").value="";
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
 by("operator-execute").addEventListener("click",async()=>{
  if(!app.selected)return;
  try{
   const data=await post("/api/operator/execute",{draft_id:app.selected});
   feedback("النتيجة المثبتة: "+data.state+" · معرف المهمة: "+data.task_id,true);
   await getState();
  }catch(e){feedback(e.message);}
 });
 loggedOut();
 getState();
});
