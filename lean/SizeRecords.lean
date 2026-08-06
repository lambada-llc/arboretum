/-
# Triage calculus, and two record-size programs, verified

Self-contained Lean 4 module (no imports). It defines:

* the values of triage calculus — unlabelled binary trees — and its five
  reduction rules, as a big-step evaluation relation `App`;
* the node-count function `sz` and the unary numeral encoding `snat`;
* the two record programs from arboretum's `src/snat/size.lamb`,
  node for node: `prog118` is `Snat.size__eager_118` (118 nodes, the
  smallest eager-safe size program with an in-repo certificate) and
  `prog103` is `Snat.size__eager_103` (103 nodes, the smallest known);
* the validity theorems: applied to any tree `t`, each program evaluates
  to the numeral for the node count of `t` —

    theorem prog118_computes_size : ∀ t, App prog118 t (snat (sz t))
    theorem prog103_computes_size : ∀ t, App prog103 t (snat (sz t))

A derivation of `App a b c` is a complete computation record: every
premise of every rule is itself an evaluated application, so the theorem
packages both convergence and the answer. The proofs mirror the structure
of the certificates the repository's `Certify` analysis emits — one
induction over the input (SPLIT), an invariant generalised over the
accumulator (GENERALIZE), induction hypotheses at the recursive calls
(FOLD), and one `App` constructor per reduction step (NORMALIZE); the
derivation terms were generated mechanically by replaying the symbolic
eager reduction of the actual program trees. Notably, `prog103` recurses
on a re-built tree rather than a subtree, which is exactly what the
repository's certifier cannot close an induction over (its verdict there
is a conservative `false`); the strong induction on `sz` below closes it.
-/

inductive Tree where
  | leaf : Tree
  | stem : Tree → Tree
  | fork : Tree → Tree → Tree
deriving Repr, DecidableEq

open Tree

/-- Shorthands, so the program literals below stay readable. -/
abbrev L : Tree := leaf
abbrev S : Tree → Tree := stem
abbrev F : Tree → Tree → Tree := fork

/-- Node count of a tree. -/
def sz : Tree → Nat
  | leaf => 1
  | stem t => sz t + 1
  | fork l r => sz l + sz r + 1

/-- `n` stems stacked on top of `s`. -/
def stack : Nat → Tree → Tree
  | 0, s => s
  | n + 1, s => stem (stack n s)

/-- The unary numeral for `n`: a chain of `n` stems over a leaf. -/
def snat (n : Nat) : Tree := stack n leaf

theorem stack_stack (a b : Nat) (s : Tree) :
    stack a (stack b s) = stack (a + b) s := by
  induction a with
  | zero => simp [stack]
  | succ n ih => simp [stack, ih, Nat.succ_add]

theorem sz_stack (n : Nat) (s : Tree) : sz (stack n s) = n + sz s := by
  induction n with
  | zero => simp [stack]
  | succ n ih => simp [stack, sz, ih]; omega

