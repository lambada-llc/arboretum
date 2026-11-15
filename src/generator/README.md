# generator

`Generator.compress t` is the smallest tree `g` it finds with `g fix = t`. For
a large compiled program `t` that is much smaller than `t`; `Generator.expand g`
is then a tree that acts as `t`, applied to anything. It sees only the tree. It
is a definition like any other, evaluated by the build with the rest of the
library. [selfie.lamb](../pico/matrix/selfie.lamb) uses it, and its tests keep
the sizes.

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
  (the conditions are with the rules in [generator.lamb](generator.lamb));
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
  rules look decodes to another tree, which `compress`'s check catches.
- **Bootstrap.** A closure compiler for a small λ-language with variables in
  binary; it runs the decoder, which is written in that language — in
  LambAda's own syntax, as a term under construction (the comment above
  `_mk`). The `fix` `g` is given serves the bootstrap, the decoder and the
  program.

`compress` takes a candidate only if it gives `t` back, so the check is the
whole contract: the tree above is one candidate, and `K t`, which gives `t` back
for any argument and is two nodes more than `t`, is the other. Any other way of
making `g` only has to join them. The check is most of what `compress` costs.

## Cost

Reading is a function of the tree and of little else, and the build's
evaluator remembers every application, so a tree met again costs nothing.
Evaluation is eager, which shapes the code: see the comment at the top of
[generator.lamb](generator.lamb).

`g` does its own work when it is given `fix`, on a machine that may remember
nothing: it decodes and compiles all of `t` first. What that costs
grows with how far out the variables each part uses are bound, so a program
meant to be compressed binds what its inner code uses close to it.
