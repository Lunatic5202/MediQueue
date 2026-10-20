import "@testing-library/jest-dom/vitest";
import { afterEach, beforeEach } from "vitest";
import { cleanup } from "@testing-library/react";

beforeEach(() => {
  if (typeof localStorage !== "undefined") {
    localStorage.clear();
  } else {
    Object.defineProperty(window, "localStorage", {
      value: {
        _d: new Map(),
        getItem(k) { return this._d.get(k) ?? null; },
        setItem(k, v) { this._d.set(k, String(v)); },
        removeItem(k) { this._d.delete(k); },
        clear() { this._d.clear(); },
      },
      configurable: true,
      writable: true,
    });
  }
});

afterEach(() => cleanup());

