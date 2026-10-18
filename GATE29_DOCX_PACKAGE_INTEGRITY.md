# RASD — Gate 29: unambiguous DOCX package and screenshot relationships

**Date:** 18 October 2026  
**Scope:** Offline DOCX media package integrity; no Gmail, private state, scheduler, publisher permissions or billing changes.

## Problems detected after Gate 28

1. Python's ZIP reader can resolve duplicate archive entry names by the last matching entry. A DOCX with duplicate `word/media/*` parts therefore passed integrity checks despite ambiguous OPC part identity. Consumers may interpret ambiguous packages differently.
2. The validator inspected image relation `Target` but not `TargetMode`. A relative-looking `media/image1.jpg` relation explicitly marked `TargetMode="External"` passed even though the document no longer unambiguously references its internal captured screenshot.

## Test-first evidence

Two synthetic-only, offline negative regressions demonstrated both failures on the prior implementation: [red CI](https://github.com/Hatem1984/RASD-Cloud-Monitor/actions/runs/39102426177) — 178 tests, **two intended failures** with `'READY' != 'HOLD'`, and one dependency-conditional skip.

## Correction

- Reject **any duplicated ZIP member name** before resolving DOCX XML or image media, even when repeated bytes are identical.
- Reject image relationships whose `TargetMode` is anything other than internal; absence is treated as the standard implicit internal mode.
- Preserve Gate 27 and Gate 28 protections: actual captured JPEG digest, drawing order bound to article, archive integrity, unique picture targets, no orphan media, safe HOLD and no stale final Word.

## Acceptance boundary

For either ambiguity, the attempted final Word is **HOLD**, never treated as an accepted attachment or passed to the optional private archive writer. A passing read-only CI suite proves this local validation rule, not source-wide live publisher coverage, real protected Gmail delivery, private storage restore or scheduler approval.
