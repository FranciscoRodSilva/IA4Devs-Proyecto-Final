import type { components as Provisional } from "@/api/generado/contrato-error.provisional";
import type { components as Servidor } from "@/api/generado/servidor";
import type { Rol, UsuarioActual } from "@/api/sesion";

// Fábricas de cuerpos de respuesta con nombre del dominio. Cada una cumple por compilación el esquema generado
// (`satisfies`): si el contrato cambia, `npm run typecheck` lo dice. Los identificadores son constantes fijas.
type Errores = Provisional["schemas"];
type Esquemas = Servidor["schemas"];

const CORRELACION_ID = "7b1e4c2a-5d3f-4a8b-9c6e-1f2a3b4c5d6e";
const ID_USUARIO = "0b6f1c3e-2d4a-4e5f-8a7b-9c0d1e2f3a4b";

export function usuarioActual(roles: Rol[], cambios: Partial<UsuarioActual> = {}): UsuarioActual {
  return {
    id: ID_USUARIO,
    nombre: "Rosa Villanueva",
    email: "rosa@cimenta.test",
    roles,
    sesion: { expira_en: "2026-10-27T02:00:00Z", expira_por_inactividad_en: "2026-10-26T22:00:00Z" },
    ...cambios,
  } satisfies Esquemas["UsuarioActual"];
}

export function tokenCsrf(token = "token-de-prueba"): Esquemas["TokenCsrf"] {
  return { token } satisfies Esquemas["TokenCsrf"];
}

export function errorSesion(motivo: Errores["ErrorSesion"]["motivo"]): Errores["ErrorSesion"] {
  return {
    tipo: "SESION",
    motivo,
    mensaje: "La sesión no es válida.",
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorSesion"];
}

export function errorLimiteIntentos(reintentar_en_s: number): Errores["ErrorLimiteIntentos"] {
  return {
    tipo: "LIMITE_INTENTOS",
    mensaje: "Demasiados intentos.",
    reintentar_en_s,
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorLimiteIntentos"];
}

export function errorValidacion(errores: Errores["ErrorValidacion"]["errores"]): Errores["ErrorValidacion"] {
  return {
    tipo: "VALIDACION",
    mensaje: "La petición no es válida.",
    errores,
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorValidacion"];
}

export function errorPermiso(motivo: Errores["ErrorPermiso"]["motivo"]): Errores["ErrorPermiso"] {
  return {
    tipo: "PERMISO",
    motivo,
    mensaje: "No tienes permiso para esta operación.",
    roles_requeridos: ["DIRECTOR_PROYECTOS", "DIRECCION_GENERAL"],
    correlacion_id: CORRELACION_ID,
  } satisfies Errores["ErrorPermiso"];
}
