#!/usr/bin/env python3
"""Prototype of the size certifier from src/certify/size.lamb, for fast iteration.

Faithful port of the .lamb system, plus experiments toward certifying the
__lazy size programs. Terms are quoted-encoding spines:
    term = (head, args)   head = '^' (leaf) | ('v', name_tuple)   args = tuple
An application f x is (f.head, f.args + (x,)). The quoted encoding:
    leaf ^, opaque variable ('v',n), application = fork.
"""
import sys, os
sys.setrecursionlimit(100000)

LEAF = ('^', ())

def V(name): return (('v', tuple(name)), ())
def is_leaf(t): return t[0] == '^' and not t[1]
def is_var(t): return t[0] != '^' and not t[1]
def app1(f, x): return (f[0], f[1] + (x,))

# ---------- parsing the dumped .term files (real trees) ----------
def parse_tree(s):
    toks = s.replace('(', ' ( ').replace(')', ' ) ').split()
    pos = 0
    def expr():
        nonlocal pos
        items = []
        while pos < len(toks) and toks[pos] != ')':
            items.append(atom())
        t = items[0]
        for c in items[1:]:
            assert len(t) < 2
            t = t + (c,)
        return t
    def atom():
        nonlocal pos
        if toks[pos] == '(':
            pos += 1
            r = expr()
            assert toks[pos] == ')'
            pos += 1
            return r
        assert toks[pos] == chr(9651), toks[pos]
        pos += 1
        return ()
    return expr()

def load_tree(name):
    with open(os.path.join(os.path.dirname(__file__), 'trees', name + '.term')) as f:
        return parse_tree(f.read())

def quote(tree):
    # quoted rep: leaf stays leaf; children become arguments of leaf
    return ('^', tuple(quote(c) for c in tree))

def tree_size(tree):
    return 1 + sum(tree_size(c) for c in tree)

def term_size(t):
    return 1 + sum(term_size(a) for a in t[1])

# ---------- reduction (spine, budgeted) ----------
class OutOfFuel(Exception): pass

class Fuel:
    __slots__ = ('n',)
    def __init__(self, n): self.n = n
    def spend(self):
        if self.n <= 0: raise OutOfFuel()
        self.n -= 1

def whnf(t, fuel):
    """Head-reduce. Returns (term, blocker_name_or_None)."""
    while True:
        h, args = t
        if h != '^':
            return t, h[1]                     # variable-headed: stuck on it
        if len(args) < 3:
            return t, None                     # value
        a, b, c, rest = args[0], args[1], args[2], args[3:]
        a, ba = whnf(a, fuel)
        if ba is not None:
            return ('^', (a, b, c) + rest), ba
        ah, aargs = a
        if len(aargs) == 0:                    # rule 1: ^ ^ b c -> b
            fuel.spend(); t = (b[0], b[1] + rest)
        elif len(aargs) == 1:                  # rule 2: ^(^x) b c -> x c (b c)
            fuel.spend()
            x = aargs[0]
            t = (x[0], x[1] + (c, (b[0], b[1] + (c,))) + rest)
        else:                                  # rule 3: ^(^ w x) b c -> triage c
            assert len(aargs) == 2
            w, x = aargs
            c, bc = whnf(c, fuel)
            if bc is not None:
                return ('^', (a, b, c) + rest), bc
            ch, cargs = c
            if len(cargs) == 0:   fuel.spend(); t = (w[0], w[1] + rest)
            elif len(cargs) == 1: fuel.spend(); t = (x[0], x[1] + (cargs[0],) + rest)
            else:
                assert len(cargs) == 2
                fuel.spend(); t = (b[0], b[1] + cargs + rest)

def nf(t, fuel):
    """Full normal form (normal order): whnf, then args. Blocker: head first."""
    t, b = whnf(t, fuel)
    h, args = t
    out, blockers = [], []
    for a in args:
        a2, ba = nf(a, fuel)
        out.append(a2); blockers.append(ba)
    for x in [b] + blockers:
        if x is not None: b = x; break
    else: b = None
    return (h, tuple(out)), b

def normalize_fallback(q, budget):
    """nf if it fits the budget, else whnf: the alt(_lazily) states."""
    try:
        return nf(q, Fuel(budget))
    except OutOfFuel:
        pass
    try:
        return whnf(q, Fuel(budget))
    except OutOfFuel:
        return None

