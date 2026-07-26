---
name: pack-triage
description: Use when a new sample pack lands in the ATONOMUS drop folder — scans, license-gates, sorts files into the 02_ enforced structure, and flags CC0/permissive files for Training_Data.
---

# Pack Triage

## When to use
A new audio pack (zip or folder) appears in 02_ATONOMUS_Music_Dataset or is handed
to you in a task mentioning samples/packs/triage.

## Inputs it expects
- The pack path; the 02_ enforced structure (genre/{Drums,Bass,Melodies,FX,Loops,OneShots})
- 02_/README.md license conventions; Indexes/pack_index.md

## Steps
1. Scan: verify archive integrity; on Windows confirm Defender-clean before extraction.
2. License gate: locate the pack's license text. CC0/royalty-free → eligible for
   Training_Data. Unclear → tag `[NEED: license]`, keep performance-only.
3. Classify each file by type (drums/bass/melody/FX/loop/one-shot) into the matching
   genre subfolder. Unsure → genre/General, never guess a genre tag into the index.
4. Flag permissive files: copy (not move) into Training_Data/<Genre>/.
5. Index: append one row per file to Indexes/pack_index.md (name, type, genre, license, source pack).
6. Ledger: one line — pack name, file count, training-eligible count.

## Output contract
Sorted files in 02_, updated pack_index.md, ledger entry, handoff noting any
[NEED: license] holds.

## Failure modes
Corrupt archive → stop, ledger the failure, leave the archive untouched. License
ambiguity → NEVER enters Training_Data; loud [NEED] in the handoff.
