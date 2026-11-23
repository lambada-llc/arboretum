# term codec

`Codec.shrink Codec.Term.codec t` is a tree that acts as `t`, applied to
anything, and is never larger; for a large compiled program it is much smaller.
It is `Codec.Term.encode t`, the smallest tree `g` it finds with `g fix = t`,
wrapped by [`Codec.defer`](../codec.lamb) so that it works out `g fix` only once
applied. It sees only the tree. It is a
definition like any other, evaluated by the build with the rest of the
library. [selfie.lamb](../../pico/matrix/selfie/selfie.lamb) uses it, and its tests
keep the sizes.

`g` is given `fix` rather than nothing because evaluation is eager: a `g` that
ignored its argument would be worked out, into `t`, before it was applied.

## How

`g = λf. bootstrap f decoder △ f (data t)`

- **Read.** LambAda compiles by Kiselyov's algorithm, and evaluation leaves
  only the `△` shapes of the combinators it emits, so a closed tree is read as
  the combinator it is, short of some arguments, and given fresh variables
  until it has them all: each step it then takes is an application the
  compiler made that combinator for, and what is left is the λ-term's body. A
  step is taken only where the compiler would have made the combinator for it
  (the conditions are with the rules in [term.lamb](term.lamb));
  anything else is the closed function it is, applied as written, and data is
  `△` applied to its parts. So the term compiles back to the tree by
  construction: one pass, nothing tried twice, nothing compiled to check.
- **Data.** The term, as a tree, in a grammar of its own (the comment under
  *The data*). A variable is written by its de Bruijn index or by the level of
  its binder, whichever is shorter, in bijective binary; a chain of λs is one
  form; and so are LambAda's ways of taking a pair and a tree apart, and `fix`
  applied to λs. A closed part is written as its term or as its value,
  whichever is smaller where it stands.
- **Decoder.** Decodes the data and compiles it the way LambAda does, so that
  the result, evaluated, is the tree. It recognises a variable by its compiled
  form being `I`; a program with another term compiling to `I` where the η
  rules look decodes to another tree, which `encode`'s check catches.
- **Bootstrap.** A closure compiler for a small λ-language with variables in
  binary; it runs the decoder, which is written in that language — in
  LambAda's own syntax, as a term under construction (the comment above
  `_mk`). The `fix` `g` is given serves the bootstrap, the decoder and the
  program.

`encode` takes a candidate only if it gives `t` back, so the check is the
whole contract: the tree above is one candidate, and `K t`, which gives `t` back
for any argument and is two nodes more than `t`, is the other. Any other way of
making `g` only has to join them. The check is most of what `encode` costs.

## Sharing a repeated subterm, and why it is not here

The payload is nearly all data — of the 9,336 nodes `encode` makes of
[the selfie's program](../../pico/matrix/selfie/selfie.lamb), 7,318 are the
data, 1,998 the decoder and the bootstrap, which are the same whatever the
program, and the rest the frame around them. That data is a redundant tree:
7,318 nodes over 1,764 distinct subtrees. Writing a repeated subterm once is
the obvious next saving, and it needs nothing new from the grammar — `let x = e
in b` is `(λx. b) e`, and a λ, an application and a variable are forms it has
already. It was built and measured, and it is not here. Three things bite, in
this order:

**A binding only reduces where evaluation reaches it.** `g fix` has to give the
*tree* back, not a tree that acts as it, and a β-redex under a λ that is never
applied stays in the tree: `λx. ((λz. b) e)` compiles to `R e (λx λz. b)`.
Since a program is a function, the redexes that do reduce are the ones above
its own λs — `(λz. b) e` with nothing over it, and, each λ of that chain being
applied to its own argument, another inside it. So bindings can only chain at
the top. Binding at the lowest common ancestor of a cluster of uses, which is
what the *Cost* section below asks a program to do for itself, is not open to
the encoder.

**That makes every reference a long one.** A variable costs two nodes for the
innermost binder and four or more for one further out, and a binder at the top
is as far out as it gets: four nodes a use, plus four for the λ and the
application. Only the outermost binder of all has no level form — references to
it are by index, which grows with the depth of the use — so a chain has to open
with a binder nothing refers to.

**And a bound occurrence is no longer closed, which the compiler reads.** It
chooses by closedness: for `λx. (X x) Y` it writes `R Y X` where `Y` is closed
and `C X Y` where `Y` has variables of its own (the rules above `_last`). The
two are the same function and different trees, so taking an occurrence in `Y`'s
place turns an `R` into a `C` and the tree is not the tree. Occurrences can be
taken where no such step is above them — walking out, each application the
occurrence stands in the argument of must have an argument that already had
variables of its own, or a function that is closed and that nothing was taken
from — and the rest have to stay written out.

What is left pays nothing here, and the measurement says why. The redundancy is
real but it is in subtrees shorter than a reference: summed over the distinct
subtrees of that data, (uses − 1) × size is 1,916 for subtrees of one or two
nodes, 4,245 for three or four and 6,258 for five to eight, against 2,459 for
everything above sixteen. Allowing a binder for *any* repeated subtree of the
data — which a λ cannot do, since it can only bind a subterm — and charging the
four nodes a reference and a binder cost, 141 of the 1,764 would pay at all,
2,389 nodes in total if they did not overlap, and the best single one 116. The
pass that was built, binding repeated closed subtrees in a chain at the top,
measured 7,448 nodes against 7,318 with the closedness rule above and 7,328
without it: worse either way.

It does find what is left, and rarely: of sixteen of this library's functions,
three improved — `Int.add` 2,666 → 2,081, `Nat.to_string` 2,683 → 2,308,
`Nat.divmod` 1,991 → 1,838 — one more would have but did not give the tree
back, and the other twelve came out the same or a few nodes worse. A program
written the way the *Cost* section asks has already bound what repeats, and the
selfie's is. The pass also reads the whole term once a candidate, which took
about a hundred seconds on a program this size and had not finished in twenty
minutes on `Lambada.parse_expr`, so it would need a bound on its own work
before it could live in a build. Sharing below the price of a reference is
what [`Codec.Sharing`](../sharing/) is for, and on this payload that loses too:
`Codec.Sharing.encode` of it is 13,663 nodes.

## Cost

Reading is a function of the tree and of little else, and the build's
evaluator remembers every application, so a tree met again costs nothing.
Evaluation is eager, which shapes the code: see the comment at the top of
[term.lamb](term.lamb).

`g` does its own work when it is given `fix`, on a machine that may remember
nothing: it decodes and compiles all of `t` first. What that costs
grows with how far out the variables each part uses are bound, so a program
meant to be compressed binds what its inner code uses close to it.
