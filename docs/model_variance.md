# brian: what do you figure the delta will be when i change models?   deepseek -> gemini?

# claude: Honestly?
The structure delta should be near-zero — and that's the whole point of what you built
tonight. The SKILL, the audit_state.json schema, the validate_state gate, the fixed 14 tabs, the
intent+hints inspection — all of that normalizes whatever model is driving. Swap DeepSeek for Gemini and
you'll still get the same shape: 14 tabs, the same findings schema, the same rollup. You've
deliberately factored the prompting-and-format variance out, which means the swap is now a fairly clean
A/B of model judgment, not harness noise. That's a much better experiment than most people ever get to
run.

So the delta lands almost entirely in the substance, and I'd bet on four axes:

1. Severity calibration — the biggest and most annoying one. One model's "High" is another's "Medium."
DeepSeek gave you 10 Critical / 21 High; Gemini could easily reshuffle that distribution meaningfully
even on identical underlying issues. Since your rollup sorts and prioritizes by severity, this directly
reshapes the "grab one first" list. Cross-model severity agreement is notoriously loose.
2. Grounding / evidence fidelity — the schema demands evidence: file:line, but models differ a lot in
whether that's a real citation or a plausible-sounding hallucination. This is where your false-positive
rate diverges, and it's the axis that most affects whether the  team trusts the list. Different
failure mode, not just different volume.
3. Domain emphasis & blind spots — models have characteristic strengths. You may find Gemini sharper on,
say, the GCP IAM / K8s RBAC minutiae and the Go operator, while DeepSeek leaned harder into
reasoning-heavy areas (agentic surface, escalation paths). Expect the distribution across the 11 domains
to shift, and each model to quietly under-cover something.
4. Depth vs. breadth — some models emit many shallow findings, others fewer deep ones. Same 71-ish count
could hide very different value density.

Here's the fun part: you already built the instrument to measure this instead of guessing. Run Gemini on
the same repo/date into a parallel dir, and diff_reports / whats_changed (diff_findings over the two
audit_state.jsons) will hand you added/removed/changed findings between the two models directly. And the
corrections ledger is exactly where human review adjudicates which model was right — run that a few
times and you'll have empirical data on which model to trust for this codebase, per domain.

My gut prediction: comparable order of magnitude of findings, real divergence in severity labels and the
high-severity set, and a different false-positive profile — with the framework making all of that
visible and diffable rather than lost in noise. Which is the actual win: you're no longer comparing
vibes, you're comparing findings with evidence.

