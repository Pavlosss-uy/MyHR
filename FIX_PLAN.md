# MyHR — Fix Plan (Simple Language)

This is the to-do list that came out of the technical audits, written plainly.
Each item says: **what's wrong**, **why it matters**, and **how to fix it**.

Legend: 🔴 critical · 🟠 important · 🟡 nice-to-have · ✅ already done

---

## ✅ Already fixed (this session)
- **Database fills up after 100 interviews** → now auto-cleans each interview's leftover
  search data when it ends. (The thing we hit manually before.)
- **Dead/duplicate files** (broken copies, scripts with a teammate's hardcoded paths) → deleted.
- **Misleading "survives restart" comment** → corrected to the truth (Firestore is what saves state).
- **Two interviews at once could corrupt each other** → added safety locks on shared memory.
- **No way to check if the app is healthy** → added a `/health` check.

---

## Phase 1 — Critical (DONE ✅)

### ✅ 1. The answer-scoring AI is fed the wrong data — FIXED
- **Problem (simple):** The model that scores answers (relevance / clarity / depth) was *trained*
  using one method of turning text into numbers, but at *runtime* it's given numbers made a
  **completely different way**. The sizes match, so nothing crashes — but it's like training
  someone to read English and then handing them Chinese in the same-shaped book. Its live scores
  are basically random.
- **Why it matters:** This model is part of every candidate's final score, and the impressive
  "0.95 accuracy" number was measured on the *training-style* data, not what the app actually uses.
  So that number doesn't hold up in real use.
- **What was done:** `train_evaluator.py` now re-encodes each answer with the exact inference model
  (all-mpnet-base-v2, answer-only) instead of the stale MiniLM features; retrained → Spearman
  0.94/0.94/0.93 measured on the *real* representation. The checkpoint is now stamped with its
  embedder name and the registry **refuses to load a mismatched model**.

### ✅ 2. The interview can make up CV details when search fails — FIXED
- **Problem (simple):** Questions are supposed to be based on the candidate's real CV. But if the
  CV search comes back empty (bad CV, missing data), the system **still asks a confident question**
  and the AI can invent experience the person never had.
- **Why it matters:** The candidate gets asked about skills/projects that aren't theirs, which makes
  the whole interview and score unfair/wrong.
- **What was done:** added a grounding check in `agent.py`. If retrieval returns no real CV, the
  interviewer now asks a **safe, CV-agnostic question** (rotated so it doesn't repeat) and logs a
  warning — it never generates a question against empty/placeholder CV context. The drill-down path
  already used conversation history, so it was safe.

---

## Phase 2 — Important (strengthens your thesis credibility)

### 🟠 3. The AI grades itself (circular logic)
- **Problem (simple):** The model that scores answers learned from grades written by an AI (the LLM)
  — and at runtime that **same AI** also grades. So the "second opinion" isn't really independent;
  it just echoes the LLM.
- **Why it matters:** An examiner can call this out: "how do you know it's actually right, not just
  agreeing with itself?"
- **The fix:** Run the **human rating study** that's already built (you just need a few people to
  score ~40 answers), then report how well the AI agrees with humans. That gives you a real,
  independent number.
- **Effort:** 30 min of setup + a few people rating.

### 🟠 4. No final "exam" for the models (only practice tests)
- **Problem (simple):** Every model is checked on data it could peek at during tuning. There's no
  truly held-out final test set, so the reported scores are a bit too optimistic.
- **Why it matters:** Real accuracy is likely a little lower than reported; a reviewer will ask about
  the test set.
- **The fix:** Split data three ways (train / validate / **test**) and report the untouched **test**
  numbers.
- **Effort:** ~half a day across the models.

### 🟠 5. Voice-emotion model is half-trained on rough labels
- **Problem (simple):** The emotion-from-voice model only finished **1 of its 5 planned training
  rounds**, and the emotion labels were force-fitted (e.g. "calm" relabeled as "confident",
  "sad" as "hesitant") — approximations, never checked by humans.
- **Why it matters:** The mood signal in reports is weakly grounded.
- **The fix:** Finish all 5 training rounds; sanity-check the label mapping against a few human-rated
  clips; merge emotions that overlap too much.
- **Effort:** ~1 day (mostly training time).

### 🟠 6. The other scorer also has a train-vs-runtime mismatch
- **Problem (simple):** A second scoring model was trained with **fake "tone" numbers** but is given
  **real** tone numbers at runtime — again, slightly different worlds.
- **The fix:** Train it with real tone numbers (run the real voice model on the audio), or drop the
  tone input and note it.
- **Effort:** ~half a day.

---

## Phase 3 — Nice-to-have (polish)
- 🟡 **Search blends keyword + meaning 50/50.** For CVs, meaning should usually count a bit more
  (e.g. 60/40). Easy weighting tweak.
- 🟡 **Difficulty engine aims for "average" answers (~65%).** It treats a brilliant answer the same
  as a weak one. Reshape the reward if you want it to reward strong candidates.
- 🟡 **Small model design nits** (missing normalization layers, a too-large margin setting). Minor
  quality improvements.

---

## Phase 4 — Production hardening (only if you deploy for real)
- 🟠 **"Audio saved to the cloud" isn't true** — it saves to the local disk. Wire up real cloud
  storage (S3) before real users.
- 🟠 **Logging is just `print()`** — add real logging + basic monitoring so you can debug in
  production.
- 🟡 **Watch for drift** (incoming CVs/answers changing over time), add model lineage tracking, and
  load-test many interviews at once.
- 🟡 **Merge `enterprise` → `main`** so teammates stop pulling the old broken version.

---

## Suggested order if time is tight (before defense)
1. **Fix #1** (evaluator data mismatch) — makes your scores actually mean something.
2. **Fix #2** (RAG hallucination guard) — never invent a candidate's CV.
3. **Fix #3** (run human study) — gives you one honest, independent accuracy number.
4. **Fix #4** (test sets) — so every number you present survives scrutiny.

Everything in Phase 3–4 is real but won't change whether your core claims hold up under questioning.
