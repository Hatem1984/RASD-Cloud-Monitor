# RASD | مصفوفة قبول النسخة الساعية — 21 نوفمبر 2026

**تصنيف الحالة: QA release candidate فقط — غير معتمد من الوزارة وغير منشور للإرسال الساعي.**

المستودع \`Hatem1984/RASD-Cloud-Monitor\`، فرع العزل \`release-rasd-hourly-contract-20261121\`. التاريخ والساعة في التقرير والجدول والتسليم تستخدم **Africa/Cairo**؛ مفاتيح الساعة الداخلية الثابتة UTC للسلامة وقت التوقيت الصيفي فقط.

## تمييز مصدر المتطلبات

**مستند وزارة معتمد:** لم يُعثر في المصادر المتصلة والمتاحة أثناء هذه المهمة على خطاب رسمي موقع أو نموذج تكليف حديث يمكن نسب هذه التفاصيل إليه. المستندات \`GATE40_UNIFIED_MINISTRY_WORD_ACCEPTANCE.md\` و\`RASD_PRODUCTION_ACCEPTANCE_2026-10-24.md\` أدلة تطوير داخلية وليست قرارًا من الوزارة. ملفات RASD المؤرشفة من 13 أكتوبر تاريخية، ولا تثبت اعتماد المواصفة الجديدة. لا تُسمّى هذه النسخة «معتمدة من الوزارة» دون مستند رسمي.

**مواصفات المالك المعتمدة:** طلب الاستكمال الصريح بتاريخ 21 نوفمبر 2026، مع قراراته السابقة على العناوين الأصلية، تقرير العجز الصريح، عشرة أخبار/عشرة ناشرين/عشرة أحداث **كهدف مشروط بالتوفر**، و22:00 للتجميع اليومي.

**حلول فنية من المطور:** ضبط حدود الساعة بـUTC وتحويل عرضها للقاهرة، اختبارات source-id + event dedup، CAS موحد لكل ساعة، تقسيم Word عند الحجم، no-retry عند غموض SMTP، مفاتيح تشغيل مغلقة قبل التفويض.

## جدول القبول

| البند | التصنيف/المصدر | اختبار مدخل الاستخدام الفعلي | الدليل المطلوب | الحكم |
|---|---|---|---|---|
| تقرير واحد عن كل ساعة مكتملة بتوقيت القاهرة | مالك، 21 نوفمبر | فحص تأخير المصدر/الاحتياطي عند 07/18/37/48 دقيقة، و21:00–22:00 مقابل 22:00 اليومي، وفصول Cairo | ساعات فعلية متتابعة + سجل ساعة CAS واحد | **QA فقط / LIVE HOLD** |
| حتى 10 أخبار عن 10 أحداث و10 ناشرين مختلفين، منشورة داخل الساعة نفسها | مالك | فحص RSS الأصلي وتاريخ النشر وID ودلالات العناوين مع رفض التاريخ القديم والحدث السابق | العناوين والروابط والدقائق والناشر مع أسباب استبعاد كل مرشح | **قاعدة QA، لكن وفرة المحتوى HOLD** |
| **لو تحقق 3، يعرض الثلاثة وصورهم ويعلن "3 أخبار موثقة من أصل 10 مستهدفة"؛ لو 0 يوضح مصدر/صور/عدم النشر** | مالك، تكليف الاستكمال الحالي | الاختبار من \`run_scheduled\` إلى \`prepare_source_limited_verified_word\` وWord الفعلي، وليس status فارغًا | Word بعدد صحيح، صور أصلية حقيقية، عنوان وملخص وبريد متسق | **QA / LIVE HOLD** |
| كل مرشح مع سبب قبول أو استبعاد | مالك | فحص \`candidate_decisions\` والأسباب \`wrong_original_date / repeated_event / same_publisher / unverified_source\` | سجل داخلي غير كاشف للبيانات الخاصة، مع مجاميع أسباب قصيرة | **QA** |
| روابط/تواريخ أصلية وصلة مباشرة باختصاصات الوزارة | مالك ومتطلبات الخدمة العامة | بوابة RSS التاريخ والناشر والموضوع، واعتماد المرشحين فقط بعد إثبات H1 الأصل | حالة لكل مصدر ونموذج أول رسالة موثقة من ساعة حقيقية | **جزئي** |
| صور الصفحات الأصلية ونفس بايت JPEG في Word | مالك + اختيار تقني SHA-256 | \`proof_capture\` + \`word_images_match_capture_digests\` + فتح DOCX | كل صفحة خبر وصورها وهويتها؛ refusal/blank/lazy-loading HOLD | **QA؛ بعض الناشرين HOLD** |
| الغلاف العربي الكحلي/الذهبي، «رصد»، التحليل والتوزيع والصور والروابط | مالك وقالب مستلم فعليًا | Word حقيقي من Gmail في 21 نوفمبر + Word صناعي من مسار رصد نفسه | معاينة كل صفحة وقابلية القراءة والأعداد | **القالب القديم متحقق؛ الساعي LIVE HOLD** |
| منع رسالتين من تشغيل الرئيسي والاحتياطي أو بعد عطل SMTP | مالك + CAS فني | حجز slot + IDs قبل SMTP، CAS ذَرّي، تعارض رئيسي/احتياطي، عدم تكرار مع receipt uncertain | سجل خاص ومراسلة Gmail واحد لنفس الساعة عبر عدة دورات | **QA / LIVE HOLD** |
| التجميع اليومي 22:00 القاهرة بصور سبق إرسالها بلا إعادة تصوير | مالك + نافذة تسليم موروثة | مقارنة Word يوم 20 نوفمبر بـWord دوري 15:30 و16:30 و20:30 | **3/3 JPEG SHA-256 متطابقة، 3 ناشرين وروابط أصلية** | **PASS لهذه العينة الحقيقية** |
| سعة يومية كافية | مالك؛ قرار تقني | الحد \`MAX_ROLLUP\` يعدّ **عدد الأخبار المستلمة SMTP**، وليس الرسائل. 10×24=240؛ 15×24=360 حد أعلى هندسي؛ Word ≤7.5 MB/جزء، ≤32 أجزاء | اختبارات 240 JPEG و360 cap ورفض 361؛ اختبار حجم صور حقيقية واسع وحصة بريد فعلية | **QA / LIVE HOLD** |
| الدليل الحقيقي للإرسال | مالك | GitHub run → SMTP acceptance → البريد المتصل Inbox → ملف Word الذي وصل → وقت Cairo | وقت الاستحقاق والبدء والاستلام لكل دورة ومرفقاتها، لا يكفي "success" | **القديم موثق؛ الساعي HOLD** |
| موافقة الوزارة الرسمية على النطاق/الجدولة/المستلمين | **وزارة — مستند غير متاح** | مطابقة أحدث خطاب أو نموذج صادر عنها | نص رسمي محدد وتاريخ تفويض | **UNVERIFIED** |

## أدلة حقيقية من آخر حالة إنتاج

- \`main\` عند الفحص: \`6715b41d98795cb547faa0b5ae38ea9c776068e8\`، PR #190 وPR #191 مدمجان، PR #189 مفتوح Draft ومتباعد من main. 14 مصدر RSS مفعّل.
- تقرير Inbox دوري 21 نوفمبر 19:00 القاهرة، استُلم تقريبًا **19:07**: في Word المرسل **خبر واحد مصوّر من النهار**، لكن الناشر يذكر وقت نشر **11:33 القاهرة**؛ لذلك التقرير القديم **لا يجتاز شرط خبر منشور خلال الساعة**.
- تقرير Inbox اليومي 20 نوفمبر 22:00: **3 أخبار من 3 ناشرين**، مطابق لصور تقارير Inbox الدورية 15:30 و16:30 و20:30، **3/3 SHA-256 بصمات متطابقة بايت ببايت**. جرى فتح المستندين وعرض 3 صفحات لكل واحد؛ الصورة تخص العنوان والروابط مضمّنة.
- التشغيل الإنتاجي 21 نوفمبر **19:37 القاهرة**: workflow ناجح كعملية، لكن \`EVIDENCE_HOLD\` من «حابي» \`publisher_access_refused\` و**0 SMTP**؛ لا يُعد رسالة مُسلَّمة.
- [قياس ساعة فعلية 17:00–18:00 القاهرة](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/44927545127): 14/14 RSS قابلة للقراءة، مرشح واحد من عشرة، **قبل صورة الناشر**.
- [إصلاحات المصادر والصور PR #191](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/191)، والهوية البصرية [PR #190](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/190).
- [اختبارات الفرع المنعزل](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/workflows/rasd-isolated-hourly-release-qa-no-send.yml) و[فحص المصدر والصورة إلى Word فعليًا دون إرسال](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/workflows/rasd-release-originals-word-qa-no-send.yml).

**تنبيه البيانات:** يُذكر Inbox الذي أمكن اختباره دون نشر عناوين المستلمين أو أرقام الرسائل أو صورهم داخل المستودع العام. تعذر الاطلاع على Gmail Sent الخاص بحساب SMTP رصد من حساب المالك المتصل؛ Gmail Inbox للمالك **لا يثبت تسليم صندوق الوزارة الآخر**. لا تكتب بيانات خاصّة أو رموز دخول في هذا التقرير.

## النشر الآمن والاسترجاع

1. **الدمج لا يفعّل الإرسال الساعي:** جميع workflows الإنتاجية في فرع المرشح تحمل \`RASD_HOURLY_REPORTS_ENABLED='false'\` و\`RASD_DAILY_VOLUME_DELIVERY_ENABLED='false'\` صراحةً، وتبقى جدولة النصف ساعة كما هي. لا دمج واسع لفرع PR #189.
2. مراجعة ملف-بملف لفرع الإصدار والـCI، والتحقق من اتصال المالك/الوزارة وقبول التطبيق، ومراجعة حصص SMTP وIMAP، ثم تحديد نافذة تنفيذ نهائية بتفويض منفصل قبل تغيير المفاتيح إلى \`true\`.
3. عند التفعيل المصرح به، تشغيل تجريبي **إلى صندوق شخصي مُتحقق فقط** دون الوزارة، ومقارنة رسالة Gmail Sent/Inbox ذات الـWord الأصلي بالـCAS. لا تعد نجاح الاختبار الشخصي اعتماد تسليم الوزارة.
4. **الرجوع بدون Force Push:** إيقاف \`RASD_HOURLY_REPORTS_ENABLED\` و\`RASD_DAILY_VOLUME_DELIVERY_ENABLED\` عبر PR مراجَع؛ الحفاظ على سجل الحجوزات/الرسائل/النسخ؛ لا إعادة إرسال حالة Reserved/uncertain تلقائيًا؛ مراجعة كل receipt قبل استعادة نصف الساعة.
5. راقب تراكم سجل GitHub الخاص: \`MAX_LEDGER_ITEMS=20,000\` وحد API وحجم JSON يحتاجان اختبار سعة واحتفاظ/أرشفة آمنة طويلة الأجل، ولا تتجاوزهما بحذف صامت. إذا لم تتحقق الحصة/الاحتفاظ فلا تعلن استقرارًا يوميًا طويل الأمد.

**الحكم:** لا «مكتمل تقنيًا» ولا «معتمد من الوزارة» دون اختبارات التسليم الحقيقي للنسخة الساعية، وورود Word نفسه في Inbox المقصود، وعدم فقد أحداث أو صور عند 22:00، وتفويض النشر.

## تحديث رصد التشغيل — 22 نوفمبر 2026 (Africa/Cairo)

**التصنيف: الإصدار الساعي QA/HOLD كما هو؛ لم يتم دمجه، ولم يُرسل من هذا الفرع أي بريد.**
هذا ملحق مراجعة حية ويُلغي الاعتماد على حالة 21 نوفمبر وحدها، دون تعديل موافقة الوزارة أو حالة SMTP الخاصة.

| معيار القبول | الدليل من 22 نوفمبر | الحكم |
|---|---|---|
| المستودع وسلامة دمج #190 و#191 دون #189 | main `6715b41`؛ #190/#191 merged؛ #189/#192 Draft | النسخة الساعية غير منشورة |
| مصدر مستقل/تاريخ وصورة أصلية وWord | [Live QA 45065180148](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45065180148): فحص RSS صالح 14/14؛ ثلاث مواد بحثية خلال 72h، صورتان من صفحتين أصليتين و2 JPEG مطابقان داخل Word؛ حابي refused | PASS لعينة المصدر→Word، لا يثبت 10 في ساعة |
| قرار قبول أو استبعاد لكل مرشح حتى بعد امتلاء السعة | Commit `fad9833d` يعالج القفز على مرشحي overflow؛ [795 اختبارًا بدون شبكة/SMTP للإرسال](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45065180170) PASS | PASS محاكاة وCI؛ لا إثبات حصة الساعة الحقيقية |
| أول رسالة ساعية فعلية تصل Inbox | لم تُفعّل switches، ولا توجد رسالة ساعية جديدة من إصدار #192 | **HOLD** |
| أول يومي 22:00 Cairo | [تشغيل 22:00](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45063889247) failed؛ [relay 22:07](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45064602914) failed مع `other_held_failure` غير مشخص علنًا | **PRODUCTION HOLD**؛ فحص السجل/التسليم المحمي يدويًا قبل أي resend |
| آخر استلام فعلي في Inbox الذي أمكن فحصه | 22 نوفمبر 18:07:48 Cairo، رسالة الفحص الدوري 18:00 (نصف ساعة)، Word أصلي 3 صفحات، صورة واحدة من البورصة؛ النشر 17:31 Cairo. آخر يومي وجده البحث: 20 نوفمبر 22:00 Cairo، 3 صور/3 روابط في Word من 3 صفحات؛ لا رسالة يومي لـ21/22 ظهرت في البحث حتى 22:15 Cairo | إثبات تسليم **قديم** للصندوق الشخصي المتصل فقط، وليس إثبات تسليم ساعي أو صندوق الوزارة |
| تفويض وزارة للتفعيل وحصص البريد وCAS | مستند التكليف الرسمي غير متاح، والبيانات المحمية لم تُفحص | **UNVERIFIED / HOLD** |

**حدود التحقق:** حالة `other_held_failure` لا تكفي لتحديد هل السبب تحفظ في CAS، أو IMAP/SMTP، أو اعتماد/سعة، أو خطأ آخر. لا تقم بإلغاء حجز أو إعادة إرسال أي ساعة/تجميع بشكل أعمى. يحتاج صاحب الصلاحية نتيجة تدقيق محمية لمفتاح كل نافذة وreceipt SMTP ومقارنة صندوق Sent قبل أي نشر أو تصحيح. المرفقات الخاصة والروابط إلى Gmail الشخصي **غير منشورة** هنا.

**الرجوع:** يبقى التفعيلان `RASD_HOURLY_REPORTS_ENABLED=false` و`RASD_DAILY_VOLUME_DELIVERY_ENABLED=false`. لا تغيير في `main` أو جدولة الإنتاج أو المستلمين أو السجل الخاص، ولا force push.

## تحقيق 23 نوفمبر 2026 — تسلسل الفشل والساعة الحقيقية

**PR #192 remains DRAFT / QA / PRODUCTION HOLD.** No merge, live send, ledger reservation release, SMTP replay, recipient or cron change was authorized or performed. Local owner-machine production credentials are not available, and the protected read-only CI environment did not start its job; the temporary workflow was removed. No attempt to bypass that protection.

| Check | Exact evidence | Scope and verdict |
|---|---|---|
| Latest unchanged main baseline | `6715b41`; PR #190 and #191 merged; #189 is separate Draft | Production has not switched from 30-minute to hourly |
| 23 November at 12:37/12:40 Cairo | [Cloudflare run 45157769519](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45157769519) and [Backup 45158224596](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45158224596): 14/14 RSS healthy and no new articles; **interval step returned successfully**, followed by failed `rollup_recovery` | First publicly identified failing operation = daily recovery, not feed polling |
| Daily 22:00 Cairo | [22 Nov daily run 45063889247](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45063889247), before any asserted new receipt | Daily Sent/IMAP or document preparation **not yet attributable to an exact fixed error**; don't label `other_held_failure` as an SMTP error |
| Safe daily stage and error classification | `scheduled_rasd.py` now emits fixed `RASD_DAILY_STAGE` boundaries with Cairo day and an 8-character opaque key hint, plus a strict allowlist of Sent/IMAP/Word HOLD codes | Code-level QA; no source, mailbox, IDs, secrets or private record payload in public logs |
| Recreated no-send failure-shaped daily cases | `test_production_daily_reuses_sent_word.py` simulates accepted-story shapes for Nov 21 and Nov 22 and unavailable original Sent: verifies failure before CAS/SMTP and a specific sanitized code; real private payload never copied into tests | PASS, NOT proof of exact real root cause |
| One genuinely completed hour | [Run 45162850875](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45162850875): Cairo 23 Nov 12:00–13:00; 14 feeds, 13 healthy, Masrawy HTTP 403, three RSS candidates, one fresh distinct pre-photo candidate, one older, one same-publisher rejection | Zero *photo-verified* items established from that precise hour; 72h image QA is separate: 2 JPEG inside Word SHA verified |
| 0/3/10 events; photos; dedup; CAS; DST; daily 22:00; volume parts | [Isolated release QA 45161646425](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45161646425): 796/796 offline no-send tests on `b3f9c3a`; latest branch CI must be rechecked after this document update | No production acceptance implied |
| Existing delivery-state proof / authorized mailbox | Private ledger and owner Inbox inspected without modifying either. Details of private message IDs, addresses and content **are not recorded in this public file** | True live hourly owner-only test and direct SMTP sender Sent/IMAP inspection remain **HOLD** |
| Protected read-only triage execution | [One-off attempt 45163118689](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45163118689) failed before job steps could run. Test workflow removed from branch after access block | No Sent read from this workflow; do not change environment branch protection to force access |
| Exact daily capacity semantics | main `MAX_ROLLUP=60` articles, QA `MAX_ROLLUP=360`, target 240/24h; Word parts max 32 and max 7.5MB each | Offline simulated capacity and partial-mail failures tested; actual sender quota/real 240-image production day NOT VERIFIED |

**Root-cause evidence boundary:** The two requested daily cutoffs have no confirmed daily SMTP acceptance in the authorized evidence reviewed. Public `other_held_failure` hides the inner exception; until a *protected, authorized, read-only* original Sent check reports an error code, the first internal failure is unknown. An accepted original periodic mail cannot be treated as acceptance of its unsent daily aggregate. No blind re-send.

**Only activation decision once gates pass:** Select exact reviewed SHA of PR #192; explicitly approve `RASD_HOURLY_REPORTS_ENABLED='true'` and `RASD_DAILY_VOLUME_DELIVERY_ENABLED='true'` after verifying the approved sender, To, CC/BCC, SMTP/IMAP quota, private CAS, original Word SHA, and personal-owner single-message test. Keep the Cairo daily deadline at 22:00 and preserve immutable private ledger. Rollback by reviewed flag change to both `false`; never delete reservations, Force Push, or automatically replay an unknown SMTP receipt.


## إثبات عدم توافق القالب المستلم مع قارئ الإنتاج — 23 نوفمبر

**تم فحص أصلين حقيقيين في Inbox الشخصي المصرح به، دون نقل أي عنوان أو صورة أو MIME إلى GitHub العام:** تقرير دوري مستلم 21 نوفمبر 19:07 بالقاهرة، وتقرير دوري مستلم 22 نوفمبر 18:07 بالقاهرة. كل مرفق DOCX عُرض بصريًا في 3 صفحات: غلاف، تحليل/جدول، بطاقة ناشر وصورة. لا صفحات بيضاء، وصورة واحدة على بطاقة خبر أصلية في كل مرفق.

**سبب برمجي مثبت (وبذلك سبب كافٍ لرفض هذه المرفقات عند وصول التنفيذ إلى مرحلة استخراج Word):** `main/daily_sent_consolidator.py` يبحث عن الفقرة العليا `الأخبار المطابقة`، ويبحث عن `a:blip` داخل `document.paragraphs` فقط. كلا المرفقين الأصليين يحتوي **صفرًا** من هذه العناوين والصور في الفقرات العليا، لكن يحتوي **صورة واحدة داخل بطاقة جدول ذات عنوان مرقم، ووقت نشر، ورابط واحد**. بالتالي مسار `main.extract_sent_originals` سيرفضهما بـ `daily_sent_original_headlines_hold`؛ وسبب الفرق اعتماد قالب جدول الوزارة في PR #190 دون نشر قارئ الجدول في `main`. This is verified structural incompatibility, **not a claim that dedicated sender IMAP successfully fetched each message in the live failed run**.

**الإصلاح موجود في الفرع المنعزل:** `daily_sent_consolidator.py` في PR #192 يستخدم `is_interval_ministry_grid` ثم `extract_sent_grid_originals` من `rasd_daily_grid_extractor.py`، ويتحقق من صاحب الخبر والتاريخ والرابط وصورة JPEG والهوية والبصمة. أُضيف الاختبار الصناعي `test_new_real_style_breaks_old_paragraph_extractor_but_grid_recovers`، ليؤكد أن القالب الجديد لا يحتوي العنوان/الصورة في موضع القارئ القديم بينما القارئ الجديد يستخرج الصورة والهوية الصحيحة. **لا بيانات بريد خاصة في المستودع أو الاختبارات.**

**مطلوب لإغلاق السبب الجذري لكل رسالة فعليًا:** نتيجة قراءة Sent لدى حساب المرسل المخوّل فقط، والتحقق من أول `Message-ID` يتعذر أو ينجح استخراج ملفه؛ إذا تعطل IMAP قبل تنزيل المستند، فهناك عائق إضافي غير محسوم. لا توجد حجوزات يومية ليومي 21 أو 22؛ لذلك لا تعاود الإرسال دون تفويض إنتاجي منفصل.



## مستجدات 23 نوفمبر 2026 — قبول Word الحقيقي وإصدار اليومي المنفصل

هذه النتائج الجديدة لا تمثل تفويض تشغيل أو إثباتًا للنسخة الساعية، ولا تتضمن صور Inbox أو عناوين بريد أو بيانات السجل الخاص.

| بند جديد | دليل تم التحقق منه | الحكم |
|---|---|---|
| مصدر الكود | `main@6715b41`; هذه الفرع الساعي لم يدمج بعد | أساس الإصلاح منفصل |
| اختبار قارئ Word على مرفقات Inbox الفعلية | 12 ملفًا مؤرشفًا محليًا، 13 صورة أصلية/رابط؛ `main` استخرج 7/13؛ قارئ هذه الفرع 13/13. يوم 21: 6/8 ثم 8/8؛ يوم 22: 0/2 ثم 2/2؛ 23 نوفمبر 13:07: 0/2 ثم 2/2؛ قالب 20 القديم 1/1 في النسختين. روابط وبصمات كل صورة وترتيبها طابقت Word | PASS للمدخل المحلي، وليس إثبات Sender Sent |
| نسختا التقريرين التجريبيتان | أعيد بناء نافذة يوم 21 بعدد 8 أخبار/8 صور، ويوم 22 بعدد 2 خبر/2 صورة، من **Inbox المالك فقط**؛ 8 و2 روابط فريدة، وكل صور JPEG مطابقة SHA-256؛ مراجعة بصرية 2 و1 صفحة. بيانات الملفات خاصة خارج GitHub | PASS إعادة البناء محليًا؛ لا SMTP ولا CAS |
| إصلاح اليومي المستقل | [PR #193](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/193) من main يتضمن قارئ البطاقات + توافق القارئ القديم، ولا يغيّر جدولة أو سعة أو مستلمين أو مفاتيح ساعية. [747/747 no-send](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45181832963) على `ed83ea944cf496c181be8a97bb665b92a28a8040` | PASS، Draft وغير مدمج |
| فحص Gmail Sent محمي من مسار معتمد سابقًا | [الوظيفة القديمة المعتمدة على main، إعادة تنفيذ attempt 2](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/40093969919): `VERIFIED_READ_ONLY`، صورتان، `EMAILS_SENT=0`، `PRIVATE_LEDGER_WRITES=0` | PASS لعينة قديمة؛ لم تستهدف كل رسائل 21/22 |
| رفض تشغيل فرع PR192 المحمي | [Run 45163118689](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45163118689)، `ref=release-rasd-hourly-contract-20261121`، `environment=rasd-production`، فشل job بلا خطوات `steps=[]`؛ سجل نص السبب لم يُتح عبر الموصل، فلا يجوز الجزم بقاعدة الحماية التي رفضته. ملف التشخيص المؤقت أزيل | HOLD؛ لا تعديل لحماية البيئة |
| سعة اليومية الساعية | `MAX_ROLLUP=360` خبرًا مقابل 60 على main، مستهدف 240 خبرًا/اليوم. 32 جزء Word كحد أقصى و7.5MB للجزء؛ **كل جزء رسالة SMTP منفصلة في التصميم التجريبي**. العدد الفعلي يتحدد بأحجام الصور، وليس 240/حد ثابت. تصالح كل الأجزاء المقبولة قبل أي استرداد | PASS اختبارات no-send، actual quota and volume owner mail HOLD |
| الاختبار الشخصي الساعي | لم يُجرَ إرسال واحدة من فرع الساعي عبر صاحب الحساب وإعدادات To-only؛ لا Inbox اختبار جديد ولا تحقق من Cc/Bcc لرسالة فعلية | HOLD |
| قرار النشر | `PR #193` إصلاح اليومي أولًا بمراجعة أثره؛ بعد دمجه يجب تحديث/إعادة اختبار `PR #192` حتى لا يرجع توافق اليومي؛ تفعيل الساعي بتفويض منفصل فقط | HOLD |

