// Prove Tenor end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv pw> PPUB=<ppub pw> node scripts/prove.mjs
//
// padv opens a brief. ppub (the author) publishes two outputs on chain against it: one that
// honours the brief and one that breaks no rule but betrays it. padv, a third party, challenges
// each; a round judges the author's own on-chain words and returns ON_BRIEF or OFF_BRIEF. Only
// the off-brief output strikes the author. The contract fetches nothing; provenance is settled
// by construction (the author is the message sender), so a challenger cannot forge an output.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs'; import os from 'os'; import path from 'path'; import url from 'url';

const AT = process.env.AT;
const PADV = process.env.PADV || '';
const PPUB = process.env.PPUB || '';
if (!AT || !PADV || !PPUB) { console.error('set AT, PADV and PPUB'); process.exit(1); }

const ROOT = path.join(path.dirname(url.fileURLToPath(import.meta.url)), '..');
const KS = path.join(os.homedir(), '.genlayer', 'keystores');
async function acct(file, pw) {
  const w = await Wallet.fromEncryptedJson(fs.readFileSync(path.join(KS, file), 'utf8'), pw);
  return { addr: w.address.toLowerCase(), client: createClient({ chain: testnetAsimov, account: createAccount(w.privateKey) }) };
}
const padv = await acct('padv.json', PADV);   // brief owner + challenger (a third party to the author)
const ppub = await acct('ppub.json', PPUB);    // the author who publishes outputs
const anybody = createClient({ chain: testnetAsimov });

const TITLE = 'Acme support voice';
const BRIEF = 'Warm, plain replies for a budgeting app for people anxious about money. Reassure first, never shame the user, never push a paid upgrade, never give specific investment advice. End with one small concrete step.';
const GOOD = "You're not behind, and this is more common than it feels. One small step that helps: pick a single safe-to-spend number for the week, so you don't recalculate before every purchase. Want me to set that from your current balance?";
const BAD = "Your spending is about 32% over the recommended threshold for your income, which is why the balance is low. Cut discretionary purchases now. Most users in your situation upgrade to Acme Premium; at $14.99 the Pro plan is the responsible choice here. Budgeting is a discipline.";

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const withTimeout = (p, ms, tag) => Promise.race([p, new Promise((_, rej) => setTimeout(() => rej(new Error('TIMEOUT ' + tag)), ms))]);
const transient = e => /TIMEOUT|-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET|ENOTFOUND|EAI_AGAIN|getaddrinfo|resource not found/i
  .test(String(e?.details || e?.shortMessage || e?.message || e) + ' ' + String(e?.cause?.cause?.code || e?.cause?.code || ''));

