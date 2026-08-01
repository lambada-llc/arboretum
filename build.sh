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

# Evaluate the top-level expressions, recording results in the sources
>&2 echo "Running tests"
$lambada expect-test src/.dag-bundle-canonical --root src

# Take the compiler back out of the bundle it is part of, so that the lambada
# submodule ships the compiler this repository just built from its source.
# Everything above runs on that same compile_to_dag.dag, so a broken one would
# brick the next build: extract first, probe, and only then install.
>&2 echo "Exporting compiler"
compiler=submodules/lambada/compiler
for symbol in compile compile_to_dag; do
  $dag extract --symbol "Lambada.$symbol" src/.dag-bundle-canonical \
    | $dag canonicalize > "$compiler/$symbol.dag.new"
done

probe=$(node submodules/tree-calculus/bin/main.js \
  -dag -file "$compiler/compile_to_dag.dag.new" -string 'x = △' -string 2>/dev/null || true)
case "$probe" in
  ':t '*) for symbol in compile compile_to_dag; do mv "$compiler/$symbol.dag.new" "$compiler/$symbol.dag"; done ;;
  *) rm -f "$compiler"/*.dag.new
     >&2 echo "ERROR: the extracted compiler cannot compile 'x = △'; the shipped one is left alone."
     exit 1 ;;
esac
