"use strict";
/* One existing V0.3 page, one read-only verified source/model/owner journey.
   The browser cannot approve a draft or execute an action through this widget. */
document.addEventListener("DOMContentLoaded", () => {
  const by = (id) => document.getElementById(id);
  const root = by("agent-journey-steps");
  const status = by("agent-journey-status");
  const details = by("agent-journey-details");
  if (!root || !status || !details) return;
  let lastIdentity = "";

  function row(label, value) {
    const box = document.createElement("div");
    box.className = "customer-answer";
    const title = document.createElement("strong");
    title.textContent = label;
    const text = document.createElement("p");
    text.textContent = String(value);
    box.append(title, text);
    return box;
  }

  async function refresh() {
    try {
      const response = await fetch("/api/agent-journey", {
        credentials: "same-origin", cache: "no-store"
      });
      if (!response.ok) throw new Error("لم تكتمل مطابقة الدليل والتحليل");
      const data = await response.json();
      if (data.schema !== "MAAL_COMPETITION_JOURNEY_V1" ||
          data.live_signal !== false || data.company_is_synthetic !== true ||
          data.evidence.status !== "VERIFIED_ORIGINAL_PAGE" ||
          data.ai.human_review !== "NOT_APPROVED_BY_MODEL" ||
          data.operations.external_actions !== false) {
        throw new Error("عقد بيانات الوكيل غير آمن");
      }
      const decision = data.approval.drafts.find(x=>x.state==="DRAFT") ||
                       data.approval.drafts[0];
      const identity = [data.ai.run_id, data.approval.authenticated,
        ...data.approval.drafts.map(x=>x.draft_id+":"+x.state)].join("|");
      if (identity === lastIdentity) return;
      lastIdentity = identity;
      root.replaceChildren();
      root.append(
        row("1 · الإشارة والدليل", data.evidence.publisher+" — "+
            data.evidence.published_day+" — صورة أصلية مقبولة SHA-256"),
        row("2 · تحليل الذكاء الاصطناعي", data.ai.model+" · "+
            data.ai.run_id+" · نتيجة محفوظة "+data.ai.recorded_at),
        row("3 · أثر على نشاط الشركة الافتراضية", data.ai.impact),
        row("4 · التوصية غير المعتمدة", data.ai.recommendation),
        row("5 · قرار المالك", !data.approval.authenticated ?
            "يلزم دخول حساب المالك لرؤية المسودة وسجلها" :
            decision ? decision.state+" · "+decision.draft_id :
            "لا توجد مسودة مرئية مرتبطة بالدليل"),
        row("6 · التنفيذ الداخلي", data.approval.authenticated &&
            data.approval.drafts.some(x=>x.task_id) ?
            "توجد مهمة داخلية موثقة في سجل المالك" :
            "لم يثبت تنفيذ مهمة داخلية في هذه الجلسة")
      );
      const approvedBundle = data.report.ai_run_bound_word_pdf_available === true;
      by("agent-report-word").hidden = !approvedBundle;
      by("agent-report-pdf").hidden = !approvedBundle;
      const modelAge = "الاستدلال محفوظ منذ "+data.ai.recorded_at+
          "، وليس استدلالًا جديدًا عند فتح الصفحة.";
      details.textContent = modelAge+
          " الدليل: "+data.evidence.headline+
          (approvedBundle ?
            ". التقرير بصيغتي Word/PDF مرتبط بنفس بصمة المصدر ومعرّف النموذج، ويظل مسودة للمراجعة." :
            ". ملف Word الأساسي يثبت صورة المصدر التاريخية، وتقرير AI الموحد لم يُعتمد بعد.");
      status.textContent = "الدليل والتحليل متطابقان · "+
          (data.approval.authenticated ? "حالة المراجعة مُحمّلة من سجل المالك" :
           "عرض آمن؛ اعتماد المالك غير متحقق")+
          " · لا إرسال خارجي";
    } catch (err) {
      lastIdentity = "";
      root.replaceChildren();
      status.textContent = "HOLD — "+err.message+". لا توجد موافقة أو نتيجة تنفيذ مفترضة.";
      details.textContent = "تعذّر إثبات تسلسل الدليل ← النموذج ← القرار. لا يمكن اعتبار العرض مقبولًا.";
    }
  }
  by("agent-journey-review").addEventListener("click", () => {
    const navigation = document.querySelector('.nav-link[data-view="decisions"]');
    if (navigation) navigation.click();
    const advanced = by("advanced-operator-review");
    if (advanced) advanced.open = true;
    const lab = by("operator-lab");
    if (lab) lab.scrollIntoView({block:"start",behavior:"smooth"});
  });
  refresh();
  window.addEventListener("maal:auth-changed", refresh);
  // Single source of truth from the current local server. No fake freshness.
  setInterval(refresh,12000);
});
