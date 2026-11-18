import { z } from "zod";
import type { components } from "@/api/generado/servidor";
import { aDecimal, enteroNoNegativo } from "@/compartido/dinero/dinero";
import type { CampoCatalogo } from "@/compartido/formularios/FormularioCatalogo";

// TKT-032a · F4. Los esquemas validan el formulario, no espejan el modelo: los nombres de campo son los del API para
// que un 422 caiga en su campo, y lo que se rechaza aquí es cortesía (CA-4); el servidor manda. El tope de consignación
// es dinero: entra y sale como cadena y se compara con decimal.js, nunca como número (CA-R4).

type Esquemas = components["schemas"];
type Proveedor = Esquemas["Proveedor"];
type ProveedorCambios = Esquemas["ProveedorCambios"];

/** Lo que teclea la persona en el alta: todo texto; los días son «1» a «7» y el tope, vacío o decimal plano. */
export interface EntradaAlta {
  nombre: string;
  rfc: string;
  tope_consignacion: string;
  dia_corte: string;
  dia_pago: string;
}

/** Lo que teclea la persona en la edición: lo del alta, con el RFC que solo se lee. */
export type EntradaEdicion = EntradaAlta;

/** Lo que entrega el formulario de edición al guardar: el RFC, si llega, no viaja. */
export interface SalidaEdicion {
  nombre: string;
  rfc?: string;
  tope_consignacion: string | null;
  dia_corte: number;
  dia_pago: number;
}

const MENSAJE_NOMBRE = "Escribe el nombre del proveedor.";
const MENSAJE_NOMBRE_LARGO = "El nombre admite hasta 200 caracteres.";
const MENSAJE_NOMBRE_CONTROL = "El nombre no admite caracteres de control.";
const MENSAJE_RFC = "Escribe el RFC con su forma, como XAXX010101000.";
const MENSAJE_TOPE = "Escribe el tope como un número, como 300000.00, o déjalo vacío.";
const MENSAJE_DIA = "Elige un día de la semana.";

const PATRON_RFC = /^[A-ZÑ&]{3,4}[0-9]{6}[A-Z0-9]{3}$/;
const PATRON_TOPE = /^[0-9]{1,14}(\.[0-9]{1,4})?$/;

/** `1` lunes … `7` domingo, en minúsculas. `valor` es lo que se envía; `etiqueta`, lo que se ve. */
export const DIAS: ReadonlyArray<{ valor: string; etiqueta: string }> = [
  { valor: "1", etiqueta: "lunes" },
  { valor: "2", etiqueta: "martes" },
  { valor: "3", etiqueta: "miércoles" },
  { valor: "4", etiqueta: "jueves" },
  { valor: "5", etiqueta: "viernes" },
  { valor: "6", etiqueta: "sábado" },
  { valor: "7", etiqueta: "domingo" },
];

/** RN-17: el alta propone jueves para el corte y sábado para el pago, y ningún tope. */
export const VALORES_INICIALES_ALTA: EntradaAlta = {
  nombre: "",
  rfc: "",
  tope_consignacion: "",
  dia_corte: "4",
  dia_pago: "6",
};

const nombre = z
  .string()
  .trim()
  .min(1, MENSAJE_NOMBRE)
  .max(200, MENSAJE_NOMBRE_LARGO)
  .refine((texto) => !texto.includes("\u0000"), MENSAJE_NOMBRE_CONTROL);

/** Se recorta y se pasa a mayúsculas antes de comprobar la forma: `xaxx010101000` se envía `XAXX010101000`. */
const rfc = z.string().trim().toUpperCase().regex(PATRON_RFC, MENSAJE_RFC);

/** Vacío significa «sin tope» y sale como null. Lo demás sale tal cual, como cadena decimal. */
const topeConsignacion = z.string().transform((texto, ctx) => {
  const limpio = texto.trim();
  if (limpio === "") return null;
  if (PATRON_TOPE.test(limpio)) return limpio;
  ctx.addIssue({ code: "custom", message: MENSAJE_TOPE, input: texto });
  return z.NEVER;
});

/** El desplegable entrega «1» a «7»; se convierte con la única puerta de cadena a entero del cliente. */
const diaDeLaSemana = z.string().transform((texto, ctx) => {
  const entero = enteroNoNegativo(texto);
  if (entero !== null && entero >= 1 && entero <= 7) return entero;
  ctx.addIssue({ code: "custom", message: MENSAJE_DIA, input: texto });
  return z.NEVER;
});

const camposComunes = {
  nombre,
  tope_consignacion: topeConsignacion,
  dia_corte: diaDeLaSemana,
  dia_pago: diaDeLaSemana,
};

/** El alta: lo de la edición más el RFC, que se escribe por primera y única vez. */
export const esquemaAlta = z.object({ ...camposComunes, rfc });

export type CampoProveedor = CampoCatalogo<keyof z.input<typeof esquemaAlta> & string>;

/** Los campos del alta, en su orden; el primero (el nombre, de texto) recibe el foco al abrirse (CA-2). */
export const camposAlta: ReadonlyArray<CampoProveedor> = [
  { nombre: "nombre", etiqueta: "Nombre" },
  { nombre: "rfc", etiqueta: "RFC" },
  { nombre: "tope_consignacion", etiqueta: "Tope de consignación (opcional)" },
  { nombre: "dia_corte", etiqueta: "Día de corte", tipo: "desplegable", opciones: DIAS },
  { nombre: "dia_pago", etiqueta: "Día de pago", tipo: "desplegable", opciones: DIAS },
];

/** La edición: el RFC no es editable y no se valida ni viaja. */
export const esquemaEdicion = z.object(camposComunes);

/** Los valores con que arranca la edición: el tope vacío si no lo hay, y los días como texto del desplegable. */
export function valoresInicialesDe(proveedor: Proveedor): EntradaEdicion {
  return {
    nombre: proveedor.nombre,
    rfc: proveedor.rfc,
    tope_consignacion: proveedor.tope_consignacion ?? "",
    dia_corte: `${proveedor.dia_corte}`,
    dia_pago: `${proveedor.dia_pago}`,
  };
}

/**
 * ¿Cambió el tope? Se compara con Decimal.eq: «300000.0000» y «300000» son el mismo importe. Si alguna cadena no es
 * decimal plano (no debería llegar aquí), se compara como texto para no dar por igual lo que no se pudo leer.
 */
function topeCambio(guardado: string | null, capturado: string | null): boolean {
  if (guardado === null) return capturado !== null;
  if (capturado === null) return true;
  const antes = aDecimal(guardado);
  const despues = aDecimal(capturado);
  if (antes === null || despues === null) return guardado !== capturado;
  return !antes.eq(despues);
}

/**
 * El cuerpo del PATCH: solo lo que cambió, y nada si no cambió nada (null: no hay petición que enviar). Así la
 * bitácora asienta lo que de verdad se modificó y no sale un ACTUALIZAR vacío.
 */
export function cambiosDe(proveedor: Proveedor, valores: SalidaEdicion): ProveedorCambios | null {
  const cambios: ProveedorCambios = {};
  if (valores.nombre !== proveedor.nombre) cambios.nombre = valores.nombre;
  if (topeCambio(proveedor.tope_consignacion ?? null, valores.tope_consignacion)) {
    cambios.tope_consignacion = valores.tope_consignacion;
  }
  if (valores.dia_corte !== proveedor.dia_corte) cambios.dia_corte = valores.dia_corte;
  if (valores.dia_pago !== proveedor.dia_pago) cambios.dia_pago = valores.dia_pago;
  return Object.keys(cambios).length === 0 ? null : cambios;
}
