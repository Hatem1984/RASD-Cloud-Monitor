"use strict";
/* A genuine human-operated comparable-task timer, never a synthetic ROI. */
document.addEventListener("DOMContentLoaded",()=>{
 const by=id=>document.getElementById(id);
 const state=by("value-benchmark-state");
 if(!state)return;
 const manual={start:null,end:null,note:null,elapsed_seconds:null};
 const agent={start:null,end:null,note:null,elapsed_seconds:null};
 const btn={
  manualStart:by("value-manual-start"),manualStop:by("value-manual-stop"),
  agentStart:by("value-agent-start"),agentStop:by("value-agent-stop"),
  save:by("value-benchmark-download")
 };
 const now=()=>performance.now();
 let interrupted=false;
 const announce=(msg)=>{state.textContent=msg;};
 const summarize=()=>{
  if(manual.elapsed_seconds!==null&&agent.elapsed_seconds!==null){
   announce("اليدوي: "+manual.elapsed_seconds+" ثانية؛ مَآل: "+agent.elapsed_seconds+
     " ثانية. دي عينة بشرية واحدة بمراجعة ذاتية، وليست عائد استثمار مثبتًا.");
  }
 };
 btn.manualStart.addEventListener("click",()=>{
  if(manual.start!==null)return;
  manual.start=now();
  btn.manualStart.disabled=true;btn.manualStop.disabled=false;
  announce("المسار اليدوي بدأ. ابحث، تحقق من الصفحة الرسمية، ثم اكتب القرار والسبب.");
 });
 btn.manualStop.addEventListener("click",()=>{
  const note=by("value-manual-note").value.trim();
  if(note.length<25){
   announce("لازم تسجل القرار ورابط المصدر وسبب القرار قبل إنهاء المسار اليدوي.");return;
  }
  manual.end=now();manual.note=note;
  manual.elapsed_seconds=Math.round((manual.end-manual.start)/10)/100;
  btn.manualStop.disabled=true;btn.agentStart.disabled=false;
  announce("المسار اليدوي اكتمل في "+manual.elapsed_seconds+" ثانية. ابدأ الآن المسار باستخدام مَآل لنفس المهمة.");
 });
 btn.agentStart.addEventListener("click",()=>{
  if(agent.start!==null)return;
  agent.start=now();btn.agentStart.disabled=true;btn.agentStop.disabled=false;
  announce("بدأ توقيت استخدام مَآل. افحص الدليل والتحليل واكتب قرارك وأخطاءك.");
 });
 btn.agentStop.addEventListener("click",()=>{
  const note=by("value-agent-note").value.trim();
  if(note.length<25){
   announce("سجّل القرار وأخطاء أو حدود مَآل قبل إنهاء القياس.");return;
  }
  agent.end=now();agent.note=note;
  agent.elapsed_seconds=Math.round((agent.end-agent.start)/10)/100;
  btn.agentStop.disabled=true;btn.save.disabled=false;summarize();
 });
 btn.save.addEventListener("click",()=>{
  if(manual.elapsed_seconds===null||agent.elapsed_seconds===null)return;
  const receipt={
    schema:"MAAL_SELF_OPERATED_MANUAL_VS_AGENT_V1",
    task:"Evaluate published FPT Cairo expansion for a synthetic Egyptian digital SME; verify original publisher and propose internal follow-up.",
    date:new Date().toISOString(),
    manually_operated:true,
    sample_size:1,
    manual:{elapsed_seconds:manual.elapsed_seconds,narrative:manual.note},
    agent:{elapsed_seconds:agent.elapsed_seconds,narrative:agent.note},
    model_replay_warning:"Cached prior real Qwen receipt; model generation not included unless a live inference was operated within the timed interval.",
    human_judged_quality_not_independently_verified:true,
    roi_not_measured:true,
    external_action:false,
    passwords_collected:false
  };
  const blob=new Blob([JSON.stringify(receipt,null,2)],{type:"application/json"});
  const url=URL.createObjectURL(blob);
  const a=document.createElement("a");
  a.href=url;a.download="MAAL_Human_Timing_Single_Case.json";
  document.body.append(a);a.click();a.remove();
  URL.revokeObjectURL(url);
 });
 window.addEventListener("beforeunload",()=>{
  interrupted=manual.start!==null&&agent.end===null;
 });
});
