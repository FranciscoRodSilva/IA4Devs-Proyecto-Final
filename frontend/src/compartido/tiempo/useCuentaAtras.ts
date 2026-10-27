import { useEffect, useState } from "react";

/** Segundos que quedan de una espera. Toma `segundos` al montar y fija el instante de fin con `Date.now()`;
 *  cada segundo recalcula contra el reloj, así que un temporizador atrasado no alarga la espera. Una espera
 *  nueva se monta de nuevo con otra `key`, así que una segunda de igual duración también cuenta. Devuelve 0
 *  cuando no hay espera o ya venció. */
export function useCuentaAtras(segundos: number | null): number {
  const [fin] = useState(() => Date.now() + (segundos ?? 0) * 1_000);
  const [restantes, setRestantes] = useState(segundos ?? 0);
  const activa = restantes > 0;

  useEffect(() => {
    if (!activa) return;
    const id = setInterval(() => {
      setRestantes(Math.max(Math.ceil((fin - Date.now()) / 1_000), 0));
    }, 1_000);
    return () => clearInterval(id);
  }, [activa, fin]);

  return restantes;
}

/** Segundos → «mm:ss», con los dos campos rellenados a dos cifras. */
export function formatearCuentaAtras(segundos: number): string {
  const minutos = Math.floor(segundos / 60);
  const resto = segundos % 60;
  return `${String(minutos).padStart(2, "0")}:${String(resto).padStart(2, "0")}`;
}
