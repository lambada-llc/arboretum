# An inductive system for certifying lazy `size` programs

This is the rule system implemented in `certify.py`. It extends the certifier
in `src/certify/size.lamb` (NORMALIZE / PEEL / SPLIT / FOLD / GENERALIZE) with
four new rules — SPEC-SPLIT, ABSTRACT, CUT and ★ — designed so that programs
which compute `size` *only under normal-order evaluation* admit finite
certificates. The base system cannot do this; the measurements that force each
extension are described alongside the rule that answers them.

## The judgment

    Γ ⊢ s ⊨ E

`s` is a symbolic machine state: the quoted program applied to an opaque input
variable, head-normalized on a budget (full normal forms need not exist here —
that is the point). `E` is a multiset of atoms:

    1        one successor is owed
    |t|      the node count of tree variable t is owed
    n        the value of Snat variable n is owed
    ⟨★⟩      a tail: "whatever the continuation owes" — at most one per spec

Γ carries the induction hypotheses `(S, E, v)`: at a SPLIT of variable `v` in
state `S` owing `E`, the claim becomes assumable for instances that send `v`
strictly below itself.

Soundness statement: if `⊢ p·x ⊨ [|x|]` derives, then for every tree `t`,
`p t` reduces in normal order to the Snat numeral of the node count of `t`.

## The base rules (unchanged)

    ───────────── ZERO            ────────────────── VALUE
    Γ ⊢ △ ⊨ ∅                    Γ ⊢ n ⊨ [n]

    Γ ⊢ x ⊨ E                     Γ, (S,E,v) ⊢ S[v:=σᵢ] ⊨ Eᵢ   (all shapes i)
    ─────────────────── PEEL      ──────────────────────────────────── SPLIT
    Γ ⊢ △x ⊨ E ⊎ [1]             Γ ⊢ S ⊨ E    (v blocked; |v| or v ∈ E)

SPLIT's shapes: a tree is `△`, `△a`, or `△a b`, rewriting `|v|` to `[1]`,
`[1,|a|]`, `[1,|a|,|b|]`; an Snat is `△` or `△m`, rewriting `n` to `∅`,
`[1,m]`. Exhaustive, by the defining equations of size.

    (S, E_h, v) ∈ Γ    σ(S) ≡ s    σ(v) strictly below v    σ(E_h) = E
    ──────────────────────────────────────────────────────────────────── FOLD
    Γ ⊢ s ⊨ E

    (S,E_h,v) ∈ Γ   σ(S) ≡ c for subterm c of s   σ(E_h) ⊆ E   n fresh
    ──────────────────────────────────────────────────────────────────── GEN
    Γ ⊢ s ⊨ E   from   Γ ⊢ s[c := n] ⊨ (E − σ(E_h)) ⊎ [n]

## The extensions

**SPEC-SPLIT.** A lazy program emits successors before consulting its input:
the state is `△x` with no `1` in the spec and nothing blocked. Every tree has
at least one node, so a `|v|` owed in the spec licenses splitting `v` even
though reduction is not waiting on it. Same shapes, same soundness as SPLIT.

**ABSTRACT** (induction strengthening). Measured obstruction: these machines
carry copies of the input that lag one constructor behind the live occurrence
— level k+1's state is level k's with `v := △v'` *except* at dead copy
positions, so no fold instance exists. Rule:

    Γ ⊢ s[p₁:=J₁, …, pₖ:=Jₖ] ⊨ E      (Jᵢ fresh opaque variables)
    ──────────────────────────────────────────────────────────── ABSTRACT
    Γ ⊢ s ⊨ E

Sound: an opaque variable stands for an arbitrary tree, and instantiating
Jᵢ back to the replaced subterms recovers exactly `s ⊨ E`. The premise's
proof can never case on Jᵢ (splitting needs the variable in the spec, and
the Jᵢ are not), so instantiation by arbitrary — even divergent — junk is
harmless *under normal-order semantics*. This rule is NOT sound for the
eager certificate, and is enabled only in the lazy prover.

Positions are found by anti-unification against a hypothesis a fold could
use (same core arity, tail iff tail): where the split variable captured
anything other than its strictly-smaller image, and small (the measured lag
junk is 2–7 nodes; large mismatches are live structure).

When a phase ends inside an ABSTRACT (or GEN), its recorded end states are
re-instantiated (`Jᵢ := junk`) on the way out — the ∀-proof covers the
original by instantiation, and the continuation needs the original.

**CUT and ★** (the tail). Measured obstruction: splitting a fork rewrites
`|v|` to `[1,|a|,|b|]`, and left-nested forks grow the spec without bound —
at depth d the spec reaches d atoms, so no finite family of hypotheses
closes the induction (confirmed empirically: max spec arity 6 at depth 8,
8 at depth 10). The spec needs a way to say "and then the rest":

    Γ ⊢ s ⊨ E ⊎ [⟨★⟩]    every recorded end state es:  Γ ⊢ es ⊨ F
    ────────────────────────────────────────────────────────────── CUT
    Γ ⊢ s ⊨ E ⊎ F

    ──────────────────── ★-CLOSE (records s as an end state)
    Γ ⊢ s ⊨ [⟨★⟩]

Reading: the phase proof shows `s` emits `val(E)` successors and then reaches
one of finitely many end states; each end state then owes `F`. Composition
gives `E ⊎ F`. FOLD treats ⟨★⟩ as an atom that must be present on both sides;
a hypothesis recorded inside a phase closes that phase's self-similar
instances at fixed arity, which is what kills the unbounded-arity problem.

End states from FOLD-closed branches are σ-instances of recorded end states,
and the obligation proofs are ∀-general in their free variables, so the
recorded set generates all of them — with one exception, which is the open
edge below.

## The borrow check (second pass)

A FOLD may bridge two different tails (a hypothesis recorded under one cut,
used under another). Its proof then borrows the hypothesis's end states for a
different continuation, which is sound exactly when those end states — the
★-leaves of the hypothesis's own split subtree, under the fold's substitution
— also satisfy the borrowing cut's spec. `validate_cross` walks the finished
proof, collects this borrow graph, and proves the extra obligations,
iterating on any new borrows those proofs introduce (to a bounded number of
rounds). A proof is only reported `true` once every borrow is discharged.

## Status

All twelve eager size programs certify (unchanged verdicts), all eight
non-size programs are rejected — including `counts_forever` (a lazy
infinite emitter), `deep_bug` (agrees with size on all inputs up to four
nodes), and `compose Snat.from_nat size` (is size, counts in binary — still
conservatively rejected). Verdict parity with `src/certify/size.lamb` was
verified before any extension was added.

`size__lazy_100` certifies with all borrow obligations verified: depth 5,
~16s in this prototype, 166 prove-steps. The rendered proof is
`proofs/lazy100.txt`. Results for the other five are recorded in
`proofs/RESULTS.txt` as measured.

## What is knowingly conservative

False still means "no proof within bounds": the search is bounded by split
depth, head-reduction budgets, abstraction caps and borrow-validation
rounds; the binary-counting size stays out of reach of the unary spec by
design; and any lazy program whose junk or continuation geometry defeats
the abstraction heuristics fails conservatively, never unsoundly.
