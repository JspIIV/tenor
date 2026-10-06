# Tenor

**Hold an author to a brief they published against, judged on their own on-chain words.** An intent-fidelity primitive for GenLayer, with a live register.

An agent output can clear every mechanical check it was given, no banned words, the right length, the right format, and still betray the brief it was made for: off-tone, quietly selling something the brief forbade, missing the point. That gap, between the letter of the rules and the intent of the brief, is what no ordinary check can see.

The subject of any judgement here is never an arbitrary page a stranger points at. An author **publishes** an output on chain, in their own transaction, claiming it honours a standing brief. The output is their own bytes under their own address: they cannot disown it and no one else can fabricate it for them. Anyone may then **challenge** that publication, and a round of GenLayer validators reads the output against the brief, told to assume the mechanical rules pass, and rules whether it is faithful or off-brief. An off-brief verdict strikes the author.

## How it works

1. **`open_brief(title, brief)`** — a brief: the intent and voice an output is meant to honour. Bound to `gl.message.sender_address`.
2. **`publish(brief_id, output)`** — an author commits an output on chain, claiming it honours the brief. The **author is the message sender, by construction**, and the output is stored as their own bytes. Starts `PENDING`.
3. **`challenge(pub_id)`** — open to anybody. A GenLayer round reads the author's on-chain output against the brief and returns `OFF_BRIEF` / `ON_BRIEF` / `UNCLEAR`, told to assume every mechanical rule already passes and to judge only fidelity to intent. `OFF_BRIEF` **strikes** the author (once and for good); `ON_BRIEF` clears the publication; `UNCLEAR` leaves it open.
4. **`record(address)`** — briefs opened, outputs published, and off-brief strikes taken.

Reads: `brief(id)`, `publication(pub_id)`, `briefs_page(start, count)`, `page(start, count)`, `size()`.

## Provenance, settled by construction

The gap a steward named in the first version, that anyone could point at an unauthenticated page and trigger a reputational flag, is closed here, not patched. The judged text is exactly what the author committed in their own transaction; the brief is exactly what its owner published. **The contract fetches nothing from the web**, so there is no page to forge and no endpoint to spoof. A third party cannot attach an output to an author who did not publish it, because the author is always the message sender. The tests cover the fabrication and impersonation cases directly.

## Why it cannot be gamed

A brief is a standing channel, never closed, and every off-brief publication is a **permanent** strike on its author. Only an `OFF_BRIEF`, drawn from an output the author themselves committed, moves anything, and it is the negative. An author cannot disown a struck output, cannot clear a strike, and cannot force an `ON_BRIEF`, because they do not control the verdict. A clean tally never offsets a strike. Every challenge is kept, append-only.

## Why it needs GenLayer

Whether an output honours a brief's intent and voice, when it already satisfies every explicit rule, is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each judge the on-chain output and reach consensus on one categorical field.

## Tests

`python tests/tenor_rules.py` — the rules exercised through the real `open_brief()`, `publish()` and `challenge()` on a Tenor built against a stub of the runtime, with only the verdict controlled. It proves provenance by construction (an output is always authored by the sender and cannot be attributed to anyone else, and no web page is ever fetched), only an `OFF_BRIEF` strikes, an `ON_BRIEF` clears, `UNCLEAR` leaves a publication open, a settled publication cannot be re-judged, strikes never clear, a brief accrues strikes across its publications, and history is preserved. 25 checks, covering the fabrication and impersonation cases.

## Live

- **Contract (GenLayer Asimov):** `0x8CD569C27DA66b17d6EA6E9C2DbD8Ea53da60Adc`
- Explorer: https://explorer-asimov.genlayer.com/address/0x8CD569C27DA66b17d6EA6E9C2DbD8Ea53da60Adc
- **App:** https://jspiiv.github.io/tenor/ — reads the register from chain without a wallet; opening a brief, publishing, and challenging are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. A warm, no-upsell support-voice brief, with two outputs the author published on chain:
- an output that honours the brief → challenged → **ON_BRIEF**, cleared, no strike.
- an output that breaks no rule but is cold and pushes the paid upgrade the brief forbade → challenged → **OFF_BRIEF** → the author takes a **strike**.
- a settled publication cannot be challenged again; the author is the on-chain publisher, never the challenger.

## Where it stops, plainly

It judges what an author's own committed output shows against a stated brief, not the work behind it: write a brief that names the intent and voice to honour, and publish the output you stand behind. A strike means a round found that output betrayed the brief; a brief left unstruck only means no output committed against it has yet been shown to betray it.

## Licence

AGPL-3.0-or-later.
