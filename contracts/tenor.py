# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }
"""Tenor: a public register that flags an output which passed every rule yet betrayed its brief.

An agent output can clear every mechanical check given to it, no banned words, the right length,
the right format, and still read wrong: off-tone, off-topic, quietly selling something the brief
forbade, missing the point it was made for. That gap, between the letter of the rules and the
intent of the brief, is exactly what no ordinary check can see. Tenor registers a brief, the
intent and voice an output was meant to honour, and lets anyone submit a public output produced
for it. A round of GenLayer validators reads the output against the brief and rules whether it
is faithful or off-brief, assuming the mechanical rules already pass. Only an off-brief verdict
leaves a mark.

A brief is a standing channel, not a single claim: it keeps running, and every off-brief output
is a permanent strike recorded against it. A brief with no strikes is not certified good; it only
means nobody has yet shown an output that betrays it. Strikes can never be cleared, by the owner
or anyone, and a clean tally does not offset them.

## What it settles, per check

    OFF_BRIEF  the output betrays the brief's intent or voice, though it may break no rule -> a strike
    ON_BRIEF   the output was read and honours the brief's intent and voice -> no strike, counted clean
    UNCLEAR    the output could not be read, or there is too little to judge -> nothing changes

Only OFF_BRIEF strikes, and only from the output's own text. An unreadable or unrelated page
never strikes anyone.

## What it refuses

The brief and its title are fixed when opened and cannot be edited. The owner is bound to the
caller of open_brief, the checker to the caller of check. An output that cannot be judged is
UNCLEAR, never a strike. Every check is kept, append-only, on the brief. No one can remove a
strike or close a brief; a clean count never cancels a strike.

## Where it stops, plainly

It judges what a public output shows against a stated brief, not the work behind it: write a brief
that actually names the intent and voice to honour, and point at an output page a third party can
open. It records a signal, not a verdict on quality: a brief left unstruck only means nobody has
shown an output that betrays it.
"""

from genlayer import *
import json

OFF_BRIEF = "OFF_BRIEF"
ON_BRIEF = "ON_BRIEF"
UNCLEAR = "UNCLEAR"
VERDICTS = (OFF_BRIEF, ON_BRIEF, UNCLEAR)

MAX_TITLE = 140
MAX_BRIEF = 1400
MAX_URL = 300
MAX_PAGE = 6000
MAX_REASON = 300
MAX_QUOTE = 300
MAX_LOG = 60

FETCH_FAILED = "__FETCH_FAILED__"


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _clip(text: str, limit: int) -> str:
    text = str(text).strip()
    return text if len(text) <= limit else text[:limit] + " [...]"


def _whole(value) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return -1


def _addr(value) -> str:
    text = str(value).strip().lower()
    if not text.startswith("0x") or len(text) != 42:
        return ""
    for character in text[2:]:
        if character not in "0123456789abcdef":
            return ""
    return text


def _url_ok(url: str) -> bool:
    text = str(url).strip()
    if len(text) < 8 or len(text) > MAX_URL or " " in text:
        return False
    return text.startswith("https://") or text.startswith("http://")


def _counts_after(verdict: str):
    """Only OFF_BRIEF strikes. Returns (strike_delta, clean_delta)."""
    if verdict == OFF_BRIEF:
        return 1, 0
    if verdict == ON_BRIEF:
        return 0, 1
    return 0, 0


def _field(raw: str, name: str, allowed, fallback: str) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            said = str(obj.get(name, "")).strip().upper()
            return said if said in allowed else fallback
    except Exception:
        pass
    return fallback


def _text_field(raw: str, name: str, limit: int) -> str:
    try:
        text = str(raw).strip()
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
        if isinstance(obj, dict):
            return _clip(str(obj.get(name, "")), limit)
    except Exception:
        pass
    return ""


def _fetch(url: str) -> str:
    try:
        got = gl.nondet.web.render(url)
        page = got if isinstance(got, str) else getattr(got, "body", "")
        if isinstance(page, (bytes, bytearray)):
            page = page.decode("utf-8", "replace")
        page = _clip(str(page), MAX_PAGE)
        if not page:
            return FETCH_FAILED
        if page.strip().lower().startswith(("404: not found", "404 not found", "not found")):
            return FETCH_FAILED
        return page
    except Exception:
        return FETCH_FAILED