/--
Big-step application for triage calculus: `App a b c` holds when the value
`a` applied to the value `b` evaluates to the value `c`. The last three
rules are the K, S and triage rules of the calculus
(https://github.com/lambada-llc/tree-calculus/tree/main/reduction-rules);
the first two record that applying a leaf or a stem just grows the tree.
-/
inductive App : Tree → Tree → Tree → Prop where
  /-- `△ b` is the stem of `b`. -/
  | grow0 {b} : App leaf b (stem b)
  /-- `(△ x) b` is the fork of `x` and `b`. -/
  | grow1 {x b} : App (stem x) b (fork x b)
  /-- Rule (1): `△ △ y z ⟶ y`. -/
  | rK {y z} : App (fork leaf y) z y
  /-- Rule (2): `△ (△ x) y z ⟶ x z (y z)`. -/
  | rS {x y z r₁ r₂ r} : App x z r₁ → App y z r₂ → App r₁ r₂ r →
      App (fork (stem x) y) z r
  /-- Rule (3a): `△ (△ w x) y △ ⟶ w`. -/
  | r3a {w x y} : App (fork (fork w x) y) leaf w
  /-- Rule (3b): `△ (△ w x) y (△ u) ⟶ x u`. -/
  | r3b {w x y u r} : App x u r → App (fork (fork w x) y) (stem u) r
  /-- Rule (3c): `△ (△ w x) y (△ u v) ⟶ y u v`. -/
  | r3c {w x y u v r₁ r} : App y u r₁ → App r₁ v r →
      App (fork (fork w x) y) (fork u v) r

/-- Evaluation is deterministic: a tree applied to a tree has at most one
value. Together with the theorems at the bottom this makes the size
numeral *the* result of running each program, not just one possibility. -/
theorem App.det {a b c c' : Tree} (h : App a b c) (h' : App a b c') : c = c' := by
  induction h generalizing c' with
  | grow0 => cases h'; rfl
  | grow1 => cases h'; rfl
  | rK => cases h'; rfl
  | rS h1 h2 h3 ih1 ih2 ih3 =>
    cases h' with
    | rS g1 g2 g3 => obtain rfl := ih1 g1; obtain rfl := ih2 g2; exact ih3 g3
  | r3a => cases h'; rfl
  | r3b h ih => cases h' with | r3b g => exact ih g
  | r3c h1 h2 ih1 ih2 =>
    cases h' with
    | r3c g1 g2 => obtain rfl := ih1 g1; exact ih2 g2

/-! ## The programs

`K14` is the 14-node quine knot `_k = const (triage △ △ (\q q (△ q)))`.
For a step function `B`, `Q B` is the code value `\sq B (△ (△ _k) sq)`,
`SELF B = △ (△ _k) (△ (Q B))` is the tied loop, and `prog B = \x SELF x △`
is the program. `B118` is the record step (`_functional_smallest`),
`B103` the chain step (`_chain_step`); the resulting trees are node for
node the `Snat.size__eager_118` and `Snat.size__eager_103` of
arboretum's `src/snat/size.lamb`. -/

def K14 : Tree := (F L (F (F L L) (F (S (F (S (S L)) L)) L)))

def B118 : Tree := (F (S (F L (S (S (F L (S (S (F L L)))))))) (F (S (F (S (F L L)) (S (F (S (S L)) L)))) (F (S (F (S (F L (F (S (F L (F (S (F L L)) L))) (S L)))) (F (S (F L (F (S (F L L)) L))) (S (S (F L (F (S (F L (F (S (F L L)) L))) (S L)))))))) (S (S (F L (S L)))))))

def B103 : Tree := (F (S (F L (S (S (F L (S (S (F L L)))))))) (F (S (F (S (F L L)) (S (F (S (S L)) L)))) (F (S (F (S (F L (F (S (F L (F (S (F L L)) L))) (S L)))) (F (S (F L (F (S (F L L)) L))) (S L)))) (F (S (S L)) L))))

def Q (B : Tree) : Tree := F (S (F L B)) (S (S K14))

def SELF (B : Tree) : Tree := F (S K14) (S (Q B))

def prog (B : Tree) : Tree := F (S (SELF B)) (F L L)

def prog118 : Tree := prog B118
def prog103 : Tree := prog B103

/-- The node counts the programs are named after. -/
example : sz prog118 = 118 := by rfl
example : sz prog103 = 103 := by rfl

/-! ## The invariant

For every input `t`, `SELF B` applied to `t` evaluates to a function
value that stacks `sz t` stems onto whatever it is applied to next. This
is the certificate's content: the induction over `t` is its SPLIT, the
quantification over `s` its GENERALIZE, the uses of the induction
hypotheses its FOLDs, and every `App` constructor below one NORMALIZE
step of the machine. -/

theorem self118_spec (t : Tree) :
    ∃ f, App (SELF B118) t f ∧ ∀ s, App f s (stack (sz t) s) := by
  match t with
  | leaf =>
    exact ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) App.grow1 App.grow1) App.grow1) App.grow1))) (App.rS App.rK App.r3a App.grow1))), fun s => (App.rS App.rK (App.rS App.grow1 App.grow0 App.rK) App.grow0)⟩
  | stem u =>
    obtain ⟨fu, hfu1, hfu2⟩ := self118_spec u
    exact ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) App.grow1 App.grow1) App.grow1) App.grow1))) (App.rS App.rK (App.r3b hfu1) App.grow1))), fun s => (App.rS App.rK (hfu2 s) App.grow0)⟩
  | fork u v =>
    obtain ⟨fu, hfu1, hfu2⟩ := self118_spec u
    obtain ⟨fv, hfv1, hfv2⟩ := self118_spec v
    refine ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) App.grow1 App.grow1) App.grow1) App.grow1))) (App.rS App.rK (App.r3c (App.rS App.rK (App.rS App.rK hfu1 App.grow1) App.grow1) (App.rS (App.rS App.rK hfv1 (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) App.rK App.grow1)) App.grow1))), fun s => ?_⟩
    have h := (App.rS App.rK (App.rS App.rK (hfu2 s) (hfv2 (stack (sz u) s))) App.grow0)
    have e : stack (sz v) (stack (sz u) s) = stack (sz u + sz v) s := by
      rw [stack_stack, Nat.add_comm]
    rw [e] at h
    exact h
