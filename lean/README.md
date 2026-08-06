# Lean-verified size records

[`SizeRecords.lean`](./SizeRecords.lean) is a self-contained Lean 4 module —
no imports, no dependencies — that re-verifies the two record programs of
[`src/snat/size.lamb`](../src/snat/size.lamb) from first principles:

* it defines triage calculus (the five reduction rules) as a big-step
  evaluation relation `App` over unlabelled binary trees;
* it defines the node count `sz` and the unary numeral encoding `snat`;
* it states `prog118` and `prog103` as tree literals that are node for node
  `Snat.size__eager_118` and `Snat.size__eager_103`;
* it proves, for both, that applied to *any* tree they evaluate to the
  numeral for that tree's node count, and that this value is unique:

  ```
  theorem prog118_computes_size : ∀ t, App prog118 t (snat (sz t))
  theorem prog103_computes_size : ∀ t, App prog103 t (snat (sz t))
  theorem App.det : App a b c → App a b c' → c = c'
  ```

A derivation of `App a b c` is a complete computation record — every premise
of every rule is itself an evaluated application — so each theorem packages
convergence and the answer in one statement. The proofs follow the shape of
the certificates `Certify.certify_size` emits: induction over the input
(SPLIT), an invariant generalised over the accumulator (GENERALIZE),
induction hypotheses at the recursive calls (FOLD), and one `App` constructor
per reduction step (NORMALIZE). The derivation terms were generated
mechanically by replaying the symbolic eager reduction of the actual program
trees; the scaffolding and endgames are hand-written.

Where the in-repo certifier's induction only closes over recursion on strict
subtrees — which is why `size__eager_103`'s verdict there is a conservative
`false` — the strong induction on `sz` here has no such restriction, so the
103 gets a full proof too.

## Checking it

With [elan](https://github.com/leanprover/elan) installed, from this
directory (the `lean-toolchain` file pins the version):

```bash
lean SizeRecords.lean
```

No output means Lean accepts every theorem. The proofs use no `sorry` and no
classical reasoning: `#print axioms` on either final theorem reports only
`propext` and `Quot.sound`, Lean's benign structural axioms.
