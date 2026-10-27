import { useEffect, useState } from "react";
import { getRetentionDays } from "../lib/api";

let cached = null;

/** How many days a finished run keeps its content (null while unknown, 0: until purged). */
export function useRetentionDays() {
  const [days, setDays] = useState(cached);
  useEffect(() => {
    if (cached !== null) return undefined;
    let active = true;
    getRetentionDays()
      .then((d) => {
        cached = d;
        if (active) setDays(d);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);
  return days;
}