def _task(title: str, brief: str, output: str) -> str:
    return f"""Someone published a brief, the intent and voice an output was meant to honour, and is now
checking an output produced for it. Assume the output already passes every mechanical rule it
was given: length, format, banned words, and the like are all satisfied. Judge only whether the
output is FAITHFUL to the brief's intent and voice, or betrays it despite breaking no rule.

THE BRIEF (title: {title}) -- the intent and voice to honour:
{brief}

THE OUTPUT BEING CHECKED:
{output}

Decide one of:
  {OFF_BRIEF} the output betrays the brief's intent or voice: it is off-topic or off-tone, pushes
    something the brief forbids in spirit, misleads, or would not be recognised as honouring the
    brief by the person who wrote it, even though it may break no explicit rule
  {ON_BRIEF} the output was read and honours the brief's intent and voice
  {UNCLEAR} the output could not be read, or there is too little in the brief or the output to judge

Judge intent and voice, not mechanical compliance: an output can satisfy every listed rule and
still be {OFF_BRIEF}. Decide only from what the output actually says. An error page, a "404" or
"not found" notice, an empty page, or a page unrelated to the brief is {UNCLEAR}, never {OFF_BRIEF}.

Reply with bare JSON and nothing else:
{{"verdict": "{OFF_BRIEF}" or "{ON_BRIEF}" or "{UNCLEAR}",
  "quote": "the passage that decided it, or empty",
  "reason": "one sentence naming what decided it"}}"""


