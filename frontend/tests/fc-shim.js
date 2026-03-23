/**
 * Minimal fast-check shim for browser-based property tests.
 * Implements the subset of the fc API used by the AEGIS dashboard tests.
 * No CDN or build system required.
 */
(function (global) {
  'use strict';

  // ── Arbitrary helpers ──────────────────────────────────────────────────────

  function makeArb(gen) {
    return { _gen: gen };
  }

  function sample(arb, rng) {
    return arb._gen(rng);
  }

  // Simple splitmix32 PRNG
  function makePRNG(seed) {
    let s = seed >>> 0;
    return function () {
      s = (s + 0x9e3779b9) >>> 0;
      let z = s;
      z = Math.imul(z ^ (z >>> 16), 0x85ebca6b) >>> 0;
      z = Math.imul(z ^ (z >>> 13), 0xc2b2ae35) >>> 0;
      return (z ^ (z >>> 16)) >>> 0;
    };
  }

  function randFloat(rng) { return (rng() >>> 0) / 0x100000000; }

  // ── Arbitraries ────────────────────────────────────────────────────────────

  const fc = {};

  fc.float = function ({ min = 0, max = 1, noNaN = true } = {}) {
    return makeArb(function (rng) {
      return min + randFloat(rng) * (max - min);
    });
  };

  fc.integer = function ({ min = 0, max = 100 } = {}) {
    return makeArb(function (rng) {
      return min + (rng() % (max - min + 1));
    });
  };

  fc.boolean = function () {
    return makeArb(function (rng) { return (rng() & 1) === 1; });
  };

  fc.constant = function (v) {
    return makeArb(function () { return v; });
  };

  fc.constantFrom = function (...values) {
    return makeArb(function (rng) {
      return values[rng() % values.length];
    });
  };

  fc.string = function ({ minLength = 0, maxLength = 10 } = {}) {
    const chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_';
    return makeArb(function (rng) {
      const len = minLength + (rng() % (maxLength - minLength + 1));
      let s = '';
      for (let i = 0; i < len; i++) s += chars[rng() % chars.length];
      return s;
    });
  };

  fc.array = function (arb, { minLength = 0, maxLength = 10 } = {}) {
    return makeArb(function (rng) {
      const len = minLength + (rng() % (maxLength - minLength + 1));
      const arr = [];
      for (let i = 0; i < len; i++) arr.push(sample(arb, rng));
      return arr;
    });
  };

  fc.set = function (arb, { minLength = 0, maxLength = 10 } = {}) {
    return makeArb(function (rng) {
      const seen = new Set();
      const arr = [];
      let attempts = 0;
      while (arr.length < maxLength && attempts < maxLength * 10) {
        const v = sample(arb, rng);
        if (!seen.has(v)) { seen.add(v); arr.push(v); }
        attempts++;
      }
      return arr.slice(0, Math.max(minLength, arr.length));
    });
  };

  fc.record = function (shape) {
    return makeArb(function (rng) {
      const obj = {};
      for (const [k, arb] of Object.entries(shape)) obj[k] = sample(arb, rng);
      return obj;
    });
  };

  fc.oneof = function (...arbs) {
    return makeArb(function (rng) {
      return sample(arbs[rng() % arbs.length], rng);
    });
  };

  // Adds a .map() method to arbitraries
  const origMakeArb = makeArb;
  function makeArbWithMap(gen) {
    const arb = { _gen: gen };
    arb.map = function (fn) {
      return makeArbWithMap(function (rng) { return fn(arb._gen(rng)); });
    };
    return arb;
  }

  // Patch all arbitraries to support .map()
  ['float','integer','boolean','constant','constantFrom','string','array','set','record','oneof'].forEach(function (name) {
    const orig = fc[name];
    fc[name] = function () {
      const arb = orig.apply(fc, arguments);
      arb.map = function (fn) {
        return makeArbWithMap(function (rng) { return fn(arb._gen(rng)); });
      };
      return arb;
    };
  });

  // ── Property & Assert ──────────────────────────────────────────────────────

  fc.property = function (...args) {
    const predicate = args[args.length - 1];
    const arbs = args.slice(0, -1);
    return { _arbs: arbs, _predicate: predicate };
  };

  fc.assert = function (prop, { numRuns = 100, seed } = {}) {
    const rng = makePRNG(seed !== undefined ? seed : (Date.now() & 0xffffffff));
    for (let i = 0; i < numRuns; i++) {
      const inputs = prop._arbs.map(function (arb) { return sample(arb, rng); });
      let result;
      try {
        result = prop._predicate.apply(null, inputs);
      } catch (e) {
        throw new Error('Property threw on run ' + (i + 1) + ':\n' + e + '\nInputs: ' + JSON.stringify(inputs));
      }
      if (result === false) {
        throw new Error('Property falsified on run ' + (i + 1) + '\nCounterexample: ' + JSON.stringify(inputs));
      }
    }
  };

  global.fc = fc;
})(window);
