# Gate 66 — exact saved terms in first-party Ministry article lead (no keyword expansion)

20 October 2026 (Africa/Cairo). Base `main` `6c9bfbd648c606bd2ff24ff5e6097f0efc1c03cf`. Stage2 #42 **remains OPEN** until distinct completed dates, real screenshots, owner-only review and visual human approval; this gate changes matching logic, not accepted evidence.

## Reproduced REAL blocker

- The **original publisher** `https://mped.gov.eg/News/NewsList?lang=ar&pageNum=1&typeId=0` currently shows authentic publisher card `div_7270`, with its original `newsDetails('7270','True',...)` click action and publisher date **19 October 2026**. The same page also shows 17 October card `div_7269`. There is no need to guess an article ID, use a search result as a discovery feed, change endpoint, or substitute an AdminPanel URL.
- Official original article: `https://mped.gov.eg/singlenews?id=7270&lang=ar`. **Title** starts with `وزيرا التخطيط والاستثمار`, which is NOT one of the four saved whole-phrase matches (`وزارة التخطيط`, `وزير التخطيط`, `وزيرة التخطيط`, `التخطيط والتنمية الاقتصادية`). Its **first original publisher paragraph** contains `وزير التخطيط والتنمية الاقتصادية`, an **EXACT** saved phrase. This is editorially about the Ministry; no broad economic term is needed.
- Two owner-only hosted full-Cairo-day 19 October runs: [39440812022](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39440812022), [39443230163](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39443230163). Both found Hapi10 / Al Masry original plural RSS20 / official 20 links (healthy 3/3) but `official_offday=19`, `official_same_day=0`, `rss_matched_on_day=0` and `HOLD`; no Word. The original Ministry browser adapter **checked only headline** while the RSS adapter already qualified exact saved phrase in native publisher title OR description. `EXCLUDED_NON_MATCHING_TERM` items are not counted as `official_offday`, consistent with 19 off-day originals plus one excluded on-day article.
- A browser-automation DOM summary claiming new unrelated AdminPanel Article.View IDs **was not reliable**; the independently fetched actual original NewsList HTML for `div_7270` contains **the previously approved** `newsDetails('7270','True',...)` format. Do **not** make changes based on unverified synthetic HTML summaries.

## Surgical match correction

New helper `original_headline_or_intro_matches(body, headline, saved_keywords)` checks the genuine publisher h1/title OR the **first 1,600 normalized characters AFTER that identical title** in the same already-loaded original-page body, using the **existing exact four normalized phrases**. It excludes unrelated site navigation before the original h1, and unrelated related-story/footer text beyond this bounded original lead; no whole-web/general economy keyword, new original source, foreign search result, guessed ID, alternate feed or unverified screenshot introduced.

Both stages must agree: `OfficialPageDriver.inspect` validates URL, original headline and date and then the bounded exact phrase before it captures; `official_ministry_source._read_original` repeats the same saved-phrase check on the SAME actual original browser page, then requires original publication day equal to target, real screenshot validation and SHA digest. All existing source/page/date/original capture / Word / owner encryption / MIME NO-SEND fail-closed gates remain. An isolated test uses **synthetic** text mirroring the publisher's publicly visible 19 October title/first paragraph, and tests footer-only/nav-only rejection, wrong dates, negative generic economy, JPEG validation and both code paths.

## Evidence limits

This regression test is only an engineering fix. **No actual 19 October Word has yet been machine-accepted under the new logic**, and neither 18 nor 19 October counts as a second accepted date merely because the code passes tests. Follow up with ONE deliberate owner-manual completed-day `yesterday` run on merged main **on 20 October only**, if GitHub actor is Hatem1984 and no concurrent run exists. Require all 3 original sources, original JPEG/page rendering, the exact owner-packed SHA from Gate65, ciphertext-only artifact, and local owner's actual private-key decryption/visual review. Never auto-sign human acceptance.

No real Gmail, R2, ledger writes, cron, production source activation or public plaintext.
