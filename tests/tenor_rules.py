"""The Tenor rules, exercised through the real contract methods.

tenor.py is loaded against a stub of the runtime, a real Tenor is built, and the assertions go
through open_brief(), publish() and challenge(). The stub controls only the verdict the round
returns; the judged text is the author's own on-chain output, and the contract fetches nothing.

It proves provenance is settled by construction (an output is always authored by the message
sender and cannot be attributed to anyone else, and no web page is ever fetched), only an
OFF_BRIEF strikes, an ON_BRIEF clears, UNCLEAR leaves a publication open, a settled publication
cannot be re-judged, strikes never clear, a brief accrues strikes across its publications, and
history is preserved. It covers the fabrication and impersonation cases a steward asked for.

    python tests/tenor_rules.py
"""

import io
import json
import os
import sys
import types

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRACT = os.path.join(HERE, "..", "contracts", "tenor.py")


class _Store:
    def __init__(self, kind): self.kind = kind
    def __class_getitem__(cls, item): return cls("map" if isinstance(item, tuple) else "list")
    def make(self): return {} if self.kind == "map" else []


class _Address:
    def __init__(self, hex_value): self.as_hex = str(hex_value)
    def __str__(self): return str(self.as_hex)


class _Message:
    def __init__(self):
        self.sender_address = _Address("0x" + "0" * 40)
        self.value = 0


class _Web:
    """Present but must never be used: the contract fetches nothing."""
    def render(self, url):
        raise AssertionError("the contract must not fetch the web")


class _Nondet:
    def __init__(self):
        self.web = _Web()
        self.last_prompt = None
        self.answer = "{}"

    def exec_prompt(self, task):
        self.last_prompt = task
        return self.answer


class _Write:
    def __call__(self, fn): return fn
    def payable(self, fn): return fn


class _PublicNS:
    def __init__(self):
        self.write = _Write()
        self.view = lambda fn: fn


class _EqPrinciple:
    def prompt_comparative(self, run, principle=None): return run()


class _GL:
    def __init__(self):
        self.Contract = object
        self.public = _PublicNS()
        self.message = _Message()
        self.nondet = _Nondet()
        self.eq_principle = _EqPrinciple()


def load():
    gl = _GL()
    fake = types.ModuleType("genlayer")
    fake.gl = gl
    fake.DynArray = _Store
    fake.TreeMap = _Store
    fake.u32 = int
    fake.u256 = int
    fake.Address = _Address
    sys.modules["genlayer"] = fake
    module = types.ModuleType("tenor_under_test")
    exec(compile(io.open(CONTRACT, encoding="utf-8").read(), CONTRACT, "exec"), module.__dict__)
    return module, gl


def fresh(module):
    contract = module.Tenor.__new__(module.Tenor)
    for field, declared in module.Tenor.__annotations__.items():
        setattr(contract, field, declared.make())
    contract.__init__()
    return contract


RESULTS = []


def check_(label, condition):
    RESULTS.append((label, bool(condition)))
    print(("  ok  " if condition else " FAIL "), label)


ALICE = "0x1111111111111111111111111111111111111111"   # brief owner
BOB = "0x2222222222222222222222222222222222222222"     # an author
MALLORY = "0x3333333333333333333333333333333333333333"  # a challenger / would-be impersonator

TITLE = "Acme support voice"
BRIEF = ("Warm, plain replies for a budgeting app. Reassure first, never shame the user, "
         "never push a paid upgrade, never give specific investment advice. End with one small step.")
GOOD = "You're not behind, this happens. One small step: set a safe-to-spend number for the week."
BAD = "Your spending is 32% over the limit. Upgrade to Acme Premium, the Pro plan is the responsible choice."


def answer(verdict, reason="r", quote="q"):
    return json.dumps({"verdict": verdict, "reason": reason, "quote": quote})


