# qa_agent — closed-book QA agent + judge

Answers the Neufert knowledge probes (`knowledge/knowledge_probes.jsonl`) with several
models, as multiple choice and as open questions, and grades the answers.

```bash
.venv/bin/python -m qa_agent.run_probes --models sonnet,luna,gemini,jev --formats mcq,open --limit 5 --shuffle-seed 1
.venv/bin/python -m qa_agent.run_probes --models sonnet --formats open --kids K07,K19   # selected points
.venv/bin/python -m qa_agent.run_probes --formats mcq --shuffle-seed 2                  # full set, other option order
```

Output: `runs/qa_probes/<timestamp>/` — `graded.jsonl` (question, answer, grade per item), `answers.jsonl`,
`summary.json` / `summary.md`, `config.json`.

## Models (`qa_agent/config.py`)

| alias | provider | model id | formats |
|---|---|---|---|
| sonnet | Anthropic SDK | `claude-sonnet-5-5` | mcq, open |
| luna | OpenAI SDK | `gpt-6-luna` | mcq, open |
| gemini | Google REST | `gemini-3.8-flash` | mcq, open |
| jev | TypeSafe REST `/v1/systemone` | `jev-latest` | mcq only (decision model: returns a choice + per-option probabilities, no text) |

Keys come from `.env` (`Anthropic_KEY`, `OA_OPENAI_KEY`, `Gemini_KET`, `JEV_KEY`).
Claude runs without the server-side refusal fallback on purpose: a fallback would let a different model answer a
benchmark item. Refusals are recorded as such.

## Answering (`qa_agent/agent.py`)

One call per question, closed book, no tools. MCQ: models may reason but must end with `Answer: <letter>`;
the parser takes the last `Answer: X` or a final bare letter. JEV answers MCQ through a native `choice` question, so its
per-option probabilities are stored (`choice_probs`) — useful for calibration and probing.
`--shuffle-seed` permutes the options per item (controls position bias; run several seeds and average).

## Grading (`qa_agent/judge.py`)

- **MCQ:** rule-based — parsed letter vs the correct option. `unparsed` counts as wrong.
- **Open:** JEV as judge (prompt `v3_both_checks` in `JUDGES`) + a deterministic numeric check.
  - The judge **never sees the reference answer**. Its `state` holds only the question, `source_quotes` (the verbatim
    Neufert sentences), `source_context` (the paragraph around them, ~1200 chars) and the candidate answer. The
    instructions say what not to penalise (terse answers, paraphrase, unit conversion, order, extra explanation) and
    include a short German↔English terminology glossary (schwer entflammbar = flame-resistant, F 30, …).
  - One request asks `verdict` (choice: correct / partially_correct / incorrect), `complete` and `contradicts`
    (yes/no). A confident check overrides a verdict it clearly disagrees with.
  - `numeric` (outside the judge) compares unit-normalised values with the reference answer; together with a low
    verdict margin (< 0.7) it sets `needs_review`.
  - Accuracy counts only `correct`.

## Judge tuning (`qa_agent/judge_tune.py`)

Suite of 1,464 labelled candidates (`judge_tune/suite.jsonl`): per point the gold answer, every accepted form and three
Claude rewrites (paraphrase + unit conversion, verbose, terse) as positives; the three MCQ distractors, a near-miss
(one value changed) and an omission as negatives. Points are split 60/40 dev/holdout; prompts were tuned on dev only.

| judge | dev positives → correct | dev negatives → correct | holdout positives | holdout negatives |
|---|---|---|---|---|
| v1_quotes | 95.0% | 0.0% | 99.1% | 0.3% |
| v2_context | 98.6% | 0.0% | 98.3% | 0.3% |
| v3_both_checks (default) | 100% (437/437) | 0.0% (0/370) | 99.4% (350/352) | 0.3% (1/305) |

Gold answers: 135/135 graded correct. Repeat run: 11/1,464 raw verdict flips, identical final metrics.
Results per run in `judge_tune/report.json`, failures in `judge_tune/fails_*.jsonl`.

## Before trusting the judge

Validate it once against human labels: hand-grade ~60–100 open answers (mix of models and labels), compare with
the JEV verdict (agreement, Cohen's κ, and especially false "correct"), and only then report open-question accuracy.
Re-check whenever the judge prompt or model changes.
