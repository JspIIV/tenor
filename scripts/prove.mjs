// Prove Tenor end to end on GenLayer Asimov.
//
//   AT=0x... PADV=<padv pw> PPUB=<ppub pw> node scripts/prove.mjs
//
// padv opens a brief, the intent and voice an output must honour. Anyone checks an output
// against it: one that honours the brief leaves it clean, one that betrays it (while breaking
// no rule) strikes it, and an unreadable output never strikes anyone. The brief is never
// closed and keeps accruing strikes; history is preserved across every check.
import { Wallet } from 'ethers';
import { createClient, createAccount } from 'genlayer-js';
import { testnetAsimov } from 'genlayer-js/chains';
import fs from 'fs';
import os from 'os';
import path from 'path';
import url from 'url';

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
const padv = await acct('padv.json', PADV);   // brief owner
const ppub = await acct('ppub.json', PPUB);    // checker
const anybody = createClient({ chain: testnetAsimov });

const RAW = 'https://raw.githubusercontent.com/JspIIV/tenor/master/docs/';
const TITLE = 'Acme support voice';
const BRIEF = 'Warm, plain replies for a budgeting app for people anxious about money. Reassure first, never shame the user, never push a paid upgrade, never give specific investment advice. End with one small concrete step.';
const ON_URL = RAW + 'output-on-brief.txt';
const OFF_URL = RAW + 'output-off-brief.txt';
const UNREADABLE = RAW + 'no-such-output-9f2c.txt';

