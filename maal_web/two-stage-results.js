"use strict";
/* Read-only representation of independent two-stage model runs.
   This page deliberately has NO create/approve/execute controls. */
document.addEventListener("DOMContentLoaded",()=>{
 const by=id=>document.getElementById(id);
 const impact=by("view-impact");if(!impact)return;
 const panel=document.createElement("section");panel.className="premium-panel premium-two-stage";
 const h=document.createElement("h2");h.textContent="جودة تفكير الوكيل — اختبار المرحلتين";
 const intro=document.createElement("p");
 intro.className="premium-muted";
 intro.textContent="التحليل أولًا ثم إعداد مهمة داخلية فقط عندما توجد صلة تجارية قابلة للمراجعة. هذه نتائج محفوظة من تشغيلات محلية، وليست تشغيلًا مباشرًا أو موافقة من المالك.";
 const status=document.createElement("p");status.id="two-stage-status";
 status.setAttribute("role","status");status.textContent="جارٍ فحص سجل التشغيلات المحفوظة…";
 const entries=document.createElement("div");entries.id="two-stage-entries";
 panel.append(h,intro,status,entries);impact.prepend(panel);
 const node=(tag,value)=>{const el=document.createElement(tag);el.textContent=String(value??"");return el};
 const arabicOutcome={ACTION_WORTH_REVIEW:"مرشح لمراجعة إجراء داخلي",
 MONITOR_ONLY:"مراقبة فقط — دون مهمة",
 INSUFFICIENT_EVIDENCE:"الأدلة لا تكفي",
 NOT_RELEVANT:"غير مرتبط بالنشاط",
 ANALYSIS_HOLD:"تحليل معلّق"};
 const verdict={HOLD:"غير مقبول بنيويًا",ABSTAIN_VALID:"امتناع صحيح دون مهمة",
 CANDIDATE_FOR_INDEPENDENT_EDITORIAL:"مرشح لمراجعة تحريرية مستقلة"};
 fetch("/api/two-stage-results",{credentials:"same-origin",cache:"no-store"})
 .then(r=>{if(!r.ok)throw Error("unavailable");return r.json()})
 .then(data=>{
  if(data.schema!=="MAAL_TWO_STAGE_READONLY_RESULTS_V1"||
     data.human_editorial_approved!==false||data.owner_approved!==false||
     data.live_inference_now!==false||data.external_actions!==false)
    throw Error("unverified_source_or_authority");
  entries.replaceChildren();
  if(!data.items.length){
   status.textContent="لم تتوفر تشغيلات فعلية موثقة لهذا المسار حتى الآن. لا توصية جديدة، ولا مسودة قرار.";
   return;
  }
  status.textContent=data.items.length+" تشغيلات محلية محفوظة · "+
   data.invalid_receipts+" سجلات غير صالحة للاستعراض · صفر موافقات تحريرية أو بشرية.";
  for(const item of data.items){
   const box=document.createElement("details");box.className="premium-two-stage-item";
   const summary=node("summary",item.publisher+" · "+arabicOutcome[item.outcome]||"نتيجة غير محددة");
   const stamp=node("p","النموذج "+item.model+" · مدة المرحلتين "+item.total_seconds+
    " ثانية · سجل محفوظ "+item.recorded_at);
   stamp.className="premium-muted";
   const state=node("p","نتيجة الفحص: "+(verdict[item.quality.status]||"تحتاج مراجعة")+
     ". هذه النتيجة ليست قبولًا تحريريًا، ولا تفوّض أي إجراء.");
   const link=node("a","المصدر الرسمي");link.href=item.source_url;
   link.target="_blank";link.rel="noopener noreferrer";link.className="btn btn-secondary";
   box.append(summary,stamp,state,link);
   if(item.stage1_result){
    const q=item.stage1_result;
    const p=node("p","سبب الصلة: "+q.causal_reason+" | المجهولات: "+q.unknowns.join("، "));
    box.append(p);
   }
   if(item.stage2_result){
    const a=item.stage2_result;
    box.append(node("p","المهمة المقترحة للمراجعة فقط: "+a.title+" — "+a.deliverable+
      " | المسؤول المقترح: "+a.owner_role+" | معيار الإنجاز: "+a.completion_criteria));
   }else box.append(node("p","لم يُنشأ عقد مهمة في هذه الحالة."));
   entries.append(box);
  }
 })
 .catch(()=>{status.textContent="تعذر التحقق من سجل المرحلتين؛ لا نعرض توصيات غير مثبتة."});
});