class Tenor(gl.Contract):
    """Briefs, each accruing a permanent strike for every output shown to betray its intent."""

    # str(id) -> the brief as JSON, including its append-only check log.
    items: TreeMap[str, str]
    ids: DynArray[str]
    # address -> {"briefs": n, "strikes": n} as JSON.
    records: TreeMap[str, str]

    def __init__(self) -> None:
        pass

    def _bump(self, who: str, briefs_delta: int, strikes_delta: int) -> None:
        raw = self.records.get(who, None)
        rec = json.loads(raw) if raw is not None else {"briefs": 0, "strikes": 0}
        rec["briefs"] = int(rec.get("briefs", 0)) + briefs_delta
        rec["strikes"] = int(rec.get("strikes", 0)) + strikes_delta
        self.records[who] = json.dumps(rec)

    @gl.public.write
    def open_brief(self, title: str, brief: str) -> str:
        """Open a brief: the intent and voice an output is meant to honour. Bound to the caller."""
        owner = gl.message.sender_address.as_hex.lower()
        ttl = _clip(title, MAX_TITLE)
        bodytext = _clip(brief, MAX_BRIEF)
        if not ttl:
            return json.dumps({"ok": False, "error": "give the brief a short title"})
        if len(bodytext) < 12:
            return json.dumps({"ok": False, "error": "write the brief, the intent and voice an output must honour"})

        bid = str(len(self.ids))
        record = {
            "id": bid,
            "owner": owner,
            "opened_at": _now_iso(),
            "title": ttl,
            "brief": bodytext,
            "checks": 0,
            "strikes": 0,
            "clean": 0,
            "last_reason": "",
            "last_quote": "",
            "log": [],
        }
        self.items[bid] = json.dumps(record)
        self.ids.append(bid)
        self._bump(owner, 1, 0)
        return json.dumps({"ok": True, "id": bid})

    @gl.public.write
    def check(self, brief_id: str, output_url: str) -> str:
        """Check an output against a brief: submit a public output produced for it. Open to anybody.

        The contract fetches the output in the round and consensus rules OFF_BRIEF, ON_BRIEF or
        UNCLEAR, assuming the mechanical rules already pass. Only OFF_BRIEF leaves a permanent
        strike on the brief, accruing to its owner. A brief is never closed.
        """
        checker = gl.message.sender_address.as_hex.lower()
        bid = str(brief_id).strip()
        link = str(output_url).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"ok": False, "error": "no brief with that id"})
        if not _url_ok(link):
            return json.dumps({"ok": False, "error": "give an http(s) URL for the output"})
        record = json.loads(stored)

        # Copy into locals before the round. Nothing inside the block reads self
        # and nothing inside it raises.
        title = record["title"]
        brief = record["brief"]

        def look() -> str:
            page = _fetch(link)
            if page == FETCH_FAILED:
                return json.dumps({"verdict": UNCLEAR, "quote": "",
                                   "reason": "the output page could not be read"})
            try:
                return str(gl.nondet.exec_prompt(_task(title, brief, page)))
            except Exception as error:
                return json.dumps({"verdict": UNCLEAR, "quote": "",
                                   "reason": _clip("the prompt failed: " + str(error), MAX_REASON)})

        raw = gl.eq_principle.prompt_comparative(
            look,
            principle=(
                f"Both answers must carry the same value in the field named verdict, one of "
                f"{OFF_BRIEF}, {ON_BRIEF} or {UNCLEAR}. That single field decides whether the output "
                "is struck as off-brief, so two readers differing on it disagree about whether the "
                "output betrays the brief, not about wording. The other fields are not compared, and "
                "the two readers will not have fetched byte-identical copies of the page."
            ),
        )

        verdict = _field(raw, "verdict", VERDICTS, "")
        if not verdict:
            return json.dumps({"ok": False, "error": "the round produced no verdict this contract recognises",
                               "round_said": _clip(str(raw), 400)})

        reason = _text_field(raw, "reason", MAX_REASON)
        quote = _text_field(raw, "quote", MAX_QUOTE)
        strike_delta, clean_delta = _counts_after(verdict)

        record["checks"] = int(record.get("checks", 0)) + 1
        record["strikes"] = int(record.get("strikes", 0)) + strike_delta
        record["clean"] = int(record.get("clean", 0)) + clean_delta
        entry = {"n": record["checks"], "at": _now_iso(), "by": checker, "output_url": link,
                 "verdict": verdict, "quote": quote, "reason": reason}
        log = list(record.get("log", []))
        log.append(entry)
        if len(log) > MAX_LOG:
            log = log[-MAX_LOG:]
        record["log"] = log
        if strike_delta:
            record["last_reason"] = reason
            record["last_quote"] = quote
            self._bump(record["owner"], 0, 1)
        # ON_BRIEF and UNCLEAR leave the strike count untouched.
        self.items[bid] = json.dumps(record)
        return json.dumps({"ok": True, "id": bid, "verdict": verdict,
                           "strikes": record["strikes"], "reason": reason})

    # ------------------------------------------------------------------ reads

    @gl.public.view
    def record(self, address: str) -> str:
        """An owner's record: briefs opened, and off-brief strikes accrued across them."""
        a = _addr(address)
        if not a:
            return json.dumps({"exists": False, "briefs": 0, "strikes": 0})
        raw = self.records.get(a, None)
        if raw is None:
            return json.dumps({"exists": False, "address": a, "briefs": 0, "strikes": 0})
        rec = json.loads(raw)
        return json.dumps({"exists": True, "address": a,
                           "briefs": int(rec.get("briefs", 0)), "strikes": int(rec.get("strikes", 0))})

    @gl.public.view
    def brief(self, brief_id: str) -> str:
        """A brief's standing: how many checks, how many strikes, and the last strike's reason."""
        bid = str(brief_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"exists": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": bid, "title": record["title"],
                           "checks": record["checks"], "strikes": record["strikes"],
                           "clean": record["clean"], "reason": record.get("last_reason", "")})

    @gl.public.view
    def history(self, brief_id: str) -> str:
        """The append-only log of every check run against a brief."""
        bid = str(brief_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"exists": False})
        record = json.loads(stored)
        return json.dumps({"exists": True, "id": bid, "strikes": record["strikes"],
                           "checks": record["checks"], "log": record.get("log", [])})

    @gl.public.view
    def get(self, brief_id: str) -> str:
        """The whole brief, including its check history."""
        bid = str(brief_id).strip()
        stored = self.items.get(bid, None)
        if stored is None:
            return json.dumps({"exists": False})
        return stored

    @gl.public.view
    def size(self) -> str:
        """How many briefs stand clean and how many carry at least one strike."""
        clean = 0
        flagged = 0
        for position in range(len(self.ids)):
            struck = json.loads(self.items[self.ids[position]])["strikes"]
            if int(struck) > 0:
                flagged += 1
            else:
                clean += 1
        return json.dumps({"total": len(self.ids), "clean": clean, "flagged": flagged})

    @gl.public.view
    def page(self, start: str, count: str) -> str:
        """A slice of the briefs, newest first, for a frontend to render."""
        total = len(self.ids)
        begin = _whole(start)
        want = _whole(count)
        if begin < 0:
            begin = 0
        if want < 1:
            want = 20
        if want > 50:
            want = 50
        out = []
        seen = 0
        position = total - 1 - begin
        while position >= 0 and seen < want:
            record = json.loads(self.items[self.ids[position]])
            record["check_count"] = len(record.get("log", []))
            record.pop("log", None)
            out.append(record)
            position -= 1
            seen += 1
        return json.dumps({"total": total, "start": begin, "count": len(out), "items": out})
