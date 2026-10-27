import { createContext, useContext, useEffect, useRef } from "react";

const UnsavedWorkContext = createContext(null);

/** Lets the header ask the current page whether leaving it would lose work. */
export function UnsavedWorkProvider({ children }) {
  const dirty = useRef(false);
  return <UnsavedWorkContext.Provider value={dirty}>{children}</UnsavedWorkContext.Provider>;
}

/** A page with something in progress (a form being filled, a run starting) says so here. */
export function useUnsavedWork(isDirty) {
  const dirty = useContext(UnsavedWorkContext);
  useEffect(() => {
    if (!dirty) return undefined;
    dirty.current = !!isDirty;
    return () => {
      dirty.current = false;
    };
  }, [dirty, isDirty]);
}

export function useHasUnsavedWork() {
  const dirty = useContext(UnsavedWorkContext);
  return () => !!dirty?.current;
}
