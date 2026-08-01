# Arboretum

A repository of [trees](https://github.com/lambada-llc/lambada) defined and maintained using the [LambAda](https://github.com/lambada-llc/lambada) ecosystem.

LambAda sources (`.lamb` files) compile to combinations of `△` and previously defined symbols (`.dag` files).
Every bare top-level expression is an
expect test whose result is written back into the source as a comment.

## Setup

```bash
git submodule update --init
```

Node.js and a C++ compiler are the only dependencies. The LambAda compiler is itself a tree (`submodules/lambada/compiler/compile_to_dag.dag`).

The C++ one is there because reducing trees is what a build spends its time on,
and [`runner`](https://github.com/lambada-llc/tree-calculus/blob/main/implementation/cpp/dag-machine/runner.md)
does that faster and in bounded memory. `build.sh` asks for it with
`TREE_CALCULUS_RUNNER=eager`; the runtime compiles it from source on first use.
`=1` picks the lazy evaluator instead, and dropping the line runs the same build
on Node alone — all three to the same results.

## Build

```bash
./build.sh   # compile src/**/*.lamb and refresh the `# = …` result comments
```

Then look at `git status`: a clean tree means every test still produces what is
committed. CI runs the same build and fails on a dirty tree.

## Layout

```
src/                     LambAda sources; symbols are namespaced by directory
  core.lamb                → id, compose, fix, …          (root, unqualified)
  bool/bool.lamb           → Bool.not, Bool.and, …        (Bool.* namespace)
  expect_test.lamb         → example tests
.cache/lambada/          compiler output cache (gitignored)
```

There is no "import" statement or similar: Dependencies between modules are resolved automatically by the build system, cycles forbidden.

## Pipeline

This repository has no build logic of its own. [`build.sh`](./build.sh) is a
handful of invocations of tools that live in the submodules — the
[LambAda build tool](https://github.com/lambada-llc/lambada/tree/main/bin), which
knows about `.lamb` sources and expect tests, and the
[tree calculus runtime](https://github.com/lambada-llc/tree-calculus/tree/main/bin),
which knows about [DAGs](https://github.com/lambada-llc/tree-calculus/tree/main/conventions#dag-modules):

1. **Compile** — `lambada compile` splits each `.lamb` into top-level chunks,
   applies the LambAda compiler to each (caching by content hash), and namespaces
   the resulting symbols by file location, so `not` in `src/bool/bool.lamb` is
   exported as `Bool.not`. Bare top-level expressions become `:test.*` symbols.
   The result is one `.dag` module next to each source.
2. **Link** — `dag link` orders those modules so dependencies come first and
   concatenates them, rejecting duplicate exports and dependency cycles;
   `dag canonicalize` then hash-conses the whole thing into globally unique
   numeric ids.
3. **Test** — `lambada expect-test` evaluates each `:test.*` symbol and writes
   the result back into the source file it came from. A test symbol is named
   after that source line (`:test.Bool.Bool.12`), so no separate bookkeeping is
   needed to find it again.
4. **Export the compiler** — `dag extract` takes `Lambada.compile` and
   `Lambada.compile_to_dag` back out of the bundle as DAGs that stand on their
   own, and writes them to `submodules/lambada/compiler/`, which is where the
   [compiler source](./src/lambada/compiler.lamb) is published as a tree.

Steps 1 and 3 are the ones that reduce trees, and both hand that to the C++
runner — see [Setup](#setup).

## Adding definitions

Drop a `.lamb` file into the appropriate `src/` subdirectory and run `./build.sh`
— files are discovered automatically. Symbols may reference each other freely
across files; only cycles are rejected.

## Everything here terminates eagerly

Tree calculus is a calculus: it prescribes no evaluation order. That freedom is
the caller's, not the library's — so the rule for this repository is that every
program in it terminates under **eager** evaluation.

The discipline costs nothing and buys everything: a program that terminates
eagerly also terminates lazily, so trees from here can be handed to any
evaluator, in any order, without a caveat. Accept programs that only converge
lazily and that flexibility is gone — and with it the eager evaluators, which in
practice are the fast ones.

So a definition that diverges under eager evaluation is a bug here, not a
trade-off. What makes that workable is that delay is expressible: `wait` in
[`src/core.lamb`](./src/core.lamb) holds an application as a value until it is
applied, and `fix` is built on it, so a recursive definition unfolds one step
per call instead of ahead of itself. Anything else that must not be evaluated
yet is delayed the same way, explicitly.

A program worth keeping that only converges in normal order carries a `__lazy`
suffix. Nothing applies one directly: `Reflect.lazy_eval` evaluates it, and
terminates eagerly itself, so the rule above still holds of everything the build
runs.

## Writing [expect tests](https://blog.janestreet.com/the-joy-of-expect-tests/)

Every bare top-level expression in a `.lamb` file is a test. If the file defines
`_to_string`, it is applied to the result before rendering; otherwise identity
is assumed.

`./build.sh` records the result as a `# = …` comment right below the expression:

```lamb
# src/bool/bool.lamb
_to_string = to_source
not false
# = true
not true
# = false
```

Only `# = ` lines and their `#   ` continuations are machine-owned; your own
comments are left alone. Multi-line results wrap onto the continuation lines.

An expression that evaluates to a
[file](https://github.com/lambada-llc/tree-calculus/tree/main/conventions#files)
— `△ (△ <name> <media type>) <bytes>` — is written into a sibling
`expect-test-out/` directory instead, and the comment identifies it by name and
content hash:

```lamb
# src/expect_test.lamb
△ (△ "hello.txt" "text/plain") "Hello, LambAda!"
# = hello.txt sha256:169f0107cf1f…
```

The test signal is the git diff, not the exit code of `./build.sh`, which
succeeds either way. An unnoticed diff is a test failure.

## Running compiled programs

```bash
node submodules/tree-calculus/bin/main.js -dag -file <file.dag> -bool true -bool
```