# ---------- spec: multiset of atoms ----------
# atom: 1 | ('sz', name) | ('val', name)
ONE = 1
def Sz(v): return ('sz', tuple(v))
def Val(v): return ('val', tuple(v))
def Star(name): return ('star', tuple(name))
def is_star(a): return a != ONE and a[0] == 'star'
def spec_stars(e): return [a for a in e if is_star(a)]
def spec_core(e): return [a for a in e if not is_star(a)]

def ms_minus(f, e):
    """e minus f, or None."""
    e = list(e)
    for x in f:
        if x in e: e.remove(x)
        else: return None
    return e

# ---------- matching ----------
# With reduce_budget > 0 matching is modulo bounded head reduction, and
# coinductive: at a structural mismatch both sides are head-reduced and
# retried, and a variable-free pair of subterms seen before is taken as equal
# -- a self-reproducing unfolding is a cycle, and terms that agree on every
# finite unfolding evaluate alike. `cap` bounds the walk, so failure is clean.
class MatchCtx:
    __slots__ = ('seen', 'cap', 'whnf_budget')
    def __init__(self, cap, whnf_budget):
        self.seen, self.cap, self.whnf_budget = set(), cap, whnf_budget

def match(p, t, s, reduce_budget=0):
    ctx = MatchCtx(cap=20000, whnf_budget=reduce_budget) if reduce_budget else None
    try:
        return _match(p, t, s, ctx)
    except OutOfFuel:
        return None

def _freevars(t, _memo={}):
    r = _memo.get(id(t))
    if r is None:
        r = (frozenset() if t[0] == '^' else frozenset([t[0][1]])) \
            .union(*[_freevars(a) for a in t[1]]) if t[1] else \
            (frozenset() if t[0] == '^' else frozenset([t[0][1]]))
        _memo[id(t)] = r
    return r

def _match(p, t, s, ctx):
    if is_leaf(p):
        if is_leaf(t): return s
        if ctx is not None:
            t2 = _try_whnf(t, ctx.whnf_budget)
            if t2 is not None and t2 != t: return _match(p, t2, s, ctx)
        return None
    if is_var(p):
        n = p[0][1]
        if n in s:
            if s[n] == t: return s
            if ctx is not None and _eq(s[n], t, ctx): return s
            return None
        s2 = dict(s); s2[n] = t
        return s2
    ph, pargs = p
    pf, px = (ph, pargs[:-1]), pargs[-1]
    th, targs = t
    if targs:
        tf, tx = (th, targs[:-1]), targs[-1]
        s2 = _match(pf, tf, s, ctx)
        if s2 is not None:
            r = _match(px, tx, s2, ctx)
            if r is not None: return r
    if ctx is not None:
        # coinductive cut: this exact pair regressing means a self-reproducing
        # unfolding on both sides -- equal on every finite unfolding.
        key = (p, t)
        # cycle: sound when every variable of p is already bound, so the cut
        # cannot lose a binding the fold would have needed.
        if key in ctx.seen and all(v in s for v in _freevars(p)): return s
        if len(ctx.seen) >= ctx.cap: raise OutOfFuel()
        ctx.seen.add(key)
        p2, t2 = _try_whnf(p, ctx.whnf_budget), _try_whnf(t, ctx.whnf_budget)
        if p2 is not None and t2 is not None and (p2 != p or t2 != t):
            return _match(p2, t2, s, ctx)
    return None

def _eq(a, b, ctx):
    """Equality modulo bounded reduction, coinductively (cycle = equal)."""
    if a == b: return True
    key = (a, b)
    if key in ctx.seen: return True
    if len(ctx.seen) >= ctx.cap: raise OutOfFuel()
    ctx.seen.add(key)
    a2, b2 = _try_whnf(a, ctx.whnf_budget), _try_whnf(b, ctx.whnf_budget)
    if a2 is None or b2 is None: return False
    if a2 == b2: return True
    (ah, aargs), (bh, bargs) = a2, b2
    if ah != bh or len(aargs) != len(bargs): return False
    return all(_eq(x, y, ctx) for x, y in zip(aargs, bargs))

def _try_whnf(t, budget):
    try: return whnf(t, Fuel(budget))[0]
    except OutOfFuel: return None