const out = [];
const say = l => { console.log(l); out.push(l); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const transient = e => /-32005|-32006|-32029|-32603|at capacity|rate limit|gas rate|reverted.*consensus|consensus.*reverted|backpressure|fetch failed|timeout|502|503|429|ECONNRESET|ENOTFOUND|EAI_AGAIN|getaddrinfo|resource not found/i
  .test(String(e?.details || e?.shortMessage || e?.message || e) + ' ' + String(e?.cause?.cause?.code || e?.cause?.code || ''));

async function read(fn, args = []) {
  for (let a = 1; ; a++) {
    try { return JSON.parse(await anybody.readContract({ address: AT, functionName: fn, args })); }
    catch (e) { if (!transient(e) || a >= 14) throw e; await sleep(5000 * a); }
  }
}
async function write(who, fn, args) {
  for (let a = 1; ; a++) {
    try { return await who.client.writeContract({ address: AT, functionName: fn, args, value: 0n }); }
    catch (e) { if (!transient(e) || a >= 14) throw e; say(`  (${fn} transient, wait ${8 * a}s)`); await sleep(8000 * a); }
  }
}
async function openBrief(title, brief) {
  const n = (await read('size')).total;
  for (let attempt = 1; attempt <= 3; attempt++) {
    await write(padv, 'open_brief', [title, brief]);
    for (let i = 0; i < 30; i++) { const s = await read('size'); if (s.total > n) return String(s.total - 1); await sleep(5000); }
  }
  throw new Error('brief not opened');
}
async function checkUntil(who, id, output_url, label) {
  const before = Number((await read('get', [id])).checks || 0);
  for (let attempt = 1; attempt <= 4; attempt++) {
    try { await write(who, 'check', [id, output_url]); } catch (e) { say(`  ${label} err ${String(e.message).slice(0, 50)}`); }
    for (let i = 0; i < 36; i++) {
      await sleep(15000);
      const g = await read('get', [id]);
      if (Number(g.checks || 0) > before) { const v = g.log[g.log.length - 1].verdict;
        say(`  ${label}: strikes=${g.strikes} v=${v} (${(i + 1) * 15}s)`); return g; }
    }
    say(`  ${label}: not settled after poll, retrying`);
  }
  return await read('get', [id]);
}

say('Tenor, proven on GenLayer Asimov');
say('  contract ' + AT);
say('  owner(padv) ' + padv.addr + '  checker(ppub) ' + ppub.addr);
say('');

const baseRec = await read('record', [padv.addr]);
const baseSize = await read('size');

const id0 = await openBrief(TITLE, BRIEF);
say('padv opened brief #' + id0 + ' (' + TITLE + ')');
const id1 = await openBrief('Beta brief', BRIEF);
say('padv opened brief #' + id1 + ' (to be checked with an unreadable output)');
say('');

say('checking brief #' + id0 + ' with an output that honours it...');
const rOn = await checkUntil(ppub, id0, ON_URL, 'on-brief');
say('  #' + id0 + ' strikes ' + rOn.strikes + ' | ' + (rOn.log[rOn.log.length - 1].reason || ''));
say('checking brief #' + id1 + ' with an unreadable output...');
const rUn = await checkUntil(ppub, id1, UNREADABLE, 'unreadable');
say('  #' + id1 + ' strikes ' + rUn.strikes + ' | last verdict ' + rUn.log[rUn.log.length - 1].verdict);
say('checking brief #' + id0 + ' with an output that passes the rules but betrays the brief...');
const rOff = await checkUntil(ppub, id0, OFF_URL, 'off-brief');
say('  #' + id0 + ' strikes ' + rOff.strikes + ' | ' + (rOff.last_reason || (rOff.log[rOff.log.length - 1] || {}).reason || ''));
say('');

const hist = await read('history', [id0]);
const rec = await read('record', [padv.addr]);
const size = await read('size');
say('brief #' + id0 + ' log: [' + hist.log.map(e => e.verdict).join(', ') + ']');
say('owner record ' + JSON.stringify(baseRec) + ' -> ' + JSON.stringify(rec));
say('book: ' + JSON.stringify(size));

const onVerdict = rOn.log[rOn.log.length - 1].verdict;
const offVerdict = rOff.log[rOff.log.length - 1].verdict;
const checks = [
  ['an output that honours the brief leaves it clean', Number(rOn.strikes) === 0 && onVerdict === 'ON_BRIEF'],
  ['an unreadable output is UNCLEAR and does not strike', Number(rUn.strikes) === 0 && rUn.log[rUn.log.length - 1].verdict === 'UNCLEAR'],
  ['an output that passes the rules but betrays the brief STRIKES it', offVerdict === 'OFF_BRIEF' && Number(rOff.strikes) >= 1],
  ['the strike carries a reason drawn from the output', (rOff.last_reason || (rOff.log[rOff.log.length - 1] || {}).reason || '').length > 0],
  ["the owner's record gains exactly one strike", rec.strikes - baseRec.strikes === 1],
  ['every check is preserved in history, oldest first',
    hist.log.length >= 2 && hist.log[0].verdict === 'ON_BRIEF' && hist.log[hist.log.length - 1].verdict === 'OFF_BRIEF'],
  ['the brief was never closed; it kept taking checks', Number(rOff.checks) >= 2],
  ['this run adds one struck brief to the book', size.flagged - baseSize.flagged === 1],
];
say('');
for (const [label, ok] of checks) say((ok ? '  ok   ' : ' FAIL  ') + label);
const failed = checks.filter(([, ok]) => !ok);
say('');
say(failed.length ? `${failed.length} of ${checks.length} checks failed` : `${checks.length} checks. Only an output that betrayed the brief, while breaking no rule, struck it.`);

fs.mkdirSync(path.join(ROOT, 'results'), { recursive: true });
fs.writeFileSync(path.join(ROOT, 'results', 'proved.json'), JSON.stringify({
  proved_at: new Date().toISOString(), network: 'genlayer testnet asimov', contract: AT,
  on_brief: rOn, unreadable: rUn, off_brief: rOff, history: hist, record: rec, size,
  checks: checks.map(([label, ok]) => ({ label, ok })), transcript: out,
}, null, 2));
say('Written to results/proved.json');
process.exit(failed.length ? 1 : 0);
