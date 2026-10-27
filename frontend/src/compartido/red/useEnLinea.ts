import { useSyncExternalStore } from "react";

function suscribir(alCambiar: () => void): () => void {
  globalThis.addEventListener("online", alCambiar);
  globalThis.addEventListener("offline", alCambiar);
  return () => {
    globalThis.removeEventListener("online", alCambiar);
    globalThis.removeEventListener("offline", alCambiar);
  };
}

/** Regla 10 de CLAUDE.md. Detecta la falta de red en el cliente para no enviar nada; no evalúa ninguna regla. */
export function useEnLinea(): boolean {
  return useSyncExternalStore(
    suscribir,
    () => globalThis.navigator.onLine,
    () => true,
  );
}