def extends(v, w):
    """w strictly extends v: v is a proper suffix of w."""
    return len(w) > len(v) and w[len(w)-len(v):] == v

def subterms(t):
    """All proper subterms by application decomposition, outermost first."""
    h, args = t
    out = []
    if args:
        f, x = (h, args[:-1]), args[-1]
        out.append(f); out.extend(subterms(f))
        out.append(x); out.extend(subterms(x))
    return out

def replace(needle, name, t):
    if t == needle: return V(name)
    h, args = t
    if not args: return t
    f, x = (h, args[:-1]), args[-1]
    f2, x2 = replace(needle, name, f), replace(needle, name, x)
    return (f2[0], f2[1] + (x2,))

def instantiate(vname, shape, t):
    """Substitute shape for variable vname throughout t."""
    h, args = t
    args2 = tuple(instantiate(vname, shape, a) for a in args)
    if h != '^' and h[1] == tuple(vname):
        return (shape[0], shape[1] + args2)
    return (h, args2)

# ---------- fold ----------
def fold(asm, t, reduce_budget=0):
    """If t instantiates asm's state with the split var strictly below itself,
    return the renamed spec; else None."""
    state, spec, v = asm[0], asm[1], asm[2]
    s = match(state, t, {}, reduce_budget)
    if s is None: return None
    img = s.get(tuple(v))
    if img is None or not is_var(img): return None
    w = img[0][1]
    if not extends(tuple(v), w): return None
    out = []
    star = None
    for a in spec:
        if a == ONE: out.append(ONE)
        elif is_star(a): star = a
        else:
            kind, u = a
            iu = s.get(u)
            if iu is None or not is_var(iu): return None
            out.append((kind, iu[0][1]))
    return out, star, s

# ---------- abstraction (induction strengthening) ----------
def match_collect(p, t, path=''):
    """Full parallel walk: every var capture and every hard mismatch, with paths.
    Returns (caps: name -> [(path, term)], hard: [(path, psub, tsub)])."""
    caps, hard = {}, []
    def go(p, t, path):
        if is_var(p):
            caps.setdefault(p[0][1], []).append((path, t))
            return
        if is_leaf(p):
            if not is_leaf(t): hard.append((path, p, t))
            return
        ph, pargs = p
        th, targs = t
        if not targs:
            hard.append((path, p, t)); return
        go((ph, pargs[:-1]), (th, targs[:-1]), path + 'f')
        go(pargs[-1], targs[-1], path + 'x')
    go(p, t, path)
    return caps, hard

def replace_at(t, path, sub):
    """Replace the subterm at an f/x path with sub."""
    if not path: return sub
    h, args = t
    if path[0] == 'f':
        f2 = replace_at((h, args[:-1]), path[1:], sub)
        return (f2[0], f2[1] + (args[-1],))
    return (h, args[:-1] + (replace_at(args[-1], path[1:], sub),))

def subterms_with_paths(t, path=''):
    h, args = t
    out = []
    if args:
        f, x = (h, args[:-1]), args[-1]
        out.append((f, path + 'f')); out.extend(subterms_with_paths(f, path + 'f'))
        out.append((x, path + 'x')); out.extend(subterms_with_paths(x, path + 'x'))
    return out

# Abstraction candidates, best first: junk positions found by a near-miss
# against a hypothesis, on the whole state and then on subterms (so that a
# sub-machine embedded in the state can be cleaned for GENERALIZE).
def abstract_candidates(asms, e, s, g):
    cands = []
    whole = abstract(asms, e, s, g)
    if whole is not None: cands.append(whole)
    subs = [st for st in subterms_with_paths(s) if term_size(st[0]) > 20]
    subs.sort(key=lambda st: -term_size(st[0]))
    for c, cpath in subs[:40]:
        r = abstract(asms, e, c, g)
        if r is None: continue
        c2, g2, junk = r
        s2 = replace_at(s, cpath, c2)
        cands.append((s2, g2, junk))
        if len(cands) >= 4: break
    return cands

