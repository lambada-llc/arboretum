# Arboretum

A repository of [trees](https://github.com/lambada-llc/lambada) defined and maintained using the [LambAda](https://github.com/lambada-llc/lambada) ecosystem.

LambAda sources (`.lamb` files) compile to combinations of `△` and previously defined symbols (`.dag` files).
Every bare top-level expression is an
expect test whose result is written back into the source as a comment.

## Setup

```bash
git submodule update --init
```

Node.js is the only dependency. The LambAda compiler is itself a tree (`submodules/lambada/compiler/compile_to_dag.dag`).

## Build

```bash
./build.sh   # compile src/**/*.lamb and refresh the `# = …` result comments
./check.sh   # build, then fail if anything under src/ changed
```

## Layout

```
src/                     LambAda sources; symbols are namespaced by directory
  core.lamb                → id, compose, fix, …          (root, unqualified)
  bool/bool.lamb           → Bool.not, Bool.and, …        (Bool.* namespace)
  expect_test.lamb         → example tests
build/rules/             build steps (plain Node scripts)
build/.cache/.           compiler output cache (gitignored)
```

There is no "import" statement or similar: Dependencies between modules are resolved automatically by the build system, cycles forbidden.

## Pipeline

`build.sh` runs five phases:

1. **Compile** — `build/rules/compile-all.js` splits each `.lamb` into top-level
   chunks, applies the LambAda compiler to each (caching by content hash), then
   qualifies the resulting symbols by file location: `not` in `src/bool/bool.lamb`
   is exported as `Bool.not`. Bare top-level expressions become `:test.*` symbols.
2. **Sort** — `dag-topo-sort.js` orders the per-file DAGs so dependencies come
   first, and rejects duplicate symbols and dependency cycles.
3. **Bundle** — concatenate them into `src/.dag-bundle`.
4. **Canonicalize** — `dag-bundle-canonicalize.js` hash-conses the bundle into
   globally unique numeric IDs.
5. **Test** — `dag-test.js` evaluates each `:test.*` symbol and writes the
   result back into the source file it came from. A test symbol is named after
   that source line (`:test.Bool.Bool.12`), so no separate bookkeeping is needed
   to find it again.

## Adding definitions

Drop a `.lamb` file into the appropriate `src/` subdirectory and run `./build.sh`
— files are discovered automatically. Symbols may reference each other freely
across files; only cycles are rejected.

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

An expression that evaluates to a file — `△ (△ <name> <media type>) <bytes>` —
is written into a sibling `expect-test-out/` directory instead, and the comment
identifies it by name and content hash:

```lamb
# src/expect_test.lamb
△ (△ "hello.txt" "text/plain") "Hello, LambAda!"
# = hello.txt with hash 169f0107cf1f
```

The test signal is the git diff, not the exit code of `./build.sh`, which
succeeds either way. An unnoticed diff is a test failure.

## Running compiled programs

```bash
node submodules/tree-calculus/bin/main.js -dag -file <file.dag> -bool true -bool
```
