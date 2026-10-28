"use strict";
document.addEventListener("DOMContentLoaded",()=>{
 const $=id=>document.getElementById(id),root=$("paired-benchmark-list"),out=$("paired-benchmark-detail"),status=$("paired-benchmark-state");
 if(!root||!out)return;
 const el=(tag,value)=>{let n=document.createElement(tag);n.textContent=value||"";return n;};
 const add=(label,value)=>{let n=el("div");n.className="new-signal-section";n.append(el("strong",label),el("p",String(value||"غير محدد")));out.append(n)};
 function show(entry){
   out.replaceChildren();
   out.append(el("h4",entry.model+" · "+entry.case+" · تعليمات "+(entry.prompt_version||"V2")+" · "+entry.duration_seconds+" ثانية"));
   out.append(el("p","تقييم آلي: "+entry.grade.score+"/"+entry.grade.max_score+
     " · "+entry.grade.status+" · القبول التحريري البشري: لم يتم"));
   for(const [name,score] of Object.entries(entry.grade.dimensions))add(name,score+"/2");
   const a=entry.response_json;
   if(a&&a.recommendation){
     add("الوقائع",a.facts.join(" | "));
     add("صلة الأعمال",a.business_relevance.causal_link);
     add("شروط الأثر",a.impact_conditions.join(" | "));
     add("البدائل",a.alternatives.map(x=>x.action+" — "+x.tradeoff).join(" | "));
     add("سبب القرار",a.recommendation.why);
     add("الخطوة الداخلية المقترحة",a.recommendation.bounded_internal_step);
     add("عقد المهمة",a.action_contract.title+" — "+a.action_contract.deliverable);
     add("المسؤول والأولوية",a.action_contract.owner_role+" — "+a.action_contract.priority);
     add("معيار الإتمام",a.action_contract.completion_criteria);
     add("المجهولات",a.unknowns.join(" | "));
   }
   if(entry.grade.status==="CANDIDATE_FOR_EDITORIAL"){
     const b=el("button","افتح المراجعة التحريرية البشرية");
     b.type="button";b.className="btn btn-primary";
     b.addEventListener("click",()=>{
       document.querySelector('.nav-link[data-view="decisions"]')?.click();
       $("advanced-operator-review").open=true;
       window.dispatchEvent(new CustomEvent("maal:benchmark-review-selected",{detail:{
         run_id:entry.run_id,model:entry.model,evidence_id:entry.source_id,
         analysis:a,score:entry.grade
       }}));
       $("operator-editorial-review")?.scrollIntoView({block:"center",behavior:"smooth"});
       if($("header-logout")?.hidden)$("account-entry")?.click();
     });
     out.append(b);
   } else add("HOLD","لا توجد توصية صالحة لتفعيل مهمة جديدة من هذا التشغيل.");
 }
 fetch("/api/model-comparison",{credentials:"same-origin",cache:"no-store"})
 .then(r=>{if(!r.ok)throw Error("benchmark unavailable");return r.json()})
 .then(data=>{
   if(data.schema!=="MAAL_INDEPENDENT_MODEL_BENCHMARK_V2")throw Error("benchmark schema mismatch");
   root.replaceChildren();
   status.textContent=data.items.length+" تشغيلات حقيقية محفوظة · لا اعتماد تحريري تلقائي.";
   for(const r of data.items){
     const b=el("button",r.case+" · "+r.model+" · "+r.grade.score+"/"+
       r.grade.max_score+" — "+r.grade.status);
     b.type="button";b.className="new-signal-choice";
     b.addEventListener("click",()=>show(r));root.append(b);
   }
   if(data.items.length)show(data.items[0]);
 }).catch(e=>{status.textContent="HOLD — "+e.message;});
});