def abstract(asms, e, s, g):
    """Strengthen s for induction: against each hypothesis whose split variable
    already has a strictly-smaller variable image in s, the positions where it
    captured anything else are junk the recursion carries but never consumes --
    replace them (and hard mismatches) with fresh opaque variables. Proving the
    strengthened state proves s: an opaque variable is an arbitrary tree.
    Fresh variables never occur in the spec, so no rule can ever case on them."""
    for state, spec, w, _hid in asms:
        # only a hypothesis a fold could use is a reference for junk detection:
        # same number of size atoms, and a tail exactly when the goal has one.
        if len(spec_core(spec)) != len(spec_core(e)): continue
        if bool(spec_stars(spec)) != bool(spec_stars(e)): continue
        caps, hard = match_collect(state, s)
        w_caps = caps.get(tuple(w), [])
        live = [t for _, t in w_caps if is_var(t) and extends(tuple(w), t[0][1])]
        if not live: continue
        u = live[0]
        # a capture that is itself a strictly-smaller variable is another live
        # position, never junk: the fold that needs it will use finer patterns.
        junk = [(path, t) for path, t in w_caps
                if t != u and not (is_var(t) and extends(tuple(w), t[0][1]))]
        junk += [(path, t) for path, _, t in hard]
        junk = [(path, t) for path, t in junk if term_size(t) > 1 or is_leaf(t)]
        # lag junk is small; a large mismatch is live structure, not junk
        if not junk or len(junk) > 4 or any(term_size(t) > 12 for _, t in junk):
            continue
        names = {}
        s2 = s
        for path, t in sorted(junk, key=lambda pt: pt[0]):
            if t not in names:
                names[t] = (('j', g),); g += 1
            s2 = replace_at(s2, path, V(names[t]))
        if s2 != s:
            return s2, g, [(names[t], t) for t in names]
    return None

def subst_of(asm, t):
    return match(asm[0], t, {})

def tails_compatible(hstar, gstar, s):
    # A tail names the opaque continuation slot: the fold is legal when the
    # hypothesis slot maps to the goal's slot, so both defer the same future.
    if hstar is None or gstar is None: return hstar is None and gstar is None
    if hstar[1] == gstar[1]: return True
    if s is None: return False
    img = s.get(hstar[1])
    return img is not None and img == V(gstar[1])

# ---------- shapes / split ----------
def part(i, v): return (i,) + tuple(v)

def shapes_tree(v):
    a, b = part(0, v), part(1, v)
    return [(LEAF, [ONE], '='),
            (('^', (V(a),)), [ONE, Sz(a)], 's'),
            (('^', (V(a), V(b))), [ONE, Sz(a), Sz(b)], 'f')]

def shapes_snat(v):
    a = part(0, v)
    return [(LEAF, [], '='), (('^', (V(a),)), [ONE, Val(a)], 's')]

# ---------- the prover ----------
class P:
    """Proof node."""
    __slots__ = ('rule', 'info', 'kids')
    def __init__(self, rule, info=None, kids=()):
        self.rule, self.info, self.kids = rule, info, list(kids)

def collect_ends(proof, star_id):
    # The end states a phase reaches. An ABSTRACT (or GEN) node proved its
    # subtree for fresh variables standing for concrete subterms, so its end
    # states cover the original by instantiation: substitute back on the way
    # out, or the continuation loses what the phase abstracted away.
    out = []
    if proof.rule == 'STAR':
        if proof.info[0] == star_id: out.append(proof.info[1])
        return out
    for k in proof.kids:
        if k is not None: out.extend(collect_ends(k, star_id))
    if proof.rule == 'ABSTRACT':
        out = [_subst_all(es, proof.info) for es in out]
    elif proof.rule == 'GEN':
        out = [instantiate(proof.info[0], proof.info[1], es) for es in out]
    return out

def _subst_all(t, subst):
    for name, term in subst:
        t = instantiate(name, term, t)
    return t

