# Next steps: learn from first use before making stronger claims

This is a maintainer plan, not a list of completed user trials or scheduled jobs.

## Completed foundations

- Claude upload skill 0.2.0 supports interest/link retrieval, conversation ranking
  and HTML/CSV/JSON/RSS export, with a documented network/web-tool fallback.
- Saved functionality checks used two real links and a separate three-paper
  interest search. They are not independent accuracy tests.
- [PR #27](https://github.com/Eliot5566/JEV-Paper-Radar/pull/27), contributed by
  erSpell and merged by Eliot5566, completed the leaderboard-only profile issue.

## Next small trial round

Invite up to five volunteers across a few research fields using
[the first-run guide](first-run.md). Five is a target, not an existing user count.
Do not publish participant names or private research. The optional public form
collects version/environment, route, outcome and one concrete observation.

Review outcomes for installation, retrieval, opening the files and usefulness
of reasons. Count unknowns and failed attempts. Separate metadata-API success
from web-tool recovery, and real abstracts from labelled summaries. No analytics
or automatic uploads are introduced. Time savings or accuracy need actual data;
do not infer them from successful exports or GitHub stars.

Choose the next product change from repeated concrete blockers. Ranking quality
needs independent human relevance labels that include selected and unselected
papers, followed by a separate held-out batch; it is not established by retuning
on the same examples.

## Existing reliability and security reports to investigate

- [Issue #2](https://github.com/Eliot5566/JEV-Paper-Radar/issues/2): distinguish a
  genuinely quiet day from a persistently empty or stale arXiv feed. Reproduce
  valid emptiness, schema changes and stale records first; add an explicit,
  configurable alert without treating every quiet day as an error. Still open.
- [Issue #1](https://github.com/Eliot5566/JEV-Paper-Radar/issues/1): a general
  notice about untrusted text influencing Jev judgements. The notice explicitly
  does not prove exploitation of this repository. Treat it as a threat-model and
  evidence-gathering task; do not declare it fixed or validated without evidence.

These items are not resolved by publishing the real-paper showcase. They remain
visible work rather than marketing claims.

## Outreach and the OSS application

Use the public real-paper walkthrough when sharing. External curated-list
submission remains pending the maintainer's requested final confirmation; avoid
duplicate submissions and respect each list's contribution rules. The Claude
for Open Source application remains deferred at the maintainer's request.
Any later application should distinguish maintainer tests, actual external
contributions, user feedback and independently measured results.
