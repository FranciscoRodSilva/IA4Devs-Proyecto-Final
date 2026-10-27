/** Ruta pública del inicio de sesión. Vive aparte de rutas.tsx para que el armazón la importe sin un ciclo con las rutas. */
export const RUTA_INICIO_SESION = "/inicio-sesion";

/** Valor de `state.aviso` con el que el cierre por sesión terminada lleva a la pantalla de inicio (CA-5 esc. 1). */
export const AVISO_SESION_TERMINADA = "SESION_TERMINADA";