class Prover:
    def __init__(self, head_budget=40000, depth=6, reduce_budget=0, spec_split=False,
                 abstract_rule=False, cut_rule=False, trace=False):
        self.head_budget = head_budget
        self.depth = depth
        self.reduce_budget = reduce_budget
        self.spec_split = spec_split
        self.abstract_rule = abstract_rule
        self.cut_rule = cut_rule
        self.trace = trace
        self.steps = 0
        self.memo = {}
        self.hid = 0
        self.deaths = {}
        self.death_samples = []
        self.nf_memo = {}

    def normalize(self, q):
        hit = self.nf_memo.get(q)
        if hit is None:
            hit = (normalize_fallback(q, self.head_budget),)
            self.nf_memo[q] = hit
        return hit[0]

    def prove(self, depth, g, asms, e, q, can_abstract=True):
        self.steps += 1
        if self.steps > 2_000_000: raise OutOfFuel()
        r = self.normalize(q)
        if r is None: return None
        s, blocked = r
        key = (s, tuple(sorted(map(repr, e))),
               tuple((a[0], tuple(sorted(map(repr, a[1]))), a[2]) for a in asms),
               can_abstract)
        hit = self.memo.get(key)
        if hit is not None:
            proof, d = hit
            if proof is not None: return proof
            if d >= depth: return None
        result = self._prove(depth, g, asms, e, s, blocked, can_abstract)
        self.memo[key] = (result, depth)
        return result

    def _prove(self, depth, g, asms, e, s, blocked, can_abstract):
        if self.trace:
            print('%s state %dn %s blocked=%s' % ('  ' * (self.depth - depth),
                  term_size(s), spec_str(e), blocked and name_str(blocked)))
        def tr(msg):
            if self.trace: print('%s -> %s' % ('  ' * (self.depth - depth), msg))
        # FOLD
        for i, a in enumerate(asms):
            f = fold(a, s, self.reduce_budget)
            if f is not None:
                core, star, sigma = f
                gstars = spec_stars(e)
                ok = (star is not None) == bool(gstars) and ms_minus(core, spec_core(e)) == []
                if ok:
                    tr('FOLD hyp%d' % i)
                    cross = None
                    if gstars and star[1] != gstars[0][1]:
                        cross = (star[1], gstars[0][1], sigma, a[3])
                    return P('FOLD', (i, a[2], cross))
                elif self.trace:
                    tr('fold hyp%d spec mismatch: %s vs %s' % (i, spec_str(core), spec_str(e)))
        # GENERALIZE
        gen = self.generalize(g, asms, e, s)
        if gen is not None:
            s2, e2, info = gen
            tr('GEN %s := #%d' % (name_str(info[0]), term_size(info[1])))
            sub = self.prove(depth, g + 1, asms, e2, s2)
            return P('GEN', info, [sub]) if sub else None
        # STAR: a goal owing only the tail closes anywhere, recording where it
        # ended; the enclosing CUT proves that end state against the cut-off spec.
        if len(e) == 1 and is_star(e[0]):
            return P('STAR', (e[0][1], s))
        # CUT: with the state demanding v and the spec owing more than v's
        # subtree, prove the v-phase against a fresh tail, then prove each state
        # the phase ends in against what was cut away.
        if self.cut_rule and depth > 0:
            cands = [blocked] if blocked is not None else []
            for a in e:
                if a != ONE and not is_star(a) and a[1] not in cands:
                    cands.append(a[1])
            # the machine demands its subjects in some order; leaf every other
            # spec variable and count emissions until it blocks on v -- the
            # subject being processed now blocks earliest
            others = [a[1] for a in e if a != ONE and not is_star(a)]
            def demand_rank(v):
                t = s
                for w in others:
                    if w != tuple(v): t = instantiate(w, LEAF, t)
                n = 0
                while n < 100:
                    r = self.normalize(t)
                    if r is None: return 1000
                    t, bl = r
                    if bl is not None:
                        return n if tuple(bl) == tuple(v) else 999
                    if t[0] == '^' and len(t[1]) == 1:
                        t = t[1][0]; n += 1
                    else:
                        return 998
                return 997
            cands = cands[:3]
            cands.sort(key=demand_rank)
            for v in cands:
                keep, cut = [], []
                for a in e:
                    if a == ONE or (not is_star(a) and
                                    (a[1] == tuple(v) or extends(tuple(v), a[1]))):
                        keep.append(a)
                    else:
                        cut.append(a)
                if not (cut and spec_core(cut) and spec_core(keep)):
                    continue
                self.hid += 1
                kname = (('k', self.hid),)
                star = Star(kname)
                tr('CUT keep=%s cut=%s' % (spec_str(keep), spec_str(cut)))
                phase = self.prove(depth, g + 1, asms, keep + [star], s)
                if phase is None:
                    tr('CUT phase failed')
                    continue
                obls, seen_es = [], set()
                for es in collect_ends(phase, tuple(kname)):
                    if es in seen_es: continue
                    seen_es.add(es)
                    tr('OBLIGATION %dn |= %s' % (term_size(es), spec_str(cut)))
                    sub = self.prove(depth, g + 1, asms, list(cut), es)
                    if sub is None: obls = None; break
                    obls.append(sub)
                if obls is not None:
                    return P('CUT', (tuple(kname), tuple(cut), spec_str(keep + [star]),
                                     spec_str(cut), list(asms)), [phase] + obls)
        # ABSTRACT
        if self.abstract_rule and can_abstract and asms:
            for s2, g2, subst in abstract_candidates(asms, e, s, g):
                tr('ABSTRACT %s -> state %dn' % ([(name_str(n), term_size(t)) for n, t in subst],
                                                 term_size(s2)))
                sub = self.prove(depth, g2, asms, e, s2, can_abstract=False)
                if sub is not None:
                    return P('ABSTRACT', subst, [sub])
        # read the state off
        def split(v):
            if depth == 0: return None
            self.hid += 1
            hyp = (s, list(e), tuple(v), self.hid)
            if Sz(v) in e:
                rest0, sh = ms_minus([Sz(v)], e), shapes_tree(v)
            elif Val(v) in e:
                rest0, sh = ms_minus([Val(v)], e), shapes_snat(v)
            else:
                return None
            tr('SPLIT %s' % name_str(tuple(v)))
            kids = []
            for shape, atoms, tag in sh:
                sub = self.prove(depth - 1, g, [hyp] + asms, atoms + rest0,
                                 instantiate(v, shape, s))
                if sub is None: return None
                kids.append((tag, sub))
            return P('SPLIT', (tuple(v), hyp[3]), [P('CASE', t, [k]) for t, k in kids])
        def split_someone():
            if blocked is not None:
                return split(blocked)
            if self.spec_split:
                for a in e:
                    if a != ONE and not is_star(a):
                        r = split(a[1])
                        if r is not None: return r
            return None
        def die(why):
            self.deaths[why] = self.deaths.get(why, 0) + 1
            if len(self.death_samples) < 400:
                self.death_samples.append((why, depth, term_size(s), spec_str(e),
                                           blocked and name_str(blocked)))
            return None
        if is_leaf(s):
            return P('LEAF') if e == [] else die('leaf-vs-nonempty-spec')
        if is_var(s):
            return P('VAR', s[0][1]) if ms_minus([Val(s[0][1])], e) == [] else die('var-vs-spec')
        h, args = s
        if h == '^' and len(args) == 1:               # successor
            e2 = ms_minus([ONE], e)
            if e2 is not None:
                tr('PEEL')
                sub = self.prove(depth, g, asms, e2, args[0])
                return P('PEEL', None, [sub]) if sub else None
            return split_someone() or die('succ-no-one' if depth else 'succ-depth0')
        # stuck application or fork value
        if h == '^' and len(args) == 2:
            return die('fork-value')                  # a fork is not an Snat
        return split_someone() or die(('stuck-nosplit' if blocked else 'app-noblock')
                                      if depth else 'stuck-depth0')

    def generalize(self, g, asms, e, s):
        for c in subterms(s):
            for a in asms:
                f = fold(a, c, self.reduce_budget)
                if f is None or f[1]: continue
                rest = ms_minus(f[0], e)
                if rest is None: continue
                name = (('g', g),)
                return replace(c, name, s), [Val(name)] + rest, (name, c)
        return None

