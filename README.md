# Tenor

**A public register that flags an output which passed every rule yet betrayed its brief.** An intent-fidelity primitive for GenLayer, with a live register.

An agent output can clear every mechanical check it was given, no banned words, the right length, the right format, and still read wrong: off-tone, off-topic, quietly selling something the brief forbade, missing the point it was made for. That gap, between the letter of the rules and the intent of the brief, is exactly what no ordinary check can see. Tenor registers a brief, the intent and voice an output was meant to honour, and lets anyone submit a public output produced for it. A round of GenLayer validators reads the output against the brief and rules whether it is faithful or off-brief, assuming the mechanical rules already pass. If the output betrays the brief, the brief takes a strike.

## How it works

1. **`open_brief(title, brief)`** — a brief: the intent and voice an output is meant to honour. Bound to `gl.message.sender_address`. Starts clean.
2. **`check(brief_id, output_url)`** — open to anybody. It names a public page carrying an output produced for the brief. The contract **fetches it** and a GenLayer round returns `OFF_BRIEF` / `ON_BRIEF` / `UNCLEAR`, told to assume every mechanical rule already passes and to judge only fidelity to intent and voice. `OFF_BRIEF` leaves a permanent **strike** on the brief and marks the owner; `ON_BRIEF` leaves it clean and counts a clean check; `UNCLEAR` changes nothing.
3. **`record(address)`** — the owner's record: briefs opened, and off-brief strikes accrued across them.

Reads: `brief(id)`, `history(id)`, `get(id)`, `size()`, `page(start, count)`.

## Why it cannot be gamed

A brief is a standing channel, not a single claim: it is never closed, and every off-brief output is a **permanent** strike. Only an `OFF_BRIEF`, drawn from an output's **own** public text, moves anything, and it is the negative. A brief with no strikes is not a certificate of quality; it only means nobody has yet shown an output that betrays it, and that standing can never be manufactured, only left intact. Strikes can never be cleared, by the owner or anyone, and a clean tally does not offset them. `ON_BRIEF` and `UNCLEAR` move no reputation, and an unrelated, unreadable, or not-found page never strikes anyone. Every check is kept, append-only, on the brief.

## Why it needs GenLayer

Whether an output honours a brief's intent and voice, when it already satisfies every explicit rule, is a judgement over real-world text that no ordinary contract can make and no single referee should be trusted with. GenLayer validators each fetch the output and reach consensus on one categorical field; the strike is built from the output's own text, read in the round.

## Tests

`python tests/tenor_rules.py` — the rules exercised through the real `open_brief()` and `check()` on a Tenor built against a stub of the runtime, with the output and verdict controlled. It proves only an `OFF_BRIEF` strikes a brief, an `ON_BRIEF` leaves it clean, an unreadable or not-found output never strikes anyone, the brief is put in front of the round, the round is told the mechanical rules pass, a brief is never closed and keeps accruing strikes, strikes never clear, and history is preserved. 22 checks.

## Live

- **Contract (GenLayer Asimov):** `0xBCB73B7036a7E702455929E1fB63Ea04EfAf8c1E`
- Explorer: https://explorer-asimov.genlayer.com/address/0xBCB73B7036a7E702455929E1fB63Ea04EfAf8c1E
- **App:** https://jspiiv.github.io/tenor/ — reads the register from chain without a wallet; opening a brief and checking an output are transactions on Asimov.

## Proven on Asimov

`scripts/prove.mjs`, `results/proved.json`. A brief for a warm, no-upsell support voice, checked against outputs in `docs/`:
- an output that honours the brief (`output-on-brief.txt`) → **ON_BRIEF**, the brief stays clean.
- an unreadable output → `UNCLEAR`, the brief stays clean.
- an output that breaks no rule but is cold, shaming, and pushes the paid upgrade the brief forbade (`output-off-brief.txt`) → **OFF_BRIEF** → a **strike**, and the owner's `record` gains one.
- the brief is never closed; `history` keeps every check.

## Where it stops, plainly

It judges what a public output shows against a stated brief, not the work behind it: write a brief that actually names the intent and voice to honour, and point at an output page a third party can open. It records a signal, not a verdict on quality: a brief left unstruck only means nobody has shown an output that betrays it.

## Licence

AGPL-3.0-or-later.