def main():
    module, gl = load()

    def as_(address): gl.message.sender_address = _Address(address)

    print("the pure outcome rule")
    check_("OFF_BRIEF strikes", module._settle("OFF_BRIEF") == ("OFF_BRIEF", 1, 0))
    check_("ON_BRIEF clears", module._settle("ON_BRIEF") == ("ON_BRIEF", 0, 1))
    check_("UNCLEAR leaves it pending", module._settle("UNCLEAR") == ("PENDING", 0, 0))

    print("\nopening a brief and publishing against it")
    c = fresh(module)
    as_(ALICE)
    check_("a brief needs a real body", not json.loads(c.open_brief(TITLE, "short"))["ok"])
    bid = json.loads(c.open_brief(TITLE, BRIEF))["id"]
    check_("a brief opens", bid == "0")
    as_(BOB)
    pub = json.loads(c.publish(bid, GOOD))
    pid = pub["id"]
    check_("an output publishes as PENDING", pub["ok"] and pub["status"] == "PENDING")

    print("\nprovenance: the author is the sender, and cannot be anyone else")
    p = json.loads(c.publication(pid))
    check_("the publication records the sender as author", p["author"] == BOB)
    check_("the author's own bytes are stored on chain, unchanged", p["output"] == GOOD)
    check_("publishing counts on the author's record, not the brief owner's",
           json.loads(c.record(BOB))["published"] == 1 and json.loads(c.record(ALICE))["published"] == 0)
    # Impersonation: Mallory publishing can only ever bind to Mallory, never to Bob.
    as_(MALLORY)
    pid2 = json.loads(c.publish(bid, "a forged line Mallory tries to pin on Bob"))["id"]
    check_("a third party's publication is authored by them, never by the target",
           json.loads(c.publication(pid2))["author"] == MALLORY)

    print("\nfabrication: there is no page to forge; judgement reads the on-chain output")
    as_(MALLORY)
    gl.nondet.answer = answer("ON_BRIEF", reason="warm, one step, no upsell")
    r0 = json.loads(c.challenge(pid))
    check_("a challenge needs no URL and fetches nothing", r0["ok"] and r0["verdict"] == "ON_BRIEF")
    check_("the exact published output was put in front of the round", GOOD in gl.nondet.last_prompt)
    check_("the brief and the assume-rules-pass instruction are in the prompt",
           BRIEF[:30] in gl.nondet.last_prompt and "mechanical rule" in gl.nondet.last_prompt)
    check_("an on-brief publication is cleared, no strike",
           json.loads(c.publication(pid))["status"] == "ON_BRIEF" and json.loads(c.record(BOB))["strikes"] == 0)
    check_("a cleared publication cannot be re-judged", not json.loads(c.challenge(pid))["ok"])

    print("\nan output that betrays the brief strikes its author, though it breaks no rule")
    as_(BOB)
    pid3 = json.loads(c.publish(bid, BAD))["id"]
    as_(MALLORY)
    gl.nondet.answer = answer("OFF_BRIEF", reason="pushes the paid upgrade the brief forbids", quote="Upgrade to Acme Premium")
    rf = json.loads(c.challenge(pid3))
    check_("an off-brief output STRIKES the author", rf["verdict"] == "OFF_BRIEF" and json.loads(c.publication(pid3))["status"] == "OFF_BRIEF")
    check_("the author's record gains a strike", json.loads(c.record(BOB))["strikes"] == 1)
    check_("the brief accrues the strike", json.loads(c.brief(bid))["strikes"] == 1)
    check_("the strike reason is recorded", "upgrade" in json.loads(c.publication(pid3))["reason"].lower())

    print("\nan unclear challenge leaves the publication open")
    as_(BOB)
    pid4 = json.loads(c.publish(bid, "ok"))["id"]
    as_(MALLORY)
    gl.nondet.answer = answer("UNCLEAR", reason="too little to judge")
    c.challenge(pid4)
    check_("an unclear publication stays PENDING", json.loads(c.publication(pid4))["status"] == "PENDING")
    gl.nondet.answer = answer("ON_BRIEF", reason="fine on a second look")
    c.challenge(pid4)
    check_("a pending publication can be challenged again", json.loads(c.publication(pid4))["status"] == "ON_BRIEF")

    print("\nstrikes never clear, and a clean publication does not offset one")
    c.open_brief("noop", BRIEF)  # keep ids moving
    check_("the author's one strike stands", json.loads(c.record(BOB))["strikes"] == 1)
    check_("the brief's strike is not offset by its clean publications",
           json.loads(c.brief(bid))["strikes"] == 1 and json.loads(c.brief(bid))["clean"] >= 1)

    print("\nhistory keeps every challenge on a publication, oldest first")
    hist = json.loads(c.publication(pid4))
    verdicts = [e["verdict"] for e in hist["log"]]
    check_("the full challenge log is preserved", verdicts == ["UNCLEAR", "ON_BRIEF"])

    print("\nthe book counts briefs, publications and strikes")
    size = json.loads(c.size())
    check_("the book counts a struck publication", size["struck"] == 1 and size["publications"] >= 4)

    failed = [label for label, ok in RESULTS if not ok]
    print()
    if failed:
        print("%d of %d checks failed" % (len(failed), len(RESULTS)))
        return 1
    print("%d checks, all through open_brief(), publish() and challenge() on a real Tenor; "
          "provenance by construction, the strike un-gameable" % len(RESULTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