def validate_cross(proof, prover):
    # A fold that bridged two tails borrowed its hypothesis's end states for a
    # different continuation. Sound iff those ends -- the ones of the
    # hypothesis's own split subtree, under the fold's substitution -- also
    # satisfy the borrowing cut's spec. Prove exactly that.
    cuts, borrows, subtrees = {}, [], {}
    def walk(p):
        if p is None: return
        if p.rule == 'CUT': cuts[p.info[0]] = p
        if p.rule == 'SPLIT': subtrees[p.info[1]] = p
        if p.rule == 'FOLD' and p.info[2] is not None: borrows.append(p.info[2])
        for k in p.kids: walk(k)
    walk(proof)
    done, frontier, rounds = set(), list(borrows), 0
    while frontier and rounds < 8:
        rounds += 1
        nxt = []
        for hyp_star, goal_star, sigma, hid in frontier:
            key = (hyp_star, goal_star, hid)
            if key in done: continue
            done.add(key)
            owner, tree = cuts.get(goal_star), subtrees.get(hid)
            if owner is None or tree is None: return False
            cutspec, oasms = list(owner.info[1]), owner.info[4]
            seen = set()
            for es in collect_ends(tree, hyp_star):
                for n, t in (sigma or {}).items():
                    es = instantiate(n, t, es)
                if es in seen: continue
                seen.add(es)
                sub = prover.prove(prover.depth, 900 + rounds * 50, oasms, cutspec, es)
                if sub is None: return False
                def walk2(p):
                    if p is None: return
                    if p.rule == 'FOLD' and p.info[2] is not None: nxt.append(p.info[2])
                    for k in p.kids: walk2(k)
                walk2(sub)
        frontier = nxt
    return not frontier

