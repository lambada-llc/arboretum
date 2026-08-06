# Lean-verified size records

Two ways the size records get foundational proofs:

## Generated in-repo: `Certify.lean_size_proof`

[`src/certify/lean.lamb`](../src/certify/lean.lamb) defines a tree-calculus
program that **emits** a self-contained Lean 4 module for a size program: it
recognises the knotted-loop shape, replays the program's own eager reduction
symbolically — one `App` constructor per reduction step — and renders the
certifier's primitives as an induction Lean re-checks from the five reduction
rules alone (the match on the input is SPLIT, the quantified next argument is
RGEN's residual, the recursive calls are FOLDs at GEN-TREE's minted
arguments).

[`src/certify/lean_test.lamb`](../src/certify/lean_test.lamb) demonstrates it
as file-style expect tests; the modules land in
[`src/certify/expect-test-out/`](../src/certify/expect-test-out/) —
`SizeProof125.lean` (the previous record `size__smallest`),
`SizeProof118.lean` and `SizeProof103.lean` (the current records). Each is
accepted by `lean` as-is: no imports, no `sorry`, axioms `propext` and
`Quot.sound` only. The lazy 100 gets `none` rather than a module: it
converges in normal order only, so there is no big-step computation to
replay; exporting the lazy certificates (CUT/ABSTRACT phase structure over
small-step semantics) is future work.

## Hand-assembled: `SizeRecords.lean`

[`SizeRecords.lean`](./SizeRecords.lean) is the original, hand-assembled
module covering both current records in one file, with the same theorems
plus uniqueness corollaries and fuller prose. Same guarantees: (with elan
installed, from this directory — `lean-toolchain` pins the version)

```bash
lean SizeRecords.lean
```

No output means Lean accepts every theorem.

## What the theorems say

For each program `p`: `App p t (snat (sz t))` for **every** tree `t` — the
program applied to any input evaluates to the unary numeral for that input's
node count — and by `App.det` that value is unique. A derivation of the
big-step relation `App` evaluates every premise, so each theorem packages
convergence and the answer; order-independence additionally rests on
confluence of the calculus, which is argued in the repository and not
formalized here.

These proofs cover `size__eager_103` as well, whose chain recursion is no
subtree recursion: the strong induction on node count that closes it in Lean
is the same measure the certifier's RGEN/GEN-TREE rules encode — the Lean
export and the certifier extension were built against each other.
