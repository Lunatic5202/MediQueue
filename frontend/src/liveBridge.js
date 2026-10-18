/**
 * Tiny module-level bridge so the live-updates hook (mounted once in the shell)
 * can notify route-level pages without prop drilling through the router.
 */
let lastEvent = 0;
const listeners = new Set();

export function createLiveBridge() {
  return {
    get lastEvent() {
      return lastEvent;
    },
    bump() {
      lastEvent = Date.now();
      listeners.forEach((fn) => fn(lastEvent));
    },
    subscribe(fn) {
      listeners.add(fn);
      return () => listeners.delete(fn);
    },
  };
}

export function publishLiveEvent(ts = Date.now()) {
  lastEvent = ts;
  listeners.forEach((fn) => fn(lastEvent));
}