**عائق الوصول المحمي:** يمكن للمالك مراجعة إعدادات البيئة من
`https://github.com/Hatem1984/RASD-Cloud-Monitor/settings/environments`
ثم `rasd-production`، خصوصًا قواعد deployment branches/reviewers. لا تضع أسرار الإنتاج في workflow فرع تجريبي ولا توسّع قائمة الفروع المسموحة لمجرد تسهيل الاختبار. الطريق المفضل هو تشخيص قراءة فقط من main ضمن صلاحياته المعتمدة، بعد مراجعة التغيير، دون SMTP.

**خطة الرجوع:** اليومي عبر revert عادي للـcommit المعتمد بعد مراجعة السجل، دون Force Push أو حذف حجوزات. الساعي غير مفعل أصلًا؛ إبقاء `RASD_HOURLY_REPORTS_ENABLED=false` و`RASD_DAILY_VOLUME_DELIVERY_ENABLED=false` يضمن بقاء النظام على المواعيد والسعة الحالية إلى حين قرار التفعيل.


## 23 نوفمبر 2026 — بوابة منع تقرير تاريخي قبل دمج Word اليومي

**قرار قراءة الإنتاج قبل الدمج:** عند الساعة 19:46 القاهرة يوم 23 نوفمبر 2026، يحدد `main.rollup_recovery` اليوم 22 نوفمبر 2026 (الفترة من 21 نوفمبر 22:00 حتى 22 نوفمبر 22:00). سجل CAS الخاص في قراءة مخولة فقط لا يحتوي مفتاحًا يوميًا لليوم 21 أو 22 أو 23؛ ولم يُثبت قبول SMTP يومي مستقل. إصلاح قارئ Word وحده قد يؤدي إلى إرسال التقرير التاريخي غير المفوض في أول دورة 19:xx/20:xx. لذلك **لا دمج منفرد لـ #193 قبل بوابة الأمان**، ولا إنشاء حجز وهمي أو حذف أو تعديل لأي إدخال في السجل.

