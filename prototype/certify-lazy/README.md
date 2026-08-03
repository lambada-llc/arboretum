# Prototype: certifying lazy size programs

A reference implementation, in Python, of the inductive system that extends
`src/certify/size.lamb` to certify programs which compute `size` only under
normal-order evaluation — the `__lazy` family in `src/snat/size.lamb`.

- `RULES.md` — the judgment and inference rules, with soundness arguments
- `certify.py` — the prover: spine reduction, budgeted normalization, and the
  rules NORMALIZE / PEEL / SPLIT / SPEC-SPLIT / FOLD / GENERALIZE / ABSTRACT /
  CUT / ★, plus the borrow-validation second pass and a proof-tree renderer
- `trees/*.term` — the actual program trees, dumped from the built bundle
- `proofs/` — rendered proof trees for the certified programs

Run `python3 certify.py` for the verdict table. This is the specification for
a future port of the rules into `src/certify/size.lamb`; the .lamb certifier
in the library is unchanged and keeps its verdicts.
