# RASD — Gate 28: bind publisher screenshots to the correct Word article

**Date:** 18 October 2026  
**Scope:** Cloud-only, offline regression and strict final Word evidence validation. No source-list expansion, real Gmail, scheduler, private bucket, or account changes.

## Finding reproduced on the Gate 27 baseline

Gate 27 required every displayed Word JPEG byte digest to occur in the list of independently captured publisher-page digests. But its `sorted()` multiset comparison did not enforce the association between a specific article's position and its corresponding screenshot. Two authentic but swapped pictures passed and produced an incorrect `READY` final Word.

A new synthetic-only offline regression, `test_swapped_article_screenshots_are_hold_even_with_same_byte_digests`, demonstrated the problem: [test-first red CI](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39102045662) reported 176 tests, one failure: `'READY' != 'HOLD'`, and one conditional skip.

## Correction and acceptance boundary

- Resolve each `word/document.xml` drawing through the DOCX internal image relationship and validate its exact media SHA-256, preserving drawing order.
- Compare the resulting **ordered** digest list against independently captured evidence rows, whose order matches the article iteration in `daily_report.render_docx`.
- Reject a Word whose images have been exchanged between article paragraphs, even when every media file is genuine and its digest remains unchanged.
- Retain Gate 27 checks for ZIP integrity, missing or orphan JPEG media, reused picture targets, unsupported/external relationship targets and same-day stale file prevention.
- Failed evidence binding must produce `HOLD`, remove the attempted final Word and never reach a private archive writer.

This is an **offline engineering security/accuracy acceptance only**, not proof that a new live news item was captured. Original-publisher source failures, real protected private storage, authenticated Gmail and scheduling remain `HOLD` until separately approved and proven.