**اقتراح حماية مستقل، غير منشور بعد:** [PR #194](https://github.com/Hatem1984/RASD-Cloud-Monitor/pull/194) يوقف `rollup_recovery` إذا مضت أكثر من 4 ساعات منذ موعد آخر 22:00 القاهرة، **قبل أي وصول للأسرار أو CAS أو SMTP**. يظل `rollup` اليومي الرسمي 22:00، وكذلك الاسترداد في الساعة 22:07 حتى 02:00 في الليلة الجديدة. [740/740 no-send على `1849f45c`](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/45232141304)، مع اختبار المسارات الرئيسي والاحتياطي وCloudflare في ساعة نشر مماثلة. يحتاج تغيير السياسة موافقة مراجعة قبل دمجه؛ عند المراجعة يجب دمج #194 أولًا ثم #193 بتوقيعه الأصلي `ed83ea94`.

**الأول المستحق بعد الحماية ودمج Word، إذا تم نشرهما في 23 نوفمبر قبل 22:00:** التقرير اليومي ليوم **23 نوفمبر** عند 22:00 القاهرة. لا توجد أي نتيجة تسليم مثبتة لهذا اليوم حتى الآن. الإرسال لا يصبح ناجحًا إلا عند فحص Sent وCAS وقبول SMTP ثم المرفق الواصل في Inbox مع مطابقة الأخبار وروابطها والصور.

**الساعي باقٍ مستقلاً:** PR #192 لا يدمج ولا يُفعل، ولا يجوز ربط نجاح PR #193 باعتماد 10 ناشرين/أحداث في ساعة أو بحصة SMTP للـ32 جزءًا. اختبار إرسال المالك الوحيد من المسار المرشح مع CC/BCC فارغين لم يتم؛ الاحتفاظ بقيمة `false` لكلا المفتاحين لحين الإثبات والتفويض.