termination_by sz t
decreasing_by all_goals (simp only [sz]; omega)

theorem self103_spec (t : Tree) :
    ∃ f, App (SELF B103) t f ∧ ∀ s, App f s (stack (sz t) s) := by
  match t with
  | leaf =>
    exact ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) (App.rS App.grow1 App.grow0 App.rK) App.grow1) App.grow1) App.grow1))) (App.rS App.rK App.r3a App.grow1))), fun s => (App.rS App.rK (App.rS App.grow1 App.grow0 App.rK) App.grow0)⟩
  | stem u =>
    obtain ⟨fu, hfu1, hfu2⟩ := self103_spec u
    exact ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) (App.rS App.grow1 App.grow0 App.rK) App.grow1) App.grow1) App.grow1))) (App.rS App.rK (App.r3b hfu1) App.grow1))), fun s => (App.rS App.rK (hfu2 s) App.grow0)⟩
  | fork u v =>
    obtain ⟨fu, hfu1, hfu2⟩ := self103_spec u
    obtain ⟨fc, hfc1, hfc2⟩ := self103_spec (stack (sz u) v)
    refine ⟨_, (App.rS App.rK App.grow1 (App.r3c (App.rS (App.rS App.grow1 App.grow0 App.rK) App.grow0 (App.rS App.rK App.grow1 (App.rS App.rK (App.rS (App.rS App.rK App.grow1 App.grow0) (App.rS (App.rS App.rK (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0)) (App.rS App.rK App.grow1 (App.rS App.rK App.grow0 App.grow0))) (App.rS App.grow1 App.grow0 App.rK) App.grow1) App.grow1) App.grow1))) (App.rS App.rK (App.r3c (App.rS App.rK hfu1 App.grow1) (App.rS App.rK (hfu2 v) hfc1)) App.grow1))), fun s => ?_⟩
    have h := (App.rS App.rK (hfc2 s) App.grow0)
    rw [sz_stack] at h
    exact h
termination_by sz t
decreasing_by all_goals (simp only [sz, sz_stack]; omega)

/-! ## The theorems -/

/-- `Snat.size__eager_118` computes size: applied to any tree it
evaluates to the unary numeral for that tree's node count. -/
theorem prog118_computes_size (t : Tree) : App prog118 t (snat (sz t)) := by
  obtain ⟨f, h1, h2⟩ := self118_spec t
  exact App.rS h1 App.rK (h2 leaf)

/-- `Snat.size__eager_103` computes size — including the chain
recursion the in-repo certifier could not close an induction over. -/
theorem prog103_computes_size (t : Tree) : App prog103 t (snat (sz t)) := by
  obtain ⟨f, h1, h2⟩ := self103_spec t
  exact App.rS h1 App.rK (h2 leaf)

/-- Uniqueness: anything `prog118 t` evaluates to is the size numeral. -/
theorem prog118_unique {t r : Tree} (h : App prog118 t r) : r = snat (sz t) :=
  App.det h (prog118_computes_size t)

/-- Uniqueness: anything `prog103 t` evaluates to is the size numeral. -/
theorem prog103_unique {t r : Tree} (h : App prog103 t r) : r = snat (sz t) :=
  App.det h (prog103_computes_size t)