def spec_str(e):
    out = []
    for a in e:
        if a == ONE: out.append('1')
        elif a[0] == 'sz': out.append('|%s|' % name_str(a[1]))
        elif a[0] == 'star': out.append('*%s' % name_str(a[1]))
        else: out.append(name_str(a[1]))
    return '[' + ','.join(out) + ']'

def name_str(n):
    if len(n) == 1 and isinstance(n[0], tuple): return 'n%d' % n[0][1]
    return 't' + ''.join(str(i) for i in n[:-1][::-1])

INPUT = ('i',)

def computes_size(prog_tree, **kw):
    pv = Prover(**kw)
    q = app1(quote(prog_tree), V(INPUT))
    proof = pv.prove(pv.depth, 0, [], [Sz(INPUT)], q)
    if proof is not None and not validate_cross(proof, pv):
        return None
    return proof

# ---------- proof rendering ----------
def render(p, ind=0):
    pad = '  ' * ind
    if p is None: return pad + 'FAIL\n'
    if p.rule == 'SPLIT':
        out = pad + 'SPLIT %s\n' % name_str(p.info[0])
        for k in p.kids: out += render(k, ind + 1)
        return out
    if p.rule == 'CASE':
        return pad + '%s: ' % p.info + render(p.kids[0], ind).lstrip() \
            .replace('\n' + pad, '\n' + pad)
    if p.rule == 'PEEL':
        return pad + 'PEEL\n' + render(p.kids[0], ind)
    if p.rule == 'GEN':
        return pad + 'GEN %s := #%d\n' % (name_str(p.info[0]), term_size(p.info[1])) \
            + render(p.kids[0], ind)
    if p.rule == 'ABSTRACT':
        return pad + 'ABSTRACT %s\n' % ', '.join('%s := #%d' % (name_str(n), term_size(t))
                                                  for n, t in p.info) + render(p.kids[0], ind)
    if p.rule == 'CUT':
        out = pad + 'CUT phase %s then %s\n' % (p.info[2], p.info[3])
        for k in p.kids: out += render(k, ind + 1)
        return out
    if p.rule == 'STAR':
        return pad + 'END (state recorded)\n'
    if p.rule == 'FOLD':
        return pad + 'FOLD hyp%d on %s%s\n' % (p.info[0], name_str(p.info[1]),
                                                ' (borrowed tail)' if p.info[2] else '')
    if p.rule == 'LEAF': return pad + 'ZERO\n'
    if p.rule == 'VAR': return pad + 'VALUE %s\n' % name_str(p.info)
    return pad + p.rule + '\n'

# ---------- main ----------
POSITIVE = ['size', 'fastest', 'smallest', 'smallest2', 'smallest3', 'smallest4',
            'smallest5', 'smallest6', 'naive', 'swapped', 'shifted', 'accumulating']
NEGATIVE = ['leaves', 'left_spine', 'off_by_one', 'deep_bug', 'id', 'add', 'conv',
            'counts_forever']
LAZY = ['lazy100', 'lazy103', 'lazy104', 'lazy106', 'lazy108', 'lazy113']

if __name__ == '__main__':
    import time
    which = sys.argv[1:] if len(sys.argv) > 1 else POSITIVE + NEGATIVE + LAZY
    for name in which:
        t0 = time.time()
        tree = load_tree(name)
        try:
            proof = computes_size(tree)
            verdict = 'true' if proof else 'false'
        except OutOfFuel:
            verdict = 'false(step-cap)'
        print('%-14s %-6s %5.1fs' % (name, verdict, time.time() - t0))