async function read(fn, args = []) {
  for (let a = 1; ; a++) {
    try { return JSON.parse(await withTimeout(anybody.readContract({ address: AT, functionName: fn, args }), 45000, 'read')); }
    catch (e) { if (!transient(e) || a >= 16) throw e; await sleep(4000 * a); }
  }
}
async function write(who, fn, args) {
  for (let a = 1; a <= 8; a++) {
    try { const h = await withTimeout(who.client.writeContract({ address: AT, functionName: fn, args, value: 0n }), 90000, 'write'); return h; }
    catch (e) { if (!transient(e) || a >= 8) throw e; say(`  (${fn} ${String(e.message || e).slice(0, 36)}, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function openBrief() {
  const n = (await read('size')).briefs;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await write(padv, 'open_brief', [TITLE, BRIEF]);
    for (let i = 0; i < 40; i++) { const s = await read('size'); if (s.briefs > n) return String(s.briefs - 1); await sleep(8000); }
  }
  throw new Error('brief not opened');
}
async function publish(bid, body) {
  const n = (await read('size')).publications;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await write(ppub, 'publish', [bid, body]);
    for (let i = 0; i < 40; i++) { const s = await read('size'); if (s.publications > n) return String(s.publications - 1); await sleep(8000); }
  }
  throw new Error('output not published');
}
async function challengeUntil(pid, label) {
  const before = Number((await read('publication', [pid])).challenges || 0);
  for (let attempt = 1; attempt <= 4; attempt++) {
    try { await write(padv, 'challenge', [pid]); } catch (e) { say(`  ${label} write ${String(e.message || e).slice(0, 36)}`); }
    for (let i = 0; i < 80; i++) {
      await sleep(15000);
      const g = await read('publication', [pid]);
      if (Number(g.challenges || 0) > before) { const v = g.log[g.log.length - 1].verdict; say(`  ${label}: status=${g.status} v=${v} (${(i + 1) * 15}s)`); return g; }
    }
    say(`  ${label}: not settled, resubmitting`);
  }
  return await read('publication', [pid]);
}

say('Tenor, proven on GenLayer Asimov');
say('  contract ' + AT);
say('  brief owner + challenger(padv) ' + padv.addr + '  author(ppub) ' + ppub.addr);
say('');

const baseRec = await read('record', [ppub.addr]);
const baseSize = await read('size');

const bid = await openBrief();
say('padv opened brief #' + bid + ' (' + TITLE + ')');
const pGood = await publish(bid, GOOD);
say('ppub published output #' + pGood + ' (honours the brief)');
const pBad = await publish(bid, BAD);
say('ppub published output #' + pBad + ' (breaks no rule, betrays the brief)');
say('');

say('padv challenges output #' + pGood + ' (the honouring one)...');
const rOn = await challengeUntil(pGood, 'on-brief');
say('  #' + pGood + ' ' + rOn.status + ' | ' + (rOn.log[rOn.log.length - 1].reason || ''));
say('padv challenges output #' + pBad + ' (the betraying one)...');
const rOff = await challengeUntil(pBad, 'off-brief');
say('  #' + pBad + ' ' + rOff.status + ' | ' + (rOff.reason || (rOff.log[rOff.log.length - 1] || {}).reason || ''));
say('');

say('trying to challenge the settled output #' + pBad + ' again (should be refused)...');
const chBefore = Number((await read('publication', [pBad])).challenges || 0);
try { await write(padv, 'challenge', [pBad]); } catch {}
await sleep(8000);
const chAfter = Number((await read('publication', [pBad])).challenges || 0);
say('  #' + pBad + ' challenges ' + chBefore + ' -> ' + chAfter + ' (a settled publication is not re-judged)');
say('');

const good = await read('publication', [pGood]);
const bad = await read('publication', [pBad]);
const rec = await read('record', [ppub.addr]);
const brief = await read('brief', [bid]);
const size = await read('size');
say('author record ' + JSON.stringify(baseRec) + ' -> ' + JSON.stringify(rec));
say('brief #' + bid + ': ' + JSON.stringify({ published: brief.published, strikes: brief.strikes, clean: brief.clean }));
say('book: ' + JSON.stringify(size));

const checks = [
  ['the author is the on-chain publisher, not the challenger', bad.author === ppub.addr && bad.author !== padv.addr],
  ['the judged text is the exact output the author committed', bad.output === BAD && good.output === GOOD],
  ['an output that honours the brief is cleared, no strike', good.status === 'ON_BRIEF'],
  ['an output that breaks no rule but betrays the brief STRIKES the author', bad.status === 'OFF_BRIEF'],
  ['the strike carries a reason from the output', (bad.reason || '').length > 0],
  ["the author's record gains exactly one strike", rec.strikes - baseRec.strikes === 1],
  ['the brief accrues the strike', Number(brief.strikes) >= 1],
  ['a settled publication cannot be re-judged', chAfter === chBefore],
  ['this run adds one struck publication to the book', size.struck - baseSize.struck === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. Only the author's own committed output, found to betray the brief, struck them.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  on_brief: good, off_brief: bad, record: rec, brief, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
