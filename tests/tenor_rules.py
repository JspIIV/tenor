"""The Tenor rules, exercised through the real contract methods.

tenor.py is loaded against a stub of the runtime, a real Tenor is built, and the assertions go
through open_brief() and check(). The stub controls the output page the round fetches and the
verdict it returns. It proves only an OFF_BRIEF strikes a brief (and only from the output's own
text), an ON_BRIEF leaves it clean, an unreadable or not-found page never strikes anyone, a
brief is never closed and keeps accruing strikes, strikes never clear, and history is preserved.

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
    def __init__(self):
        self.page = "an output"

    def render(self, url):
        if self.page is None:
            raise RuntimeError("could not fetch")
        return self.page


class _Nondet:
    def __init__(self, web):
        self.web = web
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
        self.nondet = _Nondet(_Web())
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


ALICE = "0x1111111111111111111111111111111111111111"
BOB = "0x2222222222222222222222222222222222222222"

TITLE = "Acme support voice"
BRIEF = ("Warm, plain replies for a budgeting app. Reassure first, never shame the user, "
         "never push a paid upgrade, never give specific investment advice. End with one small step.")
U = "https://example.org/output"


def answer(verdict, reason="r", quote="q"):
    return json.dumps({"verdict": verdict, "reason": reason, "quote": quote})


def main():
    module, gl = load()

    def as_(address): gl.message.sender_address = _Address(address)

    print("the pure outcome rule")
    check_("OFF_BRIEF strikes the brief", module._counts_after("OFF_BRIEF") == (1, 0))
    check_("ON_BRIEF leaves it clean and counts a clean check", module._counts_after("ON_BRIEF") == (0, 1))
    check_("UNCLEAR changes nothing", module._counts_after("UNCLEAR") == (0, 0))

    print("\nopening a brief")
    c = fresh(module)
    as_(ALICE)
    check_("a brief needs a real body", not json.loads(c.open_brief(TITLE, "too short"))["ok"])
    reg = json.loads(c.open_brief(TITLE, BRIEF))
    bid = reg["id"]
    check_("a brief opens", reg["ok"] and bid == "0")
    check_("the owner's record counts the brief, no strike",
           json.loads(c.record(ALICE)) == {"exists": True, "address": ALICE, "briefs": 1, "strikes": 0})
    check_("checking with a non-url is refused", not json.loads(c.check(bid, "not a url"))["ok"])

    print("\nan output that honours the brief leaves it clean")
    as_(BOB)
    gl.nondet.answer = answer("ON_BRIEF", reason="warm, reassures, one step, no upsell")
    r0 = json.loads(c.check(bid, U))
    check_("an on-brief output does not strike", r0["verdict"] == "ON_BRIEF" and json.loads(c.brief(bid))["strikes"] == 0)
    check_("the brief was put in front of the round", BRIEF[:30] in gl.nondet.last_prompt)
    check_("the round is told to assume mechanical rules pass", "mechanical rule" in gl.nondet.last_prompt)
    check_("a clean check is counted", json.loads(c.brief(bid))["clean"] == 1)
    check_("no strike moved for an on-brief check", json.loads(c.record(ALICE))["strikes"] == 0)

    print("\nan unreadable or not-found output never strikes")
    gl.nondet.web.page = None
    ru = json.loads(c.check(bid, U))
    check_("an unreadable output is UNCLEAR and the brief stays clean", ru["verdict"] == "UNCLEAR" and json.loads(c.brief(bid))["strikes"] == 0)
    gl.nondet.web.page = "404: Not Found"
    rn = json.loads(c.check(bid, U))
    check_("a not-found output is UNCLEAR and does not strike", rn["verdict"] == "UNCLEAR" and json.loads(c.record(ALICE))["strikes"] == 0)

    print("\nan output that betrays the brief strikes it, though it breaks no rule")
    gl.nondet.web.page = "a correct but cold reply that pushes the paid plan"
    gl.nondet.answer = answer("OFF_BRIEF", reason="shames the user and pushes the paid upgrade the brief forbids", quote="upgrade to Premium")
    rf = json.loads(c.check(bid, U))
    check_("an off-brief output STRIKES the brief", rf["verdict"] == "OFF_BRIEF" and json.loads(c.brief(bid))["strikes"] == 1)
    check_("the owner's record gains a strike", json.loads(c.record(ALICE))["strikes"] == 1)
    check_("the strike reason is recorded", "upgrade" in json.loads(c.brief(bid))["reason"].lower())

    print("\na brief is never closed and keeps accruing strikes")
    r2 = json.loads(c.check(bid, U))
    check_("a second off-brief output adds a second strike", r2["verdict"] == "OFF_BRIEF" and json.loads(c.brief(bid))["strikes"] == 2)
    check_("the owner's record now shows two strikes", json.loads(c.record(ALICE))["strikes"] == 2)
    gl.nondet.answer = answer("ON_BRIEF", reason="fine")
    r3 = json.loads(c.check(bid, U))
    check_("a later clean check does not cancel the strikes", json.loads(c.brief(bid))["strikes"] == 2 and json.loads(c.brief(bid))["clean"] == 2)

    print("\nhistory keeps every check, oldest first")
    hist = json.loads(c.history(bid))
    verdicts = [e["verdict"] for e in hist["log"]]
    check_("the full check log is preserved",
           verdicts == ["ON_BRIEF", "UNCLEAR", "UNCLEAR", "OFF_BRIEF", "OFF_BRIEF", "ON_BRIEF"])

    print("\nthe book counts briefs clean and struck")
    as_(ALICE)
    c.open_brief("A second brief", BRIEF)
    size = json.loads(c.size())
    check_("two briefs, one struck and one clean", size["total"] == 2 and size["flagged"] == 1 and size["clean"] == 1)

    failed = [label for label, ok in RESULTS if not ok]
    print()
    if failed:
        print("%d of %d checks failed" % (len(failed), len(RESULTS)))
        return 1
    print("%d checks, all through open_brief() and check() on a real Tenor, the strike un-gameable"
          % len(RESULTS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
