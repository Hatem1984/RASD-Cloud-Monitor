/* RASD Manual — local-first tenant-isolated Arabic UI. No external calls. */
"use strict";
const $=id=>document.getElementById(id);
const htmlEscape=v=>String(v??"").replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const qs=s=>new URLSearchParams(s).toString();
const fmt=s=>{if(!s)return "—";const d=new Date(s);if(isNaN(d.getTime()))return String(s).slice(0,21);return new Intl.DateTimeFormat("ar-EG",{timeZone:context.tz||"Africa/Cairo",day:"numeric",month:"short",year:"numeric",hour:"2-digit",minute:"2-digit",hour12:false}).format(d);};
const niceState=s=>({approved:"معتمد",pending:"بحاجة لمراجعة",rejected:"مستبعد",running:"جار الفحص",complete:"مكتمل",partial:"جزئي",failed:"فشل"}[s]||s||"—");
const badge=(text,tone)=>'<span class="tag '+(tone||"")+'">'+htmlEscape(text)+'</span>';
const empty=(title,detail)=>'<div class="empty"><div class="symbol">◇</div><h3>'+htmlEscape(title)+'</h3><p>'+htmlEscape(detail)+'</p></div>';
const loading='<div class="loading">جار تحميل البيانات…</div>';
let context={me:null,tid:null,tab:"home",filter:{},csrf:sessionStorage.getItem("rasd_csrf")||"",scanTimer:null,pollingScan:null,pollDismissed:false,mode:"live",tz:"Africa/Cairo",scanFrom:null,scanTo:null,topics:[]};
let timer;
function toast(msg,bad=false){const n=$("notice");n.textContent=msg;n.style.background=bad?"#a3444f":"#1d324f";n.classList.add("show");clearTimeout(timer);timer=setTimeout(()=>n.classList.remove("show"),4500);}
async function api(path,body){const opts={credentials:"same-origin",headers:{}};if(body!==undefined){opts.method="POST";opts.headers["Content-Type"]="application/json";opts.headers["X-RASD-CSRF"]=context.csrf;opts.body=JSON.stringify(body);}const resp=await fetch(path,opts);const data=await resp.json().catch(()=>({error:"استجابة غير مفهومة من الخادم"}));if(!resp.ok)throw new Error(data.error||data.reason||"request_failed");return data;}
function modal(markup){$("dialog-body").innerHTML=markup;$("dialog").classList.remove("hidden");}
function closeModal(){if(context.pollingScan&&$("dialog").dataset.kind==="scan-progress")context.pollDismissed=true;$("dialog").dataset.kind="";$("dialog").classList.add("hidden");$("dialog-body").innerHTML="";}
function currentTenant(){return context.me?.tenants?.find(x=>x.id===context.tid)||null;}
function owner(){return !!context.me?.owner}
function role(){return currentTenant()?.role||"reader"}
function canAdmin(){return owner()||role()==="tenant_admin"}
function canReview(){return canAdmin()||role()==="analyst"}
function rootPath(s=""){return "/api/tenants/"+encodeURIComponent(context.tid)+s}
function setTab(tab,filter={}){context.tab=tab;context.filter=filter;history.replaceState(null,"","#"+tab);document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.tab===tab));document.querySelector(".sidebar").classList.remove("open");$("crumb-tab").textContent=({home:"نظرة عامة",articles:"الأخبار والتغطيات",sources:"المصادر",reports:"التقارير والأرشيف",settings:"الإعدادات"}[tab]||tab);render();}
async function loadMe(){const me=await api("/api/me");context.me=me;const remembered=sessionStorage.getItem("rasd_selected_tenant");context.tid=me.tenants.some(x=>x.id===remembered)?remembered:me.tenants[0]?.id||null;return me;}
function bindShell(){$("account-email").textContent=context.me.email;$("tenant-switch").innerHTML=(context.me.tenants||[]).map(x=>'<option value="'+htmlEscape(x.id)+'">'+htmlEscape(x.name)+'</option>').join("");if(context.tid)$("tenant-switch").value=context.tid;$("current-name").textContent=currentTenant()?.name||"لا توجد جهة بعد";$("tenant-role").textContent="صلاحيتك: "+(owner()?"مالك المنصة":role()==="tenant_admin"?"مدير الجهة":role()==="analyst"?"محلل":"قارئ");
if(context.tid){const current=context.tid;api(rootPath()).then(t=>{if(context.tid!==current)return;context.mode=t.mode||"live";context.tz=t.timezone||"Africa/Cairo";context.topics=t.topics||[];$("tenant-role").textContent+=" · "+(t.mode==="demo"?"عرض تجريبي":"رصد حي");}).catch(()=>{});}
}
async function start(){try{await loadMe();$("login").classList.add("hidden");$("shell").classList.remove("hidden");bindShell();setTab(["home","articles","sources","reports","settings"].includes(location.hash.slice(1))?location.hash.slice(1):"home");}catch(e){$("login").classList.remove("hidden");$("shell").classList.add("hidden");}}
async function render(){if(!context.tid){$("view").innerHTML='<div class="content-header"><div><div class="overline">مرحبًا بك في رصد</div><h1>أنشئ أول جهة</h1><p class="muted">لكل جهة إعداداتها وبياناتها وتقاريرها الخاصة.</p></div></div>'+(owner()?'<button class="primary" data-action="new-tenant">+ إنشاء جهة الآن</button>':empty("لا توجد جهات مرتبطة بحسابك","اطلب من مالك المنصة إضافتك إلى جهة."));return;}
$("view").innerHTML=loading;try{const cfg=await api(rootPath());context.mode=cfg.mode||"live";context.tz=cfg.timezone||"Africa/Cairo";context.topics=cfg.topics||[];if(context.tab==="home")await renderHome();if(context.tab==="articles")await renderArticles();if(context.tab==="sources")await renderSources();if(context.tab==="reports")await renderReports();if(context.tab==="settings")await renderSettings();}
catch(e){$("view").innerHTML=empty("تعذر تحميل القسم","يمكنك إعادة المحاولة. "+e.message)+'<button class="outline" data-action="refresh">إعادة المحاولة</button>';}}
function head(title,desc,actions=""){return '<div class="content-header"><div><div class="overline">مساحة '+htmlEscape(currentTenant()?.name||"")+' · '+badge(context.mode==="demo"?"عرض تجريبي — غير حقيقي":"رصد حي من ناشرين معتمدين",context.mode==="demo"?"demo":"ok")+'</div><h1>'+title+'</h1><p class="muted">'+desc+'</p><p class="mini">الموضوعات: '+htmlEscape((context.topics||[]).join("، ")||"لم تحدد موضوعات بعد")+'</p></div><div class="actions">'+actions+'</div></div>'}
function localDatetime(hoursBefore){const d=new Date(Date.now()-hoursBefore*3600000);const local=new Date(d.getTime()-d.getTimezoneOffset()*60000);return local.toISOString().slice(0,16)}
function scanWindow(){if(!context.scanFrom){if(context.mode==="demo"){context.scanFrom="2026-11-22T00:00";const cap=new Date(Math.min(Date.now(),new Date("2026-11-24T21:59:00Z").getTime()));context.scanTo=new Date(cap.getTime()-cap.getTimezoneOffset()*60000).toISOString().slice(0,16);}else{context.scanFrom=localDatetime(48);context.scanTo=localDatetime(0);}}return '<div class="panel"><div class="panel-title"><h3>نافذة رصد الأخبار الجديدة</h3>'+badge("الفترة حسب تاريخ نشر المادة لا تاريخ اكتشافها","ok")+'</div><div class="form-grid two"><label>من — توقيت جهازك<input type="datetime-local" id="scan-start" value="'+htmlEscape(context.scanFrom)+'"></label><label>إلى — توقيت جهازك<input type="datetime-local" id="scan-end" value="'+htmlEscape(context.scanTo)+'"></label></div><p class="muted">المصادر تعرض حصيلة هذه الفترة فقط. إذا نجح المصدر وظهر صفر، ستعرف كم مادة خارج الفترة أو لم تطابق الموضوع. لا بيانات DEMO بديلة عند الفشل.</p></div>'}
function errorLabel(code){return ({"feed_http_or_redirect_error":"رفض المصدر أو غيّر عنوان موجز RSS","publisher_access_refused":"الناشر رفض الوصول للصفحة","publisher_h1_ambiguous":"عنوان صفحة الناشر غير واضح","publisher_h1_outside_frame":"لم يظهر عنوان الخبر داخل لقطة الصفحة؛ لم تعتمد الصورة","publisher_h1_rss_title_mismatch":"عنوان الصفحة لا يطابق مادة RSS","original_article_image_not_loaded":"الصورة الأصلية لم تكتمل","network_timeout":"انتهت مهلة الاتصال","upstream_network_error":"تعذر الاتصال بالمصدر","publisher_frame_digest_mismatch":"بصمة الصورة لم تتطابق","invalid_scan_window_timezone_order_or_31day_limit":"الفترة غير صالحة؛ الحد الأقصى ٣١ يومًا"}[code]||code||"لم تظهر مواد مطابقة")};
function actionButton(txt,act,primary=false,extra=""){return '<button class="'+(primary?"primary":"outline")+'" data-action="'+act+'" '+extra+'>'+txt+'</button>'}
function onboardingGuide(d,sources){
const items=[
 [context.topics.length>0,"١. موضوع الرصد","اكتب موضوعات الجهة والكلمات التي تريد تضمينها أو استبعادها","settings"],
 [sources.some(x=>x.enabled),"٢. مصادر الأخبار","فعّل مصادر RSS معتمدة تناسب موضوع الجهة","sources"],
 [Boolean(d.last_scan),"٣. نفّذ أول فحص","اختر فترة نشر واضحة واضغط ابدأ رصدًا الآن","scan"],
 [d.news_approved>0,"٤. راجع الأخبار","افتح نتيجة الفحص واعتمد المواد التي تأكدت منها","articles"],
 [Boolean(d.last_report),"٥. أنشئ تقرير الجهة","اختر المواد وترتيبها، ثم نزّل Word من الأرشيف","reports"]
];
const next=items.find(x=>!x[0]);
return '<div class="panel"><div class="panel-title"><h3>مسار أول تجربة للجهة — ٥ خطوات</h3><small class="muted">اختر الخطوة التالية مباشرة، بدون الرجوع للكود أو إدخال أوامر</small></div>'+
'<div class="onboarding-steps">'+items.map(x=>'<div class="onboarding-step '+(x[0]?'complete':'')+'"><strong>'+(x[0]?'✓ ':'○ ')+x[1]+'</strong><span>'+x[2]+'</span></div>').join("")+'</div>'+
(next?'<p class="notice-box"><b>الخطوة التالية:</b> '+next[2]+' <button class="text-btn" data-action="'+(next[3]==="scan"?"start-scan":"goto")+'" data-filter="'+next[3]+'">ابدأ هذه الخطوة ←</button></p>':'<p class="notice-box">أكملت الرحلة. افتح الأرشيف أو غيّر فترة الرصد لتجربة جديدة.</p>')+'</div>';
}
async function renderHome(){const d=await api(rootPath("/dashboard"));const s=d.last_scan;const sources=(await api(rootPath("/sources"))).sources;const stat=(n,label,hint,ic,action,filter)=>'<div class="stat" data-action="'+action+'" '+(filter?'data-filter="'+filter+'"':"")+'><div class="ic">'+ic+'</div><strong>'+htmlEscape(n)+'</strong><div class="label">'+label+'</div><small>'+hint+'</small></div>';
const publisher=Object.entries(d.publishers||{}).sort((a,b)=>b[1]-a[1]);const max=Math.max(1,...publisher.map(x=>x[1]));
const bars=publisher.length?publisher.slice(0,8).map(([name,count])=>'<div class="barrow" data-action="publisher-filter" data-publisher="'+htmlEscape(name)+'"><span class="bar-label" title="'+htmlEscape(name)+'">'+htmlEscape(name)+'</span><div class="bartrack"><div class="bar" style="width:'+Math.round(count/max*100)+'%"></div></div><small>'+count+'</small></div>').join(""):empty("لا يوجد توزيع بعد","نفّذ الفحص اليدوي أولًا");
const daily=Object.entries(d.timeline||{}).sort((a,b)=>a[0].localeCompare(b[0]));const dailymax=Math.max(1,...daily.map(x=>x[1]));
const trend=daily.length?daily.slice(-7).map(([date,n])=>'<div class="barrow" data-action="date-filter" data-date="'+htmlEscape(date)+'"><span class="bar-label">'+htmlEscape(date)+'</span><div class="bartrack"><div class="bar" style="width:'+Math.round(n/dailymax*100)+'%"></div></div><small>'+n+'</small></div>').join(""):empty("لم يبدأ الرصد بعد","لا توجد أرقام تغطية لعرضها");
const history=await api(rootPath("/articles?"+qs({state:"pending"})));const sample=history.articles.slice(0,4);
$("view").innerHTML=head("ملخص الرصد الإعلامي للجهة",s?"آخر فحص: "+fmt(s.started_at)+" — "+niceState(s.status):"هذه مساحة جهة مستقلة. زر الرصد يبدأ الفحص فقط ولا يرسل بريدًا.",actionButton("+ إنشاء جهة","new-tenant",false,owner()?"":"hidden")+actionButton("ابدأ رصدًا الآن","start-scan",true,canReview()?"":"disabled"))+
scanWindow()+onboardingGuide(d,sources)+'<div class="notice-box">حالة الجدولة: '+htmlEscape(d.scheduler)+'. الأعداد التالية هي <b>روابط تغطية منشورة/تجريبية</b> وليست بالضرورة أحداثًا مستقلة. الضغط على المؤشر يفتح العناصر المكوِّنة له.</div>'+
'<section class="grid stats">'+stat(d.coverages,"التغطيات المكتشفة","عدد روابط الأخبار المحفوظة","▤","goto","articles")+stat(d.events,"الأحداث المستقلة","تجميع محافظ ويمكن فتح تغطياته","◎","event-groups")+stat(d.news_pending,"بانتظار المراجعة","مواد تحتاج قرار محلل","◷","goto","pending")+stat(d.sources_unavailable,"مصادر تعذّرت","آخر تشغيل فقط","⚠","goto","sources")+'</section>'+
'<section class="grid panels"><div><div class="panel"><div class="panel-title"><h3>التغطيات عبر الأيام</h3><small class="mini">عدد الروابط حسب تاريخ النشر</small></div><div class="bars">'+trend+'</div></div><div class="panel"><div class="panel-title"><h3>آخر المواد للمراجعة</h3><button class="text-btn" data-action="goto" data-filter="articles">كل الأخبار</button></div>'+(sample.length?sample.map(a=>'<div class="rowline arow"><div><strong>'+htmlEscape(a.title)+'</strong><small>'+htmlEscape(a.publisher)+' · '+fmt(a.published_at)+(a.demo?' · DEMO':'')+'</small></div><button class="text-btn" data-action="article-detail" data-id="'+a.id+'">مراجعة</button></div>').join(""):empty("لا توجد مواد معلقة","يمكنك بدء فحص يدوي أو فتح الأرشيف."))+'</div></div><div><div class="panel"><div class="panel-title"><h3>المصادر والناشرون</h3><small class="mini">توزيع حسب تغطية الرابط</small></div><div class="bars">'+bars+'</div></div><div class="panel"><div class="panel-title"><h3>ملخص آخر تشغيل</h3></div><div class="summary-grid"><div><strong>'+htmlEscape(s?JSON.parse(s.summary||"{}").sources_ok??"—":"—")+'</strong><span>مصادر نجحت</span></div><div><strong>'+htmlEscape(s?JSON.parse(s.summary||"{}").sources_unavailable??"—":"—")+'</strong><span>مصادر متعذرة</span></div><div><strong>'+htmlEscape(s?JSON.parse(s.summary||"{}").new_matching_coverages??"—":"—")+'</strong><span>مطابقات جديدة</span></div><div><strong>'+htmlEscape(d.last_report?"نعم":"لا")+'</strong><span>تقرير مؤرشف</span></div></div>'+(s?'<button class="text-btn" data-action="scan-detail" data-id="'+s.id+'">تفاصيل الفحص ←</button>':"")+'</div></div></section>';}
async function renderArticles(){const f=context.filter||{};let params={};if(f.event_key)params.event_key=f.event_key;if(f.scan_id)params.scan_id=f.scan_id;
if(f.image_state)params.image_state=f.image_state;if(f.reported)params.reported=f.reported;
if(f.source_id)params.source_id=f.source_id;if(f.state)params.state=f.state;if(f.q)params.q=f.q;if(f.publisher)params.publisher=f.publisher;if(f.since)params.since=f.since;if(f.until)params.until=f.until;const data=await api(rootPath("/articles?"+qs(params)));const rows=data.articles;const pubs=[...new Set(rows.map(a=>a.publisher))].sort();$("view").innerHTML=head("الأخبار والتغطيات","ابحث وراجع كل خبر من رابط ناشره وصورته وحالة توثيقه. البيانات التجريبية مُعلّمة.",actionButton("ابدأ رصدًا الآن","start-scan",true,canReview()?"":"disabled"))+
(f.event_key?'<div class="notice-box">تغطيات حدث محدد · '+badge(f.event_key,"ok")+' <button class="text-btn" data-action="clear-articles">عرض جميع الأخبار</button></div>':"")+
(f.scan_id?'<div class="notice-box">الأخبار المرتبطة بالفحص المحدد'+(f.image_state?' — صور أصلية موثقة':"")+(f.reported?' — مدرجة في تقرير':"")+' <button class="text-btn" data-action="clear-articles">مسح الفلاتر</button></div>':"")+
'<div class="filters"><label>بحث أو موضوع<input id="filter-query" placeholder="اكتب كلمة أو موضوعًا" value="'+htmlEscape(f.q||"")+'"></label><label>حالة المراجعة<select id="filter-state"><option value="">كل الحالات</option>'+["pending","approved","rejected"].map(s=>'<option value="'+s+'" '+(f.state===s?"selected":"")+'>'+niceState(s)+'</option>').join("")+'</select></label><label>الناشر<select id="filter-publisher"><option value="">كل الناشرين</option>'+pubs.map(p=>'<option '+(f.publisher===p?"selected":"")+'>'+htmlEscape(p)+'</option>').join("")+'</select></label><label>من تاريخ<input type="date" id="filter-from" value="'+htmlEscape((f.since||"").slice(0,10))+'"></label><label>حتى تاريخ<input type="date" id="filter-to" value="'+htmlEscape((f.until||"").slice(0,10))+'"></label><div style="align-self:end">'+actionButton("تطبيق الفلاتر","filter-articles")+' '+actionButton("مسح","clear-articles")+'</div></div>'+
(rows.length?'<div class="table-wrap"><table><thead><tr><th>الخبر</th><th>الناشر</th><th>النشر / الاكتشاف</th><th>الحالة والصورة</th><th></th></tr></thead><tbody>'+rows.map(a=>'<tr><td><strong>'+htmlEscape(a.title)+'</strong><br><small class="muted">المطابقة: '+htmlEscape(a.match_reason)+'</small></td><td>'+htmlEscape(a.publisher)+(a.demo?'<br>'+badge("بيانات تجريبية","demo"):"")+'</td><td>نشر: '+fmt(a.published_at)+'<br>اكتشاف: '+fmt(a.discovered_at)+'</td><td>'+badge(niceState(a.state),a.state==="approved"?"ok":a.state==="rejected"?"bad":"warn")+'<br>'+badge(a.image_state==="verified_original"?"صورة أصلية":a.image_state==="demo_illustration"?"صورة توضيحية":"بلا صورة أصلية",a.image_state==="verified_original"?"ok":"warn")+'</td><td><button class="text-btn" data-action="article-detail" data-id="'+a.id+'">تفاصيل ←</button></td></tr>').join("")+'</tbody></table></div>':empty("لا توجد أخبار بهذه الفلاتر","جرّب تغيير الفترة أو إزالة كلمات البحث، أو ابدأ فحصًا يدويًا."))+
'<p class="muted">عدد الروابط الظاهرة: '+rows.length+'. الحدث الواحد قد تكون له تغطيات من ناشرين مختلفين؛ يمكنك تعديل رقم مجموعة الحدث أثناء المراجعة.</p>';
}
async function renderSources(){const data=await api(rootPath("/sources"));const s=data.sources;const scanRows=(await api(rootPath("/scans"))).scans;const latest=scanRows[0];const checks=latest?(await api(rootPath("/scans/"+latest.id))).source_checks:[];const checkMap=Object.fromEntries(checks.map(x=>[x.source_id,x]));$("view").innerHTML=head("المصادر","استعرض سلامة كل مصدر وسبب التعذر، وأضف مصادر RSS معتمدة فقط.",actionButton("+ إضافة مصدر","add-source",false,canAdmin()?"":"disabled")+
actionButton("فحص الآن","start-scan",true,canReview()?"":"disabled"))+
scanWindow()+'<div class="notice-box"><b>مصدر سليم، صفر مطابقات</b> يعني أن القراءة نجحت لكن لم تظهر مواد تتفق مع شروط الجهة. <b>مصدر متعذر</b> يعني أن الاتصال أو الصيغة فشلا؛ لا نستنتج غياب الأخبار. المصادر التجريبية ليست نشرًا فعليًا.</div>'+
(s.length?'<div class="table-wrap"><table><thead><tr><th>المصدر</th><th>آخر حالة</th><th>آخر نجاح</th><th>وقت المحاولة</th><th>المفحوص / المؤهل</th><th>أسباب عدم التأهل</th><th>التحكم</th></tr></thead><tbody>'+s.map(x=>'<tr><td><strong>'+htmlEscape(x.name)+'</strong><br><small class="muted">'+htmlEscape(x.feed_url)+'</small><br><small class="muted">حقوق إعادة استخدام الصور: '+(x.reuse_rights==="unreviewed"?"غير معتمدة — تتطلب موافقة الناشر":"تحتاج مراجعة الترخيص")+'</small></td><td>'+(!x.enabled?badge("موقوف","warn"):!x.last_ok&&!x.last_error?badge("لم يُفحص بعد"):x.last_error?badge("تعذّر الفحص","bad"):badge("سليم","ok"))+'</td><td>'+fmt(x.last_ok)+'</td><td>'+fmt(checkMap[x.id]?.checked_at)+'</td><td>'+(checkMap[x.id]?.scanned??0)+' / '+(checkMap[x.id]?.matched??0)+'</td><td>'+htmlEscape(checkMap[x.id]?.reason||"—")+'<br><small class="muted">مستبعد: '+(checkMap[x.id]?.excluded??0)+' · خارج النافذة: '+(checkMap[x.id]?.outside_window??0)+' · مكرر: '+(checkMap[x.id]?.already_known??0)+'</small></td><td><button class="text-btn" data-action="toggle-source" data-id="'+x.id+'" data-enabled="'+(x.enabled?0:1)+'" '+(canAdmin()?"":"disabled")+'>'+(x.enabled?"تعطيل":"تفعيل")+'</button></td></tr>').join("")+'</tbody></table></div>':empty("لم تُضف مصادر بعد","أضف مصدرًا معتمدًا من القائمة ثم ابدأ الفحص."));
}
async function renderReports(){const [reports,articles,ten]=await Promise.all([api(rootPath("/reports")),api(rootPath("/articles?state=approved")),api(rootPath())]);const r=reports.reports;const a=articles.articles;const status=ten.duplicate_policy==="events"?"أحداث مستقلة (تغطية واحدة لكل حدث)":"جميع روابط التغطية";$("view").innerHTML=head("التقارير والأرشيف","ملف Word مرتبط بالجهة وبالصور المختارة وبإعدادات وقت إنشائه.",actionButton("+ إنشاء تقرير Word","create-report",true,canReview()?"":"disabled"))+
'<div class="notice-box">سياسة الجهة: '+htmlEscape(status)+' · هدف العدد: '+ten.target+' · مواد معتمدة قابلة للاختيار: '+a.length+'. إذا لم توجد صور أصلية، يُوسم التقرير بأنه مسودة أو DEMO ولا يُدَّعى اكتمال توثيقه.</div>'+
(r.length?'<div class="table-wrap"><table><thead><tr><th>تاريخ الإنشاء</th><th>نافذة التقرير</th><th>العدد</th><th>الملف</th><th></th></tr></thead><tbody>'+r.map(x=>'<tr><td>'+fmt(x.created_at)+'</td><td>'+fmt(x.window_start)+'<br>إلى '+fmt(x.window_end)+'</td><td>'+JSON.parse(x.manifest).length+'</td><td><small>SHA '+htmlEscape(x.file_sha.slice(0,15))+'…</small></td><td><button class="text-btn" data-action="report-detail" data-id="'+x.id+'">معاينة</button> · <a class="text-btn" href="'+rootPath("/reports/"+x.id+"/download")+'">تنزيل Word</a></td></tr>').join("")+'</tbody></table></div>':empty("الأرشيف فارغ","بعد اعتماد مواد، اضغط إنشاء تقرير Word ليظهر هنا."));}
async function renderSettings(){const t=await api(rootPath());const members=canAdmin()?(await api(rootPath("/members"))).members:[];$("view").innerHTML=head("إعدادات الجهة","كل تعديل يسري على الفحوص والتقارير الجديدة، ولا يغيّر الملفات المؤرشفة.",owner()?actionButton("+ جهة جديدة","new-tenant"):"")+
'<div class="notice-box">هذه البيانات تخص <b>'+htmlEscape(t.name)+'</b> وحدها. صلاحيتك '+htmlEscape(t.role)+'. الاحتفاظ بقالب الوزارة في جهة منفصلة لا ينقل بريدها أو سجل تسليمها.</div>'+
'<div class="panel"><h3>الهوية وسياسة الرصد</h3><form id="settings-form"><div class="form-grid two"><label>اسم الجهة<input name="name" required value="'+htmlEscape(t.name)+'"></label><label>المنطقة الزمنية<input name="timezone" value="'+htmlEscape(t.timezone)+'"></label><label>لغة التقرير<select name="language"><option value="ar" '+(t.language==="ar"?"selected":"")+'>العربية</option><option value="en" '+(t.language==="en"?"selected":"")+'>الإنجليزية (واجهة تجريبية)</option></select></label><label>القالب<select name="template"><option value="professional" '+(t.template==="professional"?"selected":"")+'>احترافي</option><option value="brief" '+(t.template==="brief"?"selected":"")+'>موجز</option></select></label><label>هدف الأخبار<input type="number" min="1" max="360" name="target" value="'+t.target+'"></label><label>سياسة التكرار<select name="duplicate_policy"><option value="events" '+(t.duplicate_policy==="events"?"selected":"")+'>حدث مستقل</option><option value="coverages" '+(t.duplicate_policy==="coverages"?"selected":"")+'>كل التغطيات</option></select></label><label>موضوعات الجهة<textarea name="topics">'+htmlEscape(t.topics.join("، "))+'</textarea></label><label>كلمات التضمين<textarea name="includes">'+htmlEscape(t.includes.join("، "))+'</textarea></label><label>كلمات الاستبعاد<textarea name="excludes">'+htmlEscape(t.excludes.join("، "))+'</textarea></label></div><button class="primary" '+(canAdmin()?"":"disabled")+'>حفظ الإعدادات</button></form></div>'+
'<div class="grid panels"><div class="panel"><h3>الشعار</h3>'+(t.logo_path?'<img src="'+rootPath("/logo")+'" style="max-width:110px;max-height:100px" alt="شعار الجهة">':'<p class="muted">لم يُرفع شعار بعد.</p>')+'<input type="file" accept="image/png,image/jpeg" id="logo-file" '+(canAdmin()?"":"disabled")+'><button class="outline" data-action="upload-logo" '+(canAdmin()?"":"disabled")+'>حفظ الشعار</button><p class="mini">PNG/JPEG، أقل من 150KB. الملف محفوظ في مساحة هذه الجهة فقط.</p></div><div class="panel"><h3>عضو جديد</h3><form id="member-form"><label>بريد المستخدم<input type="email" name="email" required></label><label>كلمة مرور جديدة (14 حرفًا على الأقل)<input type="password" minlength="14" name="password" required></label><label>الصلاحية<select name="role"><option value="tenant_admin">مدير جهة</option><option value="analyst">محلل</option><option value="reader">قارئ</option></select></label><button class="outline" '+(canAdmin()?"":"disabled")+'>إضافة عضو</button></form></div></div>'+
'<div class="panel"><h3>إدارة أعضاء الجهة</h3><p class="muted">يمكنك إيقاف عضوية مستخدم في هذه الجهة فورًا. عند الإيقاف تُلغى جلساته النشطة، وتتوقف صلاحية الوصول إلى الأخبار والصور والتقارير والتنزيلات. لا يؤثر ذلك في عضوياته بجهات أخرى.</p>'+
(canAdmin()?(members.length?members.map(x=>'<div class="rowline arow"><div><strong>'+htmlEscape(x.email)+'</strong><small>'+htmlEscape(x.role==='tenant_admin'?'مدير الجهة':x.role==='analyst'?'محلل':'قارئ')+' · '+(x.active?'نشط':'موقوف')+'</small></div><button class="outline" data-action="member-status" data-id="'+htmlEscape(x.id)+'" data-enabled="'+(x.active?'0':'1')+'" '+(x.email===context.me.email?'disabled title="لا يمكن تعطيل نفسك"':'')+'>'+(x.active?'إيقاف العضوية':'إعادة التفعيل')+'</button></div>').join(""):'<p class="muted">لا أعضاء بعد. أضف أول مستخدم من النموذج أعلاه.</p>'):'<p class="muted">إدارة الأعضاء لمدير الجهة فقط.</p>')+'</div>'+
'<div class="panel"><h3>أمان حسابك</h3><p class="muted">غيّر كلمة مرورك من هنا. بعد الحفظ تُلغى كل جلساتك ويطلب النظام تسجيل الدخول بكلمة المرور الجديدة.</p><form id="password-form"><div class="form-grid two"><label>كلمة المرور الحالية<input type="password" name="current" required autocomplete="current-password"></label><label>كلمة المرور الجديدة (14 حرفًا على الأقل)<input type="password" name="new" required minlength="14" autocomplete="new-password"></label><label>تأكيد كلمة المرور الجديدة<input type="password" name="confirm" required minlength="14" autocomplete="new-password"></label></div><button type="submit" class="outline">تغيير كلمة المرور وتسجيل الخروج من كل الجلسات</button></form></div>'+
'<p class="muted">صلاحيات الوصول تُنفّذ على الخادم: مالك المنصة، مدير الجهة، المحلل، القارئ. لا توجد مراسلات أو إرسال مجدول.</p>';
}
async function startScan(){if(!canReview())return toast("لا توجد صلاحية تشغيل",true);
const startField=$("scan-start")?.value||context.scanFrom||localDatetime(48);
const endField=$("scan-end")?.value||context.scanTo||localDatetime(0);
const begin=new Date(startField),end=new Date(endField);
if(isNaN(begin.getTime())||isNaN(end.getTime())||begin>=end)return toast("راجع بداية الفترة ونهايتها",true);
context.scanFrom=startField;context.scanTo=endField;
try{toast("بدأنا فحص المصادر الحية للفترة المحددة…");
const r=await api(rootPath("/scan"),{start:begin.toISOString(),end:end.toISOString()});
if(r.duplicate_click)toast("نفس الفحص قيد التشغيل؛ لم يبدأ فحص ثانٍ.");
await pollScan(r.scan_id);}catch(e){toast("تعذر بدء الفحص: "+errorLabel(e.message),true);}}
async function pollScan(id){
const tid=context.tid,key=tid+":"+id;
if(context.pollingScan===key){toast("الفحص جارٍ بالفعل: نتابع نفس العملية");return;}
context.pollingScan=key;context.pollDismissed=false;
let tries=0,expected="—";
try{const data=await api("/api/tenants/"+encodeURIComponent(tid)+"/sources");expected=data.sources.filter(s=>s.enabled).length;}catch{}
const loop=async()=>{
  if(context.tid!==tid){context.pollingScan=null;return;}
  try{
    const s=await api("/api/tenants/"+encodeURIComponent(tid)+"/scans/"+encodeURIComponent(id));
    const done=s.source_checks||[];
    if(s.status==="running"){
      if(tries++>=360){
        context.pollingScan=null;
        toast("الفحص لم ينتهِ بعد؛ افتح آخر فحص لمتابعة النتيجة ولا تعتبرها صفر أخبار",true);
        return;
      }
      if(!context.pollDismissed){
        const list=done.map(c=>'<div class="rowline"><strong>'+htmlEscape(c.name)+'</strong> '+badge(c.status==="ok"?"تم الفحص":"تعذر",c.status==="ok"?"ok":"bad")+'<br><small>تمت المحاولة '+fmt(c.checked_at)+' · مقروء '+c.scanned+' · مطابق جديد '+c.matched+(c.reason?" · "+htmlEscape(errorLabel(c.reason)):"")+'</small></div>').join("");
        modal('<h2>جار فحص المصادر الحقيقية…</h2><p class="muted">عملية واحدة، لا إرسال بريد ولا بيانات DEMO بديلة. يمكنك إغلاق النافذة ومواصلة العمل.</p><div class="notice-box">اكتملت محاولة '+done.length+' من '+expected+' مصادر. النتائج تُحفظ بعد كل مصدر، وحتى لو تعذّر الآخر.</div>'+(list||'<p class="muted">جار الاتصال بالمصدر الأول…</p>'));
        $("dialog").dataset.kind="scan-progress";
      }
      context.scanTimer=setTimeout(loop,1000);
      return;
    }
    const shouldShow=!context.pollDismissed;
    context.pollingScan=null;
    if(shouldShow)closeModal();
    toast("انتهى الفحص: "+niceState(s.status)+" · "+done.filter(c=>c.status==="ok").length+" مصادر نجحت");
    await render();
    if(shouldShow)await showScanDetail(id);
  }catch(e){context.pollingScan=null;toast("تعذر متابعة الفحص، ولا يعني هذا نجاحًا أو صفر أخبار: "+errorLabel(e.message),true);}
};
await loop();
}
function scanMetricsUI(s){
const m=s.metrics||{},rows=[
 ["التغطيات المكتشفة",m.coverages||0,{}],
 ["الأحداث المستقلة",m.events||0,{}],
 ["صور الناشرين الأصلية المتحقَّق منها",m.images_verified||0,{"image-state":"verified_original"}],
 ["أخبار اعتمدها المحلل",m.approved||0,{"state":"approved"}],
 ["بانتظار المراجعة",m.pending||0,{"state":"pending"}],
 ["أخبار اختيرت في تقرير",m.report_selected||0,{"reported":"yes"}]
];
return '<h3>أخبار هذا الفحص — افتح أي عدد لمعرفة المواد المكوِّنة له</h3><div class="grid stats">'+
rows.map(([label,n,attributes])=>'<button class="stat" data-action="scan-filter" data-scanid="'+s.id+'" '+
Object.entries(attributes).map(([key,val])=>'data-'+key+'="'+val+'"').join(" ")+
' style="text-align:right;background:white;border:1px solid #e2e8f0;cursor:pointer"><strong>'+n+'</strong><small>'+label+'</small></button>').join("")+'</div>';
}
async function showScanDetail(id){const s=await api(rootPath("/scans/"+id));
const sum=JSON.parse(s.summary||"{}");const checks=s.source_checks||[];
modal('<h2>نتيجة الفحص اليدوي</h2><p>'+badge(niceState(s.status),s.status==="partial"?"warn":"ok")+' · بدأ '+fmt(s.started_at)+' · انتهى '+fmt(s.ended_at)+'</p>'+
'<div class="notice-box"><b>نافذة النشر:</b> '+fmt(s.window_start||sum.window_start)+' — '+fmt(s.window_end||sum.window_end)+'<br>وضع الرصد: '+htmlEscape(sum.mode||"غير محدد")+'. نجاح المصدر لا يعني وجود خبر مطابق.</div>'+
'<div class="summary-grid"><div><strong>'+(sum.items_inspected??0)+'</strong><span>مادة مقروءة</span></div><div><strong>'+(sum.new_matching_coverages??0)+'</strong><span>تغطية جديدة مؤهلة</span></div><div><strong>'+(sum.sources_ok??0)+'</strong><span>مصادر نجحت</span></div><div><strong>'+(sum.sources_unavailable??0)+'</strong><span>مصادر تعذّرت</span></div><div><strong>'+(sum.excluded_or_unmatched??0)+'</strong><span>غير مطابقة أو مستبعدة</span></div><div><strong>'+(sum.outside_window??0)+'</strong><span>خارج فترة النشر</span></div></div>'+scanMetricsUI(s)+'<h3>أدلة نتيجة كل مصدر</h3>'+
checks.map(c=>'<div class="rowline"><button class="text-btn" data-action="scan-filter" data-scanid="'+s.id+'" data-sourceid="'+c.source_id+'">'+htmlEscape(c.name)+'</button> '+badge(c.status==="ok"?"تمت القراءة":"تعذر الفحص",c.status==="ok"?"ok":"bad")+
'<br><small>آخر محاولة '+fmt(c.checked_at)+' · مقروء '+c.scanned+' · جديد مطابق '+c.matched+' · مستبعد '+(c.excluded??0)+' · خارج الفترة '+(c.outside_window??0)+' · ظهر سابقًا '+(c.already_known??0)+'</small>'+
'<br><small>'+htmlEscape(c.status==="ok"&&c.matched===0?"المصدر سليم لكن لا توجد مواد جديدة تطابق الشروط في الفترة.":c.reason?"السبب: "+errorLabel(c.reason):"لا توجد أخطاء")+'</small></div>').join("")+
'<p class="muted">المصدر المتعذر لا يُحتسب صفر أخبار ولا يؤدي إلى بيانات تجريبية. يمكن إعادة فحصه لاحقًا.</p>'+
'<button class="primary" data-action="goto" data-filter="articles">فتح التغطيات</button>');}
async function showEventGroups(){const d=await api(rootPath("/dashboard"));const groups=d.event_groups||[];
modal('<h2>الأحداث والتغطيات</h2><p class="muted">الحدث مجموعة محافظة لعناوين متشابهة، ويمكن للمحلل تصحيح الربط يدويًا. كل تغطية هي رابط ناشر مستقل.</p>'+
(groups.length?groups.map(g=>'<div class="rowline arow"><div><strong>'+htmlEscape(g.title)+'</strong><small>'+g.count+' روابط تغطية</small></div><button class="text-btn" data-action="event-filter" data-key="'+htmlEscape(g.key)+'">فتح كل الروابط ←</button></div>').join(""):empty("لا أحداث بعد","شغّل فحصًا يدويًا أولًا.")));}
async function showArticle(id){const a=await api(rootPath("/articles/"+id));const history=JSON.parse(a.review_log||"[]");
modal('<div class="detail"><h2>'+htmlEscape(a.title)+'</h2><p>'+badge(niceState(a.state),a.state==="approved"?"ok":"warn")+' '+badge(a.demo?"عرض تجريبي":"خبر من RSS حقيقي",a.demo?"demo":"ok")+'</p>'+
'<div class="details"><div><small>الناشر</small>'+htmlEscape(a.publisher)+'</div><div><small>سبب المطابقة</small>'+htmlEscape(a.match_reason)+'</div><div><small>تاريخ النشر لدى الناشر</small>'+fmt(a.published_at)+'</div><div><small>تاريخ اكتشاف رصد</small>'+fmt(a.discovered_at)+'</div></div>'+
'<p><a target="_blank" rel="noopener noreferrer" class="text-btn" href="'+htmlEscape(a.url)+'">فتح رابط المصدر الأصلي ↗</a></p>'+
(a.image_path?'<img class="preview-image" src="'+rootPath("/articles/"+a.id+"/image")+'" alt="صورة الخبر المرفقة" />':'<div class="notice-box">لا توجد لقطة ناشر أصلية معتمدة لهذا الخبر؛ يمكن طلب الالتقاط يدويًا إن سمح الناشر.</div>')+
'<p>'+badge(a.image_state==="verified_original"?"لقطة ناشر أصلية متحقَّق منها":a.demo?"صورة تمثيلية DEMO":"الصورة غير موثقة",a.image_state==="verified_original"?"ok":"warn")+'<br><small>بصمة JPEG: '+htmlEscape(a.image_sha||"غير موجودة")+'</small>'+(a.image_error?'<br><small class="danger">سبب فشل الصورة: '+htmlEscape(errorLabel(a.image_error))+' · '+fmt(a.image_checked_at)+'</small>':"")+'</p>'+
'<p><small>معرّف الحدث الحالي: '+htmlEscape(a.event_key)+'</small></p><h3>سجل القرارات</h3>'+
(history.length?history.map(h=>'<div class="rowline">'+htmlEscape(niceState(h.state))+' · '+htmlEscape(h.by)+' · '+fmt(h.at)+(h.reason?' · سبب: '+htmlEscape(h.reason):"")+'</div>').join(""):'<p class="muted">لم يقرر المحلل بعد.</p>')+
(!a.demo&&canReview()?'<button class="outline" data-action="capture-original" data-id="'+a.id+'">التقاط صورة أصلية من موقع الناشر</button>':"")+
(canReview()?'<form id="review-form"><label>مجموعة الحدث (اختياري) — اتركها كما هي، أو استخدم نفس المجموعة لخبرين عن الحدث نفسه<input name="event_key" value="'+htmlEscape(a.event_key)+'"></label><label>سبب القرار أو ملاحظات التوثيق<textarea name="reason" placeholder="أسباب الاعتماد أو الاستبعاد">'+htmlEscape(a.review_reason||"")+'</textarea></label><div class="actions" style="margin-top:13px"><button class="primary" name="state" value="approved">اعتماد الخبر</button><button class="outline" name="state" value="rejected">استبعاد مع السبب</button><button class="outline" name="state" value="pending">إعادته للمراجعة</button></div></form>':"")+'</div>');
if(canReview())$("review-form").addEventListener("submit",async ev=>{ev.preventDefault();const b=ev.submitter;try{await api(rootPath("/articles/"+a.id+"/review"),{state:b.value,event_key:ev.target.elements.event_key.value,reason:ev.target.elements.reason.value});toast("حُفظ القرار والسبب في سجل هذه المادة");closeModal();render();}catch(e){toast(errorLabel(e.message),true);}});}
async function showReport(id){
const x=await api(rootPath("/reports/"+id)),manifest=JSON.parse(x.manifest||"[]");
const rows=manifest.map((a,i)=>{
const sh=a.image_sha||"";
return '<div class="rowline"><strong>'+(i+1)+'. '+htmlEscape(a.title)+'</strong>'+
'<p><small>الناشر: '+htmlEscape(a.publisher)+'</small> · <a class="text-btn" href="'+htmlEscape(a.url)+'" target="_blank" rel="noopener noreferrer">فتح رابط الناشر الأصلي ↗</a></p>'+
'<small>الصورة: '+htmlEscape(a.image_state||"missing")+' · بصمة SHA-256: <code title="'+htmlEscape(sh)+'">'+htmlEscape(sh?sh.slice(0,18)+"…":"لا توجد")+'</code></small></div>';
}).join("");
modal('<h2>معاينة التقرير المؤرشف</h2><p class="muted">أُنشئ '+fmt(x.created_at)+' · الفترة '+fmt(x.window_start)+' إلى '+fmt(x.window_end)+'</p>'+
'<p class="notice-box">بصمة ملف Word الكاملة SHA-256: <code style="overflow-wrap:anywhere">'+htmlEscape(x.file_sha)+'</code></p>'+
'<h3>المواد داخل الملف بالترتيب</h3>'+
(rows||'<p class="muted">تقرير صفر مواد. لا يعني عدم نشر أخبار خارج مصادر الرصد ونطاقه.</p>')+
'<a href="'+rootPath("/reports/"+id+"/download")+'" class="primary" style="display:inline-block;margin-top:16px">تنزيل Word</a>');
}
async function createReport(){
const [res,tenant,all]=await Promise.all([api(rootPath("/articles?state=approved")),api(rootPath()),api(rootPath("/articles"))]);
const articles=res.articles,stamps=articles.map(a=>new Date(a.published_at).getTime()).filter(Number.isFinite);
const now=Date.now();
const from=new Date(stamps.length?Math.min(...stamps)-60000:now-86400000);
const to=new Date(stamps.length?Math.max(...stamps)+60000:now);
const localInput=d=>new Date(d.getTime()-d.getTimezoneOffset()*60000).toISOString().slice(0,16);
const rows=articles.map(a=>'<div class="checkrow report-row"><label style="display:flex;flex:1;align-items:center;gap:10px"><input type="checkbox" name="items" value="'+htmlEscape(a.id)+'" checked><span>'+htmlEscape(a.title)+'<br><small>'+htmlEscape(a.publisher)+' · '+(a.image_state==="verified_original"?"صورة ناشر موثقة":a.demo?"صورة DEMO":"بلا صورة أصلية")+'</small></span></label><button type="button" class="text-btn" data-move="up" title="للأعلى">↑</button><button type="button" class="text-btn" data-move="down" title="للأسفل">↓</button></div>').join("");
modal('<h2>معاينة قبل إصدار Word</h2><p class="muted">هذه المواد المعتمدة فقط. يمكنك تغيير ترتيب البطاقات بالأسهم ثم تنزيل نسخة ثابتة من الأرشيف.</p>'+
'<form id="report-form"><div class="form-grid two"><label>من — توقيت جهازك<input type="datetime-local" name="start" value="'+localInput(from)+'" required></label><label>إلى — توقيت جهازك<input type="datetime-local" name="end" value="'+localInput(to)+'" required></label></div>'+
'<div class="notice-box">الوضع: '+(tenant.mode==="demo"?"عرض تجريبي غير حقيقي":"رصد حي من ناشرين معتمدين")+' · هدف الأخبار: '+tenant.target+' · سياسة التكرار: '+(tenant.duplicate_policy==="events"?"حدث واحد، تغطية واحدة":"جميع تغطيات الناشرين")+'</div>'+
'<p class="muted" id="report-preview-count"></p>'+
(rows||'<p class="notice-box">لا توجد مواد معتمدة؛ سيُنشأ تقرير صفر مواد مع سبب القصور.</p>')+
'<button type="submit" class="primary" style="margin-top:19px">إنشاء Word وحفظه في أرشيف الجهة</button></form>');
const f=$("report-form");
function summary(){
const ids=[...f.querySelectorAll('input[name="items"]:checked')].map(x=>x.value);
const start=new Date(f.elements.start.value),end=new Date(f.elements.end.value);
const inside=a=>new Date(a.published_at)>=start&&new Date(a.published_at)<=end;
const visible=all.articles.filter(inside);
const chosen=ids.map(id=>articles.find(x=>x.id===id)).filter(Boolean);
const seen=new Set();
const final=chosen.filter(a=>{if(!inside(a))return false;if(tenant.duplicate_policy!=="events")return true;if(seen.has(a.event_key))return false;seen.add(a.event_key);return true;}).slice(0,tenant.target);
const outside=chosen.filter(a=>!inside(a)).length;
$("report-preview-count").textContent="تغطيات محفوظة داخل الفترة: "+visible.length+" · معتمدة: "+visible.filter(a=>a.state==="approved").length+" · معلقة: "+visible.filter(a=>a.state==="pending").length+" | المحدد: "+chosen.length+" · سيدخل Word: "+final.length+" من هدف "+tenant.target+" · "+new Set(final.map(x=>x.event_key)).size+" أحداث · "+new Set(final.map(x=>x.publisher)).size+" ناشرين · "+final.filter(x=>x.image_state==="verified_original").length+" صور أصلية. "+(outside?"تنبيه: "+outside+" خبر خارج الفترة؛ أزل اختياره قبل الإنشاء. ":"")+(chosen.length!==final.length?"يؤثر نطاق الفترة وسياسة التكرار والحد الأقصى على العدد النهائي. ":"")+(visible.length>final.length?"بقية التغطيات ليست كلها معتمدة أو مختارة. هذا لا يثبت نقص تغطية المصادر. ":"");
}
f.addEventListener("change",summary);
f.addEventListener("click",event=>{
  const b=event.target.closest("[data-move]");if(!b)return;
  const row=b.closest(".report-row"),parent=row.parentElement;
  if(b.dataset.move==="up"){const before=row.previousElementSibling;if(before&&before.classList.contains("report-row"))parent.insertBefore(row,before);}
  else{const after=row.nextElementSibling;if(after&&after.classList.contains("report-row"))parent.insertBefore(after,row);}
  summary();
});
summary();
f.addEventListener("submit",async e=>{
e.preventDefault();const submit=f.querySelector('button[type="submit"]');submit.disabled=true;
const ids=[...f.querySelectorAll('input[name="items"]:checked')].map(x=>x.value);
const start=new Date(f.elements.start.value),end=new Date(f.elements.end.value);
if(isNaN(start)||isNaN(end)||start>=end){toast("راجع نافذة نشر التقرير",true);submit.disabled=false;return;}
try{const r=await api(rootPath("/reports"),{article_ids:ids,start:start.toISOString(),end:end.toISOString()});toast("حُفظ تقرير Word: "+r.items+" تغطيات بالترتيب المحدد");closeModal();await render();await showReport(r.report_id);}
catch(err){toast("تعذر إنشاء Word: "+errorLabel(err.message),true);submit.disabled=false;}
});
}
async function newTenant(){if(!owner())return toast("مالك المنصة فقط ينشئ الجهات",true);modal('<h2>إضافة جهة جديدة</h2><p class="muted">مساحة منفصلة بإعدادات خاصة. لن تختلط أخبارها أو تقاريرها بجهة أخرى.</p><form id="new-tenant-form"><label>اسم الجهة<input name="name" required minlength="2" placeholder="الجهة الجديدة"></label><div class="form-grid two"><label>الموضوعات<textarea name="topics" placeholder="التعليم العالي، البحث العلمي"></textarea></label><label>كلمات التضمين<textarea name="includes" placeholder="جامعة، بحث"></textarea></label><label>كلمات الاستبعاد<textarea name="excludes"></textarea></label><label>المنطقة الزمنية<input name="timezone" value="Africa/Cairo"></label><label>الهدف<input name="target" type="number" min="1" max="360" value="10"></label><label>سياسة الأخبار<select name="duplicate_policy"><option value="events">أحداث مستقلة</option><option value="coverages">كل التغطيات</option></select></label></div><button class="primary">إنشاء مساحة الجهة</button></form>');
$("new-tenant-form").addEventListener("submit",async e=>{e.preventDefault();const f=e.target;try{const t=await api("/api/tenants",{name:f.elements.name.value,topics:f.elements.topics.value,includes:f.elements.includes.value,excludes:f.elements.excludes.value,timezone:f.elements.timezone.value,target:Number(f.elements.target.value),duplicate_policy:f.elements.duplicate_policy.value});await loadMe();context.tid=t.id;sessionStorage.setItem("rasd_selected_tenant",t.id);bindShell();closeModal();setTab("settings");toast("أنشأت جهة جديدة — أضف مصادرها قبل الرصد");}catch(err){toast(err.message,true);}});}
async function addSource(){if(!canAdmin())return toast("مدير الجهة فقط يضيف المصادر",true);const x=await api("/api/catalog");modal('<h2>إضافة مصدر معتمد</h2><p class="muted">لدواعي الأمان لا يقبل هذا الإصدار روابط RSS عشوائية؛ اختر مصدرًا من القائمة المُراجعة، أو مصدرًا توضيحيًا للتجربة.</p><form id="source-form"><label>المصدر<select name="feed_url">'+x.sources.map(s=>'<option value="'+htmlEscape(s.url)+'">'+htmlEscape(s.name)+'</option>').join("")+'<optgroup label="مصادر توضيحية وليست أخبارًا حقيقية">'+x.demo.map(s=>'<option value="'+s+'">'+s+'</option>').join("")+'</optgroup></select></label><label>الاسم الظاهر<input name="name" required placeholder="مثال: الشروق - الاقتصاد"></label><button class="primary">إضافة المصدر</button></form>');
$("source-form").addEventListener("submit",async e=>{e.preventDefault();try{await api(rootPath("/sources"),{name:e.target.elements.name.value,feed_url:e.target.elements.feed_url.value});closeModal();toast("أُضيف المصدر إلى إعدادات الجهة");render();}catch(err){toast(err.message,true);}});}
function filterArticles(){const val=id=>$(id)?.value||"";const since=val("filter-from"),until=val("filter-to");setTab("articles",{q:val("filter-query"),state:val("filter-state"),publisher:val("filter-publisher"),event_key:context.filter?.event_key||null,
scan_id:context.filter?.scan_id||null,source_id:context.filter?.source_id||null,image_state:context.filter?.image_state||null,
reported:context.filter?.reported||null,since:since?since+"T00:00:00":null,until:until?until+"T23:59:59":null});}
document.addEventListener("click",async e=>{const b=e.target.closest("[data-action]");if(!b)return;const act=b.dataset.action;try{if(act==="goto")return setTab(b.dataset.filter==="pending"?"articles":b.dataset.filter||"articles",b.dataset.filter==="pending"?{state:"pending"}:{});if(act==="new-tenant")return newTenant();if(act==="start-scan")return startScan();if(act==="refresh")return render();if(act==="filter-articles")return filterArticles();if(act==="clear-articles")return setTab("articles");if(act==="scan-filter")return (closeModal(),setTab("articles",{scan_id:b.dataset.scanid,
state:b.dataset.state||null,image_state:b.dataset.imageState||null,source_id:b.dataset.sourceid||null,
reported:b.dataset.reported||null}));
if(act==="event-groups")return showEventGroups();if(act==="event-filter")return (closeModal(),setTab("articles",{event_key:b.dataset.key}));if(act==="scan-detail")return showScanDetail(b.dataset.id);if(act==="article-detail")return showArticle(b.dataset.id);if(act==="capture-original"){toast("جار التحقق من صورة الناشر الأصلية…");try{const result=await api(rootPath("/articles/"+b.dataset.id+"/capture"),{});toast("تم توثيق الصورة الأصلية SHA "+result.sha256.slice(0,12));return showArticle(b.dataset.id);}catch(err){await showArticle(b.dataset.id);toast("تعذّر التوثيق؛ الصورة لم تُعتمد: "+errorLabel(err.message),true);return;}}if(act==="report-detail")return showReport(b.dataset.id);if(act==="create-report")return createReport();if(act==="add-source")return addSource();if(act==="toggle-source"){await api(rootPath("/sources/"+b.dataset.id+"/toggle"),{enabled:b.dataset.enabled==="1"});toast("تم تحديث حالة المصدر، ويسري القرار على التشغيلات التالية");return render();}
if(act==="member-status"){
  if(!canAdmin())return toast("إدارة المستخدمين لمدير الجهة فقط",true);
  const enable=b.dataset.enabled==="1";
  if(!enable&&!window.confirm("إيقاف عضوية المستخدم الآن؟ سيتم إلغاء جلساته ومنع الوصول إلى صور وتقارير هذه الجهة."))return;
  await api(rootPath("/members/"+b.dataset.id+"/status"),{enabled:enable});
  toast(enable?"أُعيد تفعيل عضوية هذا المستخدم. سيحتاج تسجيل الدخول مجددًا.":"أُوقفت العضوية فورًا وأُلغيت جلسات المستخدم.");
  return render();
}if(act==="publisher-filter")return setTab("articles",{publisher:b.dataset.publisher});if(act==="date-filter")return setTab("articles",{since:b.dataset.date,until:b.dataset.date+"T23:59:59"});if(act==="upload-logo")return uploadLogo();}catch(err){toast(err.message,true);}});
async function uploadLogo(){const file=$("logo-file")?.files?.[0];if(!file)return toast("اختر ملف شعار",true);if(file.size>150000)return toast("الشعار يتجاوز 150KB",true);const base64=await new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(String(r.result).split(",")[1]);r.onerror=reject;r.readAsDataURL(file);});try{await api(rootPath("/logo"),{data:base64});toast("حُفظ شعار الجهة");render();}catch(e){toast(e.message,true);}}
$("login-form").addEventListener("submit",async e=>{e.preventDefault();$("login-error").textContent="";const f=e.target;try{const r=await api("/api/login",{email:f.elements.email.value,password:f.elements.password.value});context.csrf=r.csrf;sessionStorage.setItem("rasd_csrf",r.csrf);await start();}catch(err){$("login-error").textContent="بيانات الدخول غير صحيحة أو تعذر الاتصال.";}});$("logout").addEventListener("click",async()=>{closeModal();if(context.scanTimer)clearTimeout(context.scanTimer);try{await api("/api/logout",{});}catch{}context={me:null,tid:null,tab:"home",filter:{},csrf:"",pollingScan:null,scanTimer:null,mode:"live",tz:"Africa/Cairo",scanFrom:null,scanTo:null,topics:[]};sessionStorage.removeItem("rasd_selected_tenant");sessionStorage.removeItem("rasd_csrf");$("shell").classList.add("hidden");$("login").classList.remove("hidden");});$("tenant-switch").addEventListener("change",e=>{closeModal();if(context.scanTimer)clearTimeout(context.scanTimer);context.pollingScan=null;context.mode="live";context.tz="Africa/Cairo";context.scanFrom=null;context.scanTo=null;context.tid=e.target.value;sessionStorage.setItem("rasd_selected_tenant",context.tid);bindShell();setTab("home");});document.querySelectorAll(".nav-item").forEach(x=>x.addEventListener("click",()=>setTab(x.dataset.tab)));$("close-dialog").addEventListener("click",closeModal);$("dialog").addEventListener("click",e=>{if(e.target.id==="dialog")closeModal()});$("mobile-menu").addEventListener("click",()=>document.querySelector(".sidebar").classList.toggle("open"));
document.addEventListener("submit",async e=>{
if(e.target.id==="password-form"){
  e.preventDefault();const f=e.target;
  if(f.elements.new.value!==f.elements.confirm.value)return toast("تأكيد كلمة المرور لا يطابق القيمة الجديدة",true);
  try{await api("/api/account/password",{current_password:f.elements.current.value,new_password:f.elements.new.value});
      if(context.scanTimer)clearTimeout(context.scanTimer);
      sessionStorage.removeItem("rasd_selected_tenant");sessionStorage.removeItem("rasd_csrf");
      context={me:null,tid:null,tab:"home",filter:{},csrf:"",scanTimer:null,pollingScan:null};
      closeModal();$("shell").classList.add("hidden");$("login").classList.remove("hidden");
      $("login-error").textContent="تم تغيير كلمة المرور وإلغاء كل الجلسات؛ سجل الدخول بكلمتك الجديدة.";
      toast("تم تغيير كلمة المرور");
    }catch(err){toast(errorLabel(err.message),true);}
  return;
}
if(e.target.id==="settings-form"){e.preventDefault();const f=e.target;const dto={name:f.elements.name.value,timezone:f.elements.timezone.value,language:f.elements.language.value,template:f.elements.template.value,target:Number(f.elements.target.value),duplicate_policy:f.elements.duplicate_policy.value,topics:f.elements.topics.value,includes:f.elements.includes.value,excludes:f.elements.excludes.value};try{await api(rootPath("/settings"),dto);await loadMe();bindShell();toast("حُفظت الإعدادات — تطبق على الفحوص القادمة فقط.");render();}catch(err){toast(err.message,true);}}if(e.target.id==="member-form"){e.preventDefault();const f=e.target;try{await api(rootPath("/members"),{email:f.elements.email.value,password:f.elements.password.value,role:f.elements.role.value});toast("أُضيف المستخدم. سلّمه بياناته بصورة خاصة؛ لا يرسل رصد رسائل دخول.");f.reset();render();}catch(err){toast(err.message,true);}}});
start();