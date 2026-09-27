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

# Evaluate the top-level expressions, recording results in the sources.
# The warm pass computes the answers that are not in the cache yet, on every
# core; expect-test then finds each one already written. Skipping the warm
# pass changes nothing but the time this takes.
>&2 echo "Running tests"
node tools/warm-expect-tests.js src/.dag-bundle-canonical
$lambada expect-test src/.dag-bundle-canonical --root src

# Take the compiler back out of the bundle it is part of, so that the lambada
# submodule ships the compiler this repository just built from its source. Two
# values, because a compiled chunk is a chunk: it refers to the combinator
# labels and leaves defining them to the module, which puts the prelude at the
# top of one, once. Everything above runs on that same pair, so a broken one
# would brick the next build: extract, probe, and only then install.
#
# compile_to_dag_with_spans is not extracted here. Built from these sources it
# cannot answer the probe at all: its result is not a list, so nothing can read
# it as a DAG. No test covers it either — the spanned tests reach
# syntax_to_native directly rather than through _compiler_lower, which is the
# step it takes and they do not. Until that is fixed, the working copy lambada
# ships beats the one this would install over it.
>&2 echo "Exporting compiler"
compiler=submodules/lambada/compiler
main="node submodules/tree-calculus/bin/main.js"
$dag extract --symbol Lambada.compile_to_dag src/.dag-bundle-canonical \
  | $dag canonicalize > "$compiler/compile_to_dag.dag.new"

# The prelude goes out as the DAG lines it is, not as a tree that encodes them,
# so putting it in front of a chunk is concatenating a file.
$dag extract --symbol Lambada.prelude src/.dag-bundle-canonical \
  | $dag canonicalize | $main -dag -file /dev/stdin -string > "$compiler/prelude.dag.new"

# Probed together, the way a caller uses them: compile `x = △` and read `x`
# back out of the module the prelude and that chunk make.
probe=$( { cat "$compiler/prelude.dag.new"
           $main -dag -file "$compiler/compile_to_dag.dag.new" -string 'x = △' -string
         } | $dag eval --symbol x --format term 2>/dev/null || true)
case "$probe" in
  '△') for symbol in compile_to_dag prelude; do
         mv "$compiler/$symbol.dag.new" "$compiler/$symbol.dag"
       done ;;
  *) rm -f "$compiler"/*.dag.new
     >&2 echo "ERROR: the extracted compiler and prelude do not compile 'x = △' to the leaf;"
     >&2 echo "       the shipped ones are left alone. Got: $probe"
     exit 1 ;;
esac

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
