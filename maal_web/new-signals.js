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
    if(text!==undefined && text!==null)el.textContent=String(text);
    if(cls)el.className=cls;
    return el;
  };
  const disclosure=(label)=>{
    const details=node("details",null,"new-signal-section premium-disclosure");
    details.open=label.startsWith("01") || label.startsWith("HOLD") ||
      label.startsWith("05");
    details.append(node("summary",label));
    return details;
  };
  const displayValue=(parent,label,value)=>{
    const wrapper=disclosure(label);
    wrapper.append(node("p",value||"غير مثبت"));
    parent.append(wrapper);
  };
  const list=(parent,label,values)=>{
    const group=disclosure(label);
    const ul=node("ul");for(const v of values||[]){ul.append(node("li",v));}
    group.append(ul);parent.append(group);
  };
  const readableDate=value=>{if(!value)return "غير مثبت";const time=new Date(value);
    return Number.isNaN(+time)?"غير مثبت":new Intl.DateTimeFormat("ar-EG",{
      timeZone:"Africa/Cairo",year:"numeric",month:"long",day:"numeric"
    }).format(time)};
  const choose=item=>{
    current=item;
    choices.querySelectorAll("button").forEach(btn=>{
      btn.setAttribute("aria-pressed",String(btn.dataset.evidence===item.case.evidence_id));
    });
    const c=item.case;const a=item.ai;
    evidence.replaceChildren();evidence.hidden=false;
    const meta=node("div",null,"premium-source-fields");
    const metadata=[
       ["الناشر",c.publisher||"غير مثبت"],
       ["تاريخ النشر",readableDate(c.published_day)],
       ["تاريخ الالتقاط",readableDate(c.observed_at)],
       ["حالة المصدر","دليل ناشر أصلي محفوظ، وليس إشارة حية"],
    ];
    for(const [label,value] of metadata){
      const item=node("div",null,"premium-source-field");
      item.append(node("strong",label),node("span",value));meta.append(item);
    }
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
    if(item.editorial_review?.status!=="APPROVED"){
      displayValue(analysis,"سبب عدم قبول القرار",
        "الخبر موثق، لكن توصية الذكاء الاصطناعي لم تجتز المراجعة التحريرية. "+
        "قد لا تكون مناسبة للشركة الافتراضية أو لا توضح صلة الحدث بها، لذلك لا يمكن اعتمادها بعد.");
    }
    displayValue(analysis,"استدلال Qwen3 حقيقي محفوظ سابقًا (ليس بثًا مباشرًا)",a.run_id+" · "+a.model+
      " · "+a.elapsed_seconds+" ثانية");
    list(analysis,"01 · الوقائع المثبتة من المصدر",x.facts);
    list(analysis,"03 · افتراضات وشروط الأثر غير المثبتة",x.assumptions);
    displayValue(analysis,"02 · صلة الحدث بالشركة وأثره المحتمل",x.business_impact);
    list(analysis,"04 · خيارات القرار",x.decision_options);
    list(analysis,"مجهولات تؤثر في القرار",x.unknowns);
    displayValue(analysis,"05 · توصية AI — غير معتمدة تحريرياً",x.recommendation);
    displayValue(analysis,"06 · عقد الإجراء وحدود التنفيذ",
      item.owner_draft?
      "توجد مسودة قرار مرتبطة؛ حالتها "+item.owner_draft.state+
      ". لا تعني اعتمادًا جديدًا، ولا يجوز التنفيذ دون المراجعة والموافقة البشرية.":
      "لا يوجد عقد إجراء مقبول لهذه الحالة. تفاصيل التنفيذ معلقة على استدلال مناسب ومراجعة مستقلة.");
    const editorial=item.editorial_review||{status:"HOLD",reason:"لا توجد مراجعة تحريرية مثبتة"};
    if(editorial.status!=="APPROVED"){
      displayValue(analysis,"HOLD تحريري — لا يجوز الاعتماد أو التنفيذ",
        editorial.reason||"اجتياز عقد JSON ليس اعتمادًا لمحتوى التوصية");
      action.hidden=!item.owner_draft;
      action.textContent="افتح مسودة المالك للمراجعة أو الرفض";
      if(item.owner_draft){
        displayValue(analysis,"تنبيه", "المسودة الموجودة محفوظة كما هي؛ اعتمادها محجوب إلى حين مراجعة تحليل مستقل.");
      }
      return;
    }
    action.hidden=false;
    action.textContent=item.owner_draft ?
       "افتح المسودة "+item.owner_draft.state+" للمراجعة" :
       "جهّز مسودة قرار جديدة للمراجعة البشرية";
    if(item.owner_draft){
      displayValue(analysis,"حالة قرار المالك المرتبط",
        item.owner_draft.state+" · "+item.owner_draft.draft_id+
        (item.owner_draft.task_id?" · مهمة "+item.owner_draft.task_id:" · لم تُنفّذ مهمة بعد"));
    }
  };
  async function load(){
    try{
      let response=null;
      for(let attempt=0;attempt<3;attempt++){
        try{
          response=await fetch("/api/new-signals",{cache:"no-store",credentials:"same-origin"});
          if(response.ok)break;
        }catch(_){response=null;}
        if(attempt<2)await new Promise(resolve=>setTimeout(resolve,(attempt+1)*650));
      }
      if(!response || !response.ok)throw new Error("تعذر تحميل أدلة المصادر المقبولة");
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
        const b=node("button",null,"new-signal-choice");
        const heading=node("strong",item.case.headline);
        const when=node("small",item.case.publisher+" · "+
          readableDate(item.case.published_day)+" · مصدر تاريخي محفوظ");
        const badge=node("span",item.editorial_review?.status==="APPROVED"?
            "VERIFIED · REVIEWED":"VERIFIED SOURCE · EDITORIAL HOLD","premium-pill");
        badge.dataset.tone=item.editorial_review?.status==="APPROVED"?"verified":"hold";
        b.append(heading,when,badge);
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
        " استجابة اجتازت فحص نموذج آلي · "+
        data.items.filter(x=>x.editorial_review?.status==="APPROVED").length+
        " قبولات تحريرية مثبتة · لا موافقات آلية";
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
    const existing=current.owner_draft;
    if(existing){
      document.querySelector('.nav-link[data-view="decisions"]')?.click();
      const advanced=by("advanced-operator-review");if(advanced)advanced.open=true;
      const old=Array.from(document.querySelectorAll(".operator-draft-item"))
        .find(b=>b.dataset.draftId===existing.draft_id);
      if(old)old.click();
      by("operator-lab")?.scrollIntoView({block:"start",behavior:"smooth"});
      if(by("header-logout")?.hidden)by("account-entry")?.click();
      return;
    }
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
  window.addEventListener("maal:auth-changed",load);
});
