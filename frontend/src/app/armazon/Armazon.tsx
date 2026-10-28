import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router";
import { FalloApi, pedir } from "@/api/cliente";
import { useApi } from "@/api/ProveedorApi";
import { type UsuarioActual, useSesion } from "@/api/sesion";
import logo from "@/assets/ap-logo.jpeg";
import { type Seccion, NOMBRE_ROL, seccionesDe } from "@/app/navegacion/secciones";
import { RUTA_INICIO_SESION } from "@/app/navegacion/ruta-inicio-sesion";

const GRUPOS: readonly Seccion["grupo"][] = ["Obra", "Compras", "Almacén", "Dirección"];
const formatoHora = new Intl.DateTimeFormat("es-MX", { hour: "2-digit", minute: "2-digit" });

/** CA-7 esc. 4 · la sesión vence con el primero de los dos plazos: el menor de los dos, comparado con Date.parse. */
function vencimientoMasTemprano(sesion: UsuarioActual["sesion"]): string {
  return Date.parse(sesion.expira_por_inactividad_en) < Date.parse(sesion.expira_en)
    ? sesion.expira_por_inactividad_en
    : sesion.expira_en;
}

function Cargando() {
  return (
    <div role="status" aria-busy="true" aria-label="Cargando la sesión" className="space-y-3 p-6">
      <div className="h-4 w-48 animate-pulse rounded bg-muted" />
      <div className="h-4 w-80 animate-pulse rounded bg-muted" />
    </div>
  );
}

/** M10 · sin la sesión, el armazón no pinta secciones. El error SESION lo resuelve el middleware y no se pinta aquí. */
function ErrorSesion({ sinConexion, alReintentar }: { sinConexion: boolean; alReintentar: () => void }) {
  return (
    <div role="alert" className="space-y-3 p-6">
      <p>No se pudo cargar la sesión.</p>
      {sinConexion && <p>Sin conexión con el servidor.</p>}
      <button type="button" onClick={alReintentar} className="rounded border px-3 py-1">
        Reintentar
      </button>
    </div>
  );
}

export function Armazon() {
  const api = useApi();
  const queryClient = useQueryClient();
  const navegar = useNavigate();
  const sesion = useSesion();
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [errorSalida, setErrorSalida] = useState(false);
  const botonMenu = useRef<HTMLButtonElement>(null);

  // C106 · Escape pliega el menú y devuelve el foco al botón «Menú».
  useEffect(() => {
    if (!menuAbierto) return;
    function alTeclear(evento: KeyboardEvent) {
      if (evento.key !== "Escape") return;
      setMenuAbierto(false);
      botonMenu.current?.focus();
    }
    document.addEventListener("keydown", alTeclear);
    return () => document.removeEventListener("keydown", alTeclear);
  }, [menuAbierto]);

  async function salir() {
    const resultado = await pedir(() => api.POST("/api/v1/sesion/cierre"));
    // Un cierre aceptado o una sesión que ya no existía terminan igual, sin aviso (CA-5 esc. 2 y CA-7 esc. 7).
    if (resultado.ok || resultado.error.tipo === "SESION") {
      await navegar(RUTA_INICIO_SESION, { replace: true });
      queryClient.clear();
      return;
    }
    setErrorSalida(true);
  }

  if (sesion.data === undefined) {
    if (!sesion.isError) return <Cargando />;
    const tipo = sesion.error instanceof FalloApi ? sesion.error.error.tipo : "GENERICO";
    if (tipo === "SESION") return null;
    return <ErrorSesion sinConexion={tipo === "RED"} alReintentar={() => void sesion.refetch()} />;
  }

  const usuario = sesion.data;
  const vence = vencimientoMasTemprano(usuario.sesion);
  const grupos = GRUPOS.map((grupo) => ({ grupo, secciones: seccionesDe(usuario.roles).filter((s) => s.grupo === grupo) }))
    .filter((entrada) => entrada.secciones.length > 0);

  return (
    <div className="min-h-screen">
      <header className="flex flex-wrap items-center gap-4 border-b bg-card p-4">
        <button
          ref={botonMenu}
          type="button"
          aria-label="Menú"
          aria-controls="menu-secciones"
          aria-expanded={menuAbierto ? "true" : "false"}
          onClick={() => setMenuAbierto((abierto) => !abierto)}
          className="rounded border px-3 py-1 md:hidden"
        >
          ≡
        </button>
        <img src={logo} alt="AP Buildings" className="h-8 w-auto" />
        <p className="font-semibold text-primary">CIMENTA</p>
        <p>{usuario.nombre}</p>
        <p>{usuario.roles.map((rol) => NOMBRE_ROL[rol]).join(" · ")}</p>
        <p>
          Sesión vigente hasta <time dateTime={vence}>{formatoHora.format(new Date(vence))}</time>
        </p>
        <button type="button" onClick={() => void salir()} className="ml-auto rounded border px-3 py-1">
          Salir
        </button>
        {errorSalida && <p role="alert">No se pudo cerrar la sesión. Inténtalo de nuevo.</p>}
      </header>
      <div className="md:grid md:grid-cols-[16rem_1fr]">
        <nav
          id="menu-secciones"
          aria-label="Secciones"
          data-abierto={menuAbierto ? "true" : "false"}
          className={menuAbierto ? "block border-r bg-sidebar p-4" : "hidden border-r bg-sidebar p-4 md:block"}
        >
          {grupos.map(({ grupo, secciones }) => (
            <div key={grupo} className="mb-4">
              <h2 className="mb-1 text-xs font-semibold uppercase">{grupo}</h2>
              <ul>
                {secciones.map((s) => (
                  <li key={s.clave}>
                    <NavLink to={s.ruta} onClick={() => setMenuAbierto(false)} className={({ isActive }) =>
                        isActive
                          ? "block rounded px-2 py-1 bg-sidebar-accent font-medium text-sidebar-primary"
                          : "block rounded px-2 py-1 text-sidebar-foreground hover:bg-sidebar-accent/60"
                      }
                    >
                      {s.titulo}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </nav>
        <main className="min-w-0">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
