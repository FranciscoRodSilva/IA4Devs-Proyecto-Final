import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import { crearAplicacion } from "@/app/crear-aplicacion";

/** Monta la aplicación completa en `rutaInicial` con un enrutador de memoria. Exige `vi.useFakeTimers({ shouldAdvanceTime: true })`
 *  en la prueba: `usuario` avanza el reloj simulado en cada pausa, y ninguna prueba espera con `sleep`. */
export function renderizarAplicacion(rutaInicial: string) {
  const aplicacion = crearAplicacion({ rutaInicial });
  const vista = render(aplicacion.elemento);
  const usuario = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
  return { ...aplicacion, ...vista, usuario };
}
