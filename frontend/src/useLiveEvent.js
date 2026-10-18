import { useEffect, useState } from "react";
import { createLiveBridge } from "./liveBridge";

const live = createLiveBridge();

/** Reactive view of the shared live-update stream. */
export function useLiveEvent() {
  const [ts, setTs] = useState(live.lastEvent);
  useEffect(() => live.subscribe(setTs), []);
  return ts;
}

export function bumpLive() {
  live.bump();
}
