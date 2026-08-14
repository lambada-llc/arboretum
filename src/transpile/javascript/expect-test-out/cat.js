arg => {
  const program = [[],[[[]]]];
  // Read input string and turn it into a tree
  const ofB = b => b ? [[]] : [];
  const ofL = l => { let f = []; for (let i = l.length; i; i--) f = [f, l[i - 1]]; return f };
  const ofN = n => { let l = []; for (; n; n >>= 1) l.push(ofB(n % 2)); return ofL(l) };
  const ofS = s => ofL(Array.from(s, c => ofN(c.codePointAt(0))));
  const input = ofS(arg);
  // Apply program to input and execute
  const result = [input, ...program];
  const todo = [result];
  while (todo.length) {
    const f = todo.pop();
    if (f.length < 3) continue;
    todo.push(f);
    const a = f.pop(), b = f.pop(), c = f.pop();
    if (a.length === 0) f.push(...b);
    else if (a.length === 1) {
      const newPotRedex = [c, ...b];
      f.push(newPotRedex, c, ...a[0]);
      todo.push(newPotRedex);
    }
    else if (a.length === 2)
      if (c.length === 0) f.push(...a[1]);
      else if (c.length === 1) f.push(c[0], ...a[0]);
      else if (c.length === 2) f.push(c[0], c[1], ...b);
  }
  // Turn result into string and print
  const toB = f => !!f?.length;
  const toL = f => { let l = []; while (f?.length) { l.push(f[1]); f = f[0]; } return l };
  const toN = f => toL(f).reduceRight((acc, b) => 2 * acc + (toB(b) ? 1 : 0), 0);
  const toS = f => toL(f).map(toN).map(x => String.fromCodePoint(x)).join('');
  return toS(result); }