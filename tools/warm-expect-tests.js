#!/usr/bin/env node
'use strict';

// Pre-fill the tree-calculus reduction cache with this build's expect-test
// results, in parallel.
//
// `lambada expect-test` asks the tree-calculus runtime for one reduction per
// test, in order, in one process. With TREE_CALCULUS_CACHE set, the runtime
// answers from its reduction cache whenever the term asked about is one it
// has seen — a term's cache address is a fingerprint of its structure, so
// answers survive rebuilds even though canonicalization renumbers the whole
// bundle on any change. This tool computes the same terms the expect tests
// will ask about, finds the ones whose answers are not on disk yet, and
// evaluates just those across every core. The build's expect-test pass then
// finds every answer already written.
//
// Correctness does not depend on any of this: a term this tool fails to
// predict is a cache miss, and expect-test evaluates it exactly as it would
// have without warming. Terms are constructed the way lambada's
// bin/expect-test.js constructs them (see test_dag there); if that ever
// drifts, builds get slower, not wrong.
//
// Usage: node tools/warm-expect-tests.js <bundle> [--jobs N]

const { fork } = require('child_process');
const { readFileSync, readdirSync, statSync, unlinkSync, writeFileSync } = require('fs');
const { availableParallelism, tmpdir } = require('os');
const { join, resolve } = require('path');

const runtime = require(resolve(
  process.env.LAMBADA_TREE_CALCULUS ?? `${__dirname}/../submodules/tree-calculus`,
  'bin/dag.js'));
const {
  DagModule, box, LEAF, environment, evaluator, fingerprint,
  cache_store, REDUCE_STORE, MODULE_STORE,
} = runtime;

/** One test's DAG payload, mirroring test_dag in lambada's bin/expect-test.js. */
function test_dag(own, expression, symbol) {
  const [stem, pair] = [box(':stem'), box(':pair')];
  own.lines.push([stem, box(LEAF), box(expression)], [pair, stem, box(symbol)]);
  return own.toString([pair.symbol]);
}

/** Drop entries of the store directory not used in `days` (use refreshes mtime). */
function prune_store(name, days) {
  const directory = join(process.env.TREE_CALCULUS_CACHE, name);
  let entries;
  try { entries = readdirSync(directory); } catch { return; }
  const horizon = Date.now() - days * 24 * 60 * 60 * 1000;
  for (const entry of entries) {
    const path = join(directory, entry);
    try {
      if (statSync(path).mtimeMs < horizon) unlinkSync(path);
    } catch { /* a parallel writer's temporary, or already gone */ }
  }
}

function worker_main() {
  let get = null;
  process.on('message', message => {
    if (message.type === 'exit') process.exit(0);
    try {
      // The first environment build in the first worker evaluates the module
      // and leaves its dump behind (see `loadable` in tree-calculus); every
      // later worker re-loads that dump in a fraction of the time.
      get ??= environment(evaluator, readFileSync(message.shared, 'utf8'));
      get.reduce(message.payload);
      process.send({ type: 'done' });
    } catch (error) {
      process.send({ type: 'done', error: `${message.symbol}: ${error.message}` });
    }
  });
  process.send({ type: 'ready' });
}

function main() {
  const argv = process.argv.slice(2);
  if (argv.includes('--worker')) return worker_main();

  const bundle_path = argv.find(a => !a.startsWith('--'))
    ?? (() => { throw new Error('usage: warm-expect-tests.js <bundle> [--jobs N]'); })();
  const jobs = argv.includes('--jobs')
    ? Number(argv[argv.indexOf('--jobs') + 1])
    : availableParallelism();

  // Warming pays only when reductions go through the native runner, which is
  // where the reduction cache lives; on the pure-Node path this would evaluate
  // everything without leaving anything behind for expect-test to find.
  if (!['1', 'eager'].includes(process.env.TREE_CALCULUS_RUNNER ?? '')) return;
  const reduce_store = cache_store(REDUCE_STORE);
  if (!reduce_store) return; // no TREE_CALCULUS_CACHE: nowhere to warm into

  // Prune before probing, so nothing probed as present disappears afterwards.
  prune_store(REDUCE_STORE, 30);
  prune_store(MODULE_STORE, 3);

  const text = readFileSync(bundle_path, 'utf8');
  const linked = DagModule.parse(text);

  // Tests are 2-word `:test.*` label lines; the expression a test renders is
  // the right side of its target's definition. Mirrors lambada expect-test.js.
  const defining_line = new Map();
  const tests = [];
  for (const line of linked.lines) {
    if (line.length === 2 || line.length === 3) defining_line.set(line[0], line);
    if (line.length === 2 && /^:test\./.test(line[0].symbol))
      tests.push({ symbol: line[0].symbol, target: line[1] });
  }
  if (!tests.length) return;

  const { shared, exclusive } = linked.partition(tests.map(t => t.symbol));
  const shared_text = shared.toString();

  // The terms expect-test will ask about, addressed the way the runtime
  // addresses them; whatever is already answered on disk is skipped.
  const outer = fingerprint(shared_text).fingerprints;
  const misses = [];
  for (const { symbol, target } of tests) {
    const definition = defining_line.get(target);
    const expression = definition && definition.length === 3
      ? definition[2].symbol
      : target.symbol;
    const payload = test_dag(exclusive.get(symbol), expression, symbol);
    const key = fingerprint(payload, name => outer.get(name)).value;
    if (!reduce_store.has(key)) misses.push({ symbol, payload });
  }

  process.stderr.write(`  ${tests.length - misses.length} of ${tests.length} answered, `
    + `${misses.length} to evaluate\n`);
  if (!misses.length) return;

  const shared_path = join(tmpdir(), `warm-shared-${process.pid}.dag`);
  writeFileSync(shared_path, shared_text);
  process.on('exit', () => { try { unlinkSync(shared_path); } catch { } });

  const queue = [...misses];
  let failures = 0;

  /** A worker pulling tasks off the queue until it is empty. */
  const run_worker = on_first_done => new Promise(settle => {
    const child = fork(__filename, ['--worker'], { stdio: 'inherit' });
    let finished = 0;
    const feed = () => {
      const task = queue.shift();
      if (!task) {
        child.send({ type: 'exit' });
        settle();
        return;
      }
      child.send({ type: 'task', shared: shared_path, symbol: task.symbol, payload: task.payload });
    };
    child.on('message', message => {
      if (message.type === 'done' && ++finished === 1) on_first_done?.();
      if (message.error) {
        failures++;
        process.stderr.write(`  warm: ${message.error}\n`);
      }
      feed(); // both 'ready' and 'done' mean: give it something to do
    });
    child.on('exit', () => { on_first_done?.(); settle(); }); // a crashed worker must not stall the rest
  });

  (async () => {
    // One worker starts alone: whoever misses first pays for evaluating the
    // module and leaves its dump behind for the rest (see `loadable` in
    // tree-calculus) — a herd arriving together would all pay it. Once its
    // first answer lands, the dump is on disk and the rest start against it.
    let open_gate;
    const gate = new Promise(open => { open_gate = () => { open(); open_gate = null; } });
    const first = run_worker(() => open_gate?.());
    await gate;
    await Promise.all([first, ...Array.from(
      { length: Math.max(0, Math.min(jobs, queue.length + 1) - 1) },
      () => run_worker())]);
    if (failures) process.stderr.write(`  warm: ${failures} term(s) left to expect-test\n`);
  })();
}

main();
