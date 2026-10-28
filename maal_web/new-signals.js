"use strict";
/* New real-source capture is displayed in the EXISTING MA'AL V0.3 page.
   No owner approval, task creation or model invocation from guest view. */
document.addEventListener("DOMContentLoaded",()=>{
  const by=id=>document.getElementById(id);
  const status=by("new-signal-state"),choices=by("new-signal-choices");
  const evidence=by("new-signal-evidence"),analysis=by("new-signal-analysis");
  const action=by("new-signal-draft");
  if(!status||!choices||!evidence||!analysis||!action)return;
  let current=null;
  const node=(tag,text,cls)=>{
    const el=document.createElement(tag);
    if(text!==undefined)el.textContent=String(text);
    if(cls)el.className=cls;
    return el;
  };
  const displayValue=(parent,label,value)=>{
    const wrapper=node("div",null,"new-signal-section");
    wrapper.append(node("strong",label),node("p",value||"غير مثبت"));
    parent.append(wrapper);
  };
  const list=(parent,label,values)=>{
    const group=node("div",null,"new-signal-section");
    group.append(node("strong",label));
    const ul=node("ul");for(const v of values||[]){ul.append(node("li",v));}
    group.append(ul);parent.append(group);
  };
  const choose=item=>{
    current=item;
    choices.querySelectorAll("button").forEach(btn=>{
      btn.setAttribute("aria-pressed",String(btn.dataset.evidence===item.case.evidence_id));
    });
    const c=item.case;const a=item.ai;
    evidence.replaceChildren();evidence.hidden=false;
    const meta=node("p",c.publisher+" | "+(c.published_day||"تاريخ النشر غير مثبت")+
       " | دليل: "+c.evidence_id,"new-signal-meta");
    const title=node("h3",c.headline);
    const image=document.createElement("img");
    image.src=c.evidence_image_url;image.alt="لقطة صفحة الناشر الأصلية: "+c.headline;
    image.loading="lazy";image.className="new-signal-proof";
    const origin=node("a","الصفحة الرسمية الأصلية","btn btn-secondary");
    origin.href=c.original_url;origin.target="_blank";origin.rel="noopener noreferrer";
    const digest=node("small","SHA-256: "+c.evidence_digest);
    evidence.append(title,meta,image,origin,digest);
    analysis.replaceChildren();
    action.hidden=true;
    if(!a){
      displayValue(analysis,"تحليل Qwen3","معلّق؛ دليل الناشر مقبول لكن النموذج لم يكمل استدلالًا موثقًا بعد.");
      return;
    }
    if(a.status!=="EVIDENCE_GROUNDED_GENERATIVE_DRAFT" || !a.analysis){
      displayValue(analysis,"HOLD — تحليل غير مقبول",a.error||"فشل التحقق من الاستدلال أو المصدر.");
      return;
    }
    const x=a.analysis;
    displayValue(analysis,"تشغيل AI الحقيقي",a.run_id+" · "+a.model+
      " · "+a.elapsed_seconds+" ثانية");
    list(analysis,"حقائق مقتبسة من صفحة المصدر",x.facts);
    list(analysis,"افتراضات لا يجوز اعتبارها حقائق",x.assumptions);
    displayValue(analysis,"الأثر المحتمل على الشركة الافتراضية",x.business_impact);
    list(analysis,"خيارات القرار",x.decision_options);
    list(analysis,"ما لا يزال مجهولًا",x.unknowns);
    displayValue(analysis,"توصية النموذج — تنتظر المالك",x.recommendation);
    action.hidden=false;
  };
  async function load(){
    try{
      const response=await fetch("/api/new-signals",{cache:"no-store",credentials:"same-origin"});
      if(!response.ok)throw new Error("تعذر تحميل أدلة المصادر المقبولة");
      const data=await response.json();
      if(data.schema!=="MAAL_NEW_OFFICIAL_SIGNALS_V1" ||
         data.live_schedule!==false || data.approval_requires_human!==true){
        throw new Error("تعذر إثبات حدود صلاحية الوكيل");
      }
      choices.replaceChildren();
      if(!data.items.length){
        status.textContent="لا يوجد مصدر جديد مقبول بعد؛ لا قرار قابل للتجهيز.";
        return;
      }
      for(const item of data.items){
        const b=node("button",item.case.headline,"new-signal-choice");
        b.type="button";b.dataset.evidence=item.case.evidence_id;
        b.setAttribute("aria-pressed","false");
        b.title=item.case.publisher+" · "+(item.case.published_day||"غير مؤرخ")+
          " · "+(item.ai?.status||"تحليل معلّق");
        b.addEventListener("click",()=>choose(item));
        choices.append(b);
      }
      status.textContent=data.items.length+
        " صفحات ناشرين أصلية محفوظة · "+
        data.items.filter(x=>x.ai?.status==="EVIDENCE_GROUNDED_GENERATIVE_DRAFT").length+
        " تحليل مقبول من Qwen3 · لا موافقات آلية";
      choose(data.items.find(x=>x.case.source_key==="fpt")||
             data.items.find(x=>x.ai?.status==="EVIDENCE_GROUNDED_GENERATIVE_DRAFT")||
             data.items[0]);
    }catch(e){
      status.textContent="HOLD — "+e.message;choices.replaceChildren();
      action.hidden=true;current=null;
    }
  }
  action.addEventListener("click",()=>{
    if(!current?.ai?.analysis || current.ai.status!=="EVIDENCE_GROUNDED_GENERATIVE_DRAFT")return;
    const recommendation=current.ai.analysis.recommendation;
    const field=by("operator-description");
    field.value=recommendation;
    field.dataset.modelRunId=current.ai.run_id;
    field.dataset.newEvidenceId=current.case.evidence_id;
    document.querySelector('.nav-link[data-view="decisions"]')?.click();
    const details=by("advanced-operator-review");
    if(details)details.open=true;
    by("operator-lab")?.scrollIntoView({block:"start",behavior:"smooth"});
    if(by("header-logout")?.hidden){
      by("account-entry")?.click();
    } else {
      field.focus();
    }
  });
  load();
});
