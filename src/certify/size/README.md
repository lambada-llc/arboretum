# Certifying size programs

This directory is the size instance of `Certify`: [`size.lamb`](./size.lamb)
defines the certifiers (`Certify.Size.computes_size`,
`Certify.Size.computes_size_eagerly`, and the certificate-producing
`Certify.Size.certify_size`), [`test.lamb`](./test.lamb) exercises them on
programs the library does not use, and the files below export certificates
to Lean.

## Lean-verified size records

[`lean.lamb`](./lean.lamb) defines `Certify.Size.lean_size_proof` — a tree-calculus program that **emits** a
self-contained Lean 4 module for a size program. The whole program is what
goes in, exactly as with the certifier: the loop value the induction
quantifies over is discovered by replay — the first closed value the
program applies to an opaque variable — and the theorem tying the program
to the invariant is itself proved by replaying the wrapper, not assumed
from its shape. The proof is printed as a pure term: one `App` constructor per reduction
step, the induction hypotheses plugged in at exactly the recursion points,
and the endgame equalities as explicit `congrArg`/`Eq.trans` chains. The
certifier's primitives map one-to-one — the match on the input is SPLIT,
the quantified next argument is RGEN's residual, the recursive calls are
FOLDs at GEN-TREE's minted arguments, and every constructor one NORMALIZE
step — so each module is a bespoke proof object for its program, not a
tactic script.

[`lean_test.lamb`](./lean_test.lamb) demonstrates it as file-style expect tests; the modules land in
[`expect-test-out/`](./expect-test-out/) —
`SizeProof125.lean` (the previous record `size__smallest`),
`SizeProof118.lean` and `SizeProof103.lean` (the current records). The lazy
100 gets `none` rather than a module: it converges in normal order only, so
there is no big-step computation to replay; exporting the lazy certificates
(CUT/ABSTRACT phase structure over small-step semantics) is future work.

## Checking a module

Each module is self-contained ASCII with no imports and no `sorry`. With
[elan](https://github.com/leanprover/elan) installed, from this directory
(the `lean-toolchain` file pins the version):

```bash
lean expect-test-out/SizeProof103.lean
```

No output means Lean accepts every theorem. Tactics appear only in the
program-independent scaffolding (the two stack lemmas, determinism, and the
termination side conditions); the per-program proof is a term the kernel
checks directly, and `#print axioms` on the final theorems reports only
`propext` and `Quot.sound`.

## What the theorems say

For the program `prog` stated in each module: `App prog t (snat (sz t))`
for **every** tree `t` — applied to any input it evaluates to the unary
numeral for that input's node count — and by determinism (`prog_unique`)
that value is the only possible result. A derivation of the big-step
relation `App` evaluates every premise, so each theorem packages
convergence and the answer; order-independence additionally rests on
confluence of the calculus, which is argued in the repository and not
formalized here.

This covers `size__eager_103` as well, whose chain recursion is no subtree
recursion: the strong induction on node count that closes it here is the
same measure the certifier's RGEN/GEN-TREE rules encode — the Lean export
and the certifier extension were built against each other.
