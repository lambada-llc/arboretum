#!/bin/bash
# build.sh — compile src/**/*.lamb and regenerate the test outputs
#
# Every step is an invocation of a tool from one of the submodules: the LambAda
# build tool knows about .lamb sources and expect tests, and the tree calculus
# runtime knows about DAGs. Nothing here is specific to this repository.
set -euo pipefail
cd "$(dirname "$0")"

# Use the pinned submodule rather than a published runtime.
export LAMBADA_TREE_CALCULUS="$PWD/submodules/tree-calculus"
export TREE_CALCULUS_RUNNER=eager
# Where the runtime keeps what reduction it has already done: evaluated
# modules, and per-term results the expect tests below are answered from.
# Content-addressed, so a stale entry cannot exist — only a missing one.
export TREE_CALCULUS_CACHE="$PWD/.cache/tree-calculus"
# Using an entry stamps it, so what no build has needed lately can go: an
# evaluated module after three days (one per version of the library, and each
# large), anything else after thirty.
find "$TREE_CALCULUS_CACHE/module-v1" -type f -mtime +3 -delete 2>/dev/null || true
find "$TREE_CALCULUS_CACHE" -type f -mtime +30 -delete 2>/dev/null || true
lambada="node submodules/lambada/bin/lambada.js"
dag="node submodules/tree-calculus/bin/dag.js"

# Compile each .lamb into a sibling .dag module, namespaced by its path
>&2 echo "Compiling"
$lambada compile --root src --cache .cache/lambada

# Order the modules so dependencies come first, concatenate them, and hash-cons
# the result into globally unique ids
>&2 echo "Linking"
$dag link $(find src -name '.*.dag' | sort) \
  | $dag canonicalize > src/.dag-bundle-canonical

# Evaluate the top-level expressions, recording results in the sources. A
# thread evaluating a certifier test can hold several GB of native arena, and
# one per core on a small-memory runner kills the VM outright, so each thread
# is granted 8 GB of the machine's memory.
>&2 echo "Running tests"
jobs=$(node -p 'const os = require("os"); Math.max(1, Math.min(os.availableParallelism(), Math.floor(os.totalmem() / 8 / 2 ** 30)))')
$lambada expect-test src/.dag-bundle-canonical --root src --jobs "$jobs"

# Take the compilers back out of the bundle they are part of, so that the
# lambada submodule ships what this repository just built from its source: the
# compiler, the one that also reports each expression's span, and the prelude —
# a compiled chunk refers to the combinator labels and leaves defining them to
# the module, which puts the prelude at the top of one, once. Everything above
# runs on that same compiler and prelude, so a broken one would brick the next
# build: extract, probe, and only then install.
>&2 echo "Exporting compiler"
compiler=submodules/lambada/compiler
main="node submodules/tree-calculus/bin/main.js"
compilers="compile_to_dag compile_to_dag_with_spans"
for symbol in $compilers; do
  $dag extract --symbol "Lambada.$symbol" src/.dag-bundle-canonical \
    | $dag canonicalize > "$compiler/$symbol.dag.new"
done

# The prelude goes out as the DAG lines it is, not as a tree that encodes them,
# so putting it in front of a chunk is concatenating a file.
$dag extract --symbol Lambada.prelude src/.dag-bundle-canonical \
  | $dag canonicalize | $main -dag -file /dev/stdin -string > "$compiler/prelude.dag.new"

# Probed together, the way a caller uses them: each compiler compiles `x = △`,
# and `x` is read back out of the module the prelude and that chunk make.
for symbol in $compilers; do
  probe=$( { cat "$compiler/prelude.dag.new"
             $main -dag -file "$compiler/$symbol.dag.new" -string 'x = △' -string
           } | $dag eval --symbol x --format term 2>/dev/null || true)
  if [ "$probe" != "△" ]; then
    rm -f "$compiler"/*.dag.new
    >&2 echo "ERROR: the extracted $symbol and prelude do not compile 'x = △' to the leaf;"
    >&2 echo "       the shipped ones are left alone. Got: $probe"
    exit 1
  fi
done
for symbol in $compilers prelude; do
  mv "$compiler/$symbol.dag.new" "$compiler/$symbol.dag"
done

# The scopes lambada's codemirror demo offers, cut from the same bundle. A root
# brings along what it is built from, so each file is self-contained.
>&2 echo "Exporting demo environments"
env_dags=submodules/lambada/codemirror/demo/env-dags
mkdir -p "$env_dags"

# Unqualified names are the root module.
$dag extract --matching '^([a-z]|(Bool|Pair|List|Fn|Nat|Snat|Option|String|Serialize|Map|Set)\.)' \
  src/.dag-bundle-canonical > "$env_dags/basics.dag"

# What the demo's sample calls, and nothing else of Qr.
$dag extract --symbol Qr.create --symbol Qr.to_svg \
  src/.dag-bundle-canonical > "$env_dags/qr.dag"
