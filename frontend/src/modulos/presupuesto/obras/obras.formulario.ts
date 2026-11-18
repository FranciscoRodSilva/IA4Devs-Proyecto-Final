import { z } from "zod";
import type { components } from "@/api/generado/servidor";
import type { CampoCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { fraccionAPorcentaje, porcentajeAFraccion } from "@/compartido/dinero/dinero";

type ObraNueva = components["schemas"]["ObraNueva"];
type ObraCambios = components["schemas"]["ObraCambios"];

/** El único tipo de contrato que existe en CIMENTA: se preselecciona y no admite otro valor. */
const TIPO_CONTRATO: ObraNueva["tipo_contrato"] = "PRECIO_ALZADO_MAXIMO_GARANTIZADO";

const MENSAJE_PORCENTAJE = "Escribe un porcentaje, como 15";

/** De texto a fracción exacta; lo que no es un porcentaje se rechaza en el campo con MENSAJE_PORCENTAJE. */
function convertirPorcentaje(texto: string, ctx: z.core.$RefinementCtx): string {
  const fraccion = porcentajeAFraccion(texto);
  if (fraccion !== null) return fraccion;
  ctx.addIssue({ code: "custom", message: MENSAJE_PORCENTAJE, input: texto });
  return z.NEVER;
}

/** Un porcentaje obligatorio. El rango (0 a 100) lo valida el servidor (CA-11 esc. 1). */
const porcentaje = z.string().transform((texto, ctx) => convertirPorcentaje(texto, ctx));

/** El umbral: vacío significa «sin umbral» y se envía null. */
const porcentajeOpcional = z.string().transform((texto, ctx) => {
  if (texto.trim() === "") return null;
  return convertirPorcentaje(texto, ctx);
});

/** Forma del formulario de alta. Los nombres de campo son los del API para que un 422 caiga en su campo. */
export const esquemaObra = z.object({
  codigo: z.string().trim().min(1, "Escribe el código de la obra."),
  nombre: z.string().trim().min(1, "Escribe el nombre de la obra."),
  domicilio: z.string().trim().min(1, "Escribe el domicilio de la obra."),
  tipo_contrato: z.literal(TIPO_CONTRATO),
  retencion_destajo_pct: porcentaje,
  fondo_garantia_pct: porcentaje,
  umbral_alerta_pct: porcentajeOpcional,
  iva_acreditable: z.boolean(),
});

export type CampoObra = CampoCatalogo<keyof z.input<typeof esquemaObra> & string>;

/** Los valores que propone el formulario: 15 % de retención y 5 % de fondo; el umbral vacío y el IVA sin marcar. */
export const VALORES_INICIALES_OBRA: z.input<typeof esquemaObra> = {
  codigo: "",
  nombre: "",
  domicilio: "",
  tipo_contrato: TIPO_CONTRATO,
  retencion_destajo_pct: "15",
  fondo_garantia_pct: "5",
  umbral_alerta_pct: "",
  iva_acreditable: false,
};

/** El orden de los campos es el del formulario; el primero recibe el foco al abrirse. */
export const CAMPOS_OBRA: ReadonlyArray<CampoObra> = [
  { nombre: "codigo", etiqueta: "Código" },
  { nombre: "nombre", etiqueta: "Nombre" },
  { nombre: "domicilio", etiqueta: "Domicilio" },
  {
    nombre: "tipo_contrato",
    etiqueta: "Tipo de contrato",
    tipo: "desplegable",
    opciones: [{ valor: TIPO_CONTRATO, etiqueta: "Precio alzado máximo garantizado" }],
  },
  { nombre: "retencion_destajo_pct", etiqueta: "Retención de destajo (%)" },
  { nombre: "fondo_garantia_pct", etiqueta: "Fondo de garantía (%)" },
  { nombre: "umbral_alerta_pct", etiqueta: "Umbral de alerta (%)" },
  { nombre: "iva_acreditable", etiqueta: "IVA acreditable", tipo: "casilla" },
];

/**
 * Forma del formulario de edición (TKT-012b CA-15): exactamente los seis campos editables. No declara `codigo`,
 * `tipo_contrato` ni `estado`: el código y el tipo no se cambian, y el estado solo cambia con sus transiciones (CA-2).
 * No es `.strict()`: lo que llegue con otros nombres se descarta en la salida, y nunca viaja.
 * El umbral es opcional de forma: ausente deja la clave fuera de la salida (no tocar el umbral); vacío es null (borrarlo).
 */
export const esquemaEdicionObra = z.object({
  nombre: z.string().trim().min(1, "Escribe el nombre de la obra."),
  domicilio: z.string().trim().min(1, "Escribe el domicilio de la obra."),
  retencion_destajo_pct: porcentaje,
  fondo_garantia_pct: porcentaje,
  umbral_alerta_pct: porcentajeOpcional.optional(),
  iva_acreditable: z.boolean(),
});

/**
 * Lo mismo que `esquemaEdicionObra`, con `codigo` y `tipo_contrato` declarados solo para que `FormularioCatalogo`
 * pueda mostrarlos como campos `soloLectura`. Esos dos campos nunca viajan: `FormularioCatalogo` los quita de la
 * salida antes de enviar, y el esquema de edición (el que valida) no los conoce.
 */
export const esquemaVistaEdicionObra = esquemaEdicionObra.extend({
  codigo: z.string().optional(),
  tipo_contrato: z.string().optional(),
});

/** Los campos editables, en el orden del formulario de alta (CA-15). El IVA es casilla; el resto, texto. */
const NOMBRES_EDITABLES = Object.keys(esquemaEdicionObra.shape);

/** Los campos editables con las etiquetas del alta: se toman de `CAMPOS_OBRA` para que no diverjan. */
export const CAMPOS_EDICION_OBRA: ReadonlyArray<CampoCatalogo<string>> = CAMPOS_OBRA.filter((campo) =>
  NOMBRES_EDITABLES.includes(campo.nombre),
);

type NombreCampoVistaEdicion = keyof z.input<typeof esquemaVistaEdicionObra> & string;

/**
 * Los campos que muestra el formulario de edición (CA-15): los ocho del alta, en su orden, con el código y el tipo de
 * contrato como `soloLectura`. Va aparte de `CAMPOS_EDICION_OBRA` porque esa lista es solo lo editable (TC-68).
 */
export const CAMPOS_VISTA_EDICION_OBRA: ReadonlyArray<CampoCatalogo<NombreCampoVistaEdicion>> = CAMPOS_OBRA.map((campo) =>
  campo.nombre === "codigo" || campo.nombre === "tipo_contrato" ? { ...campo, soloLectura: true } : campo,
);

/**
 * Los valores con que arranca el formulario de edición: los de la obra, con los porcentajes como se teclean.
 * Lo que el servidor manda es fracción de seis decimales (invariante de la forma); si una fracción no se pudiera
 * convertir, el campo sale vacío y el esquema lo rechaza en su campo, en vez de inventar un valor.
 */
export function valoresDeEdicion(obra: components["schemas"]["Obra"]): z.input<typeof esquemaEdicionObra> {
  return {
    nombre: obra.nombre,
    domicilio: obra.domicilio,
    retencion_destajo_pct: fraccionAPorcentaje(obra.retencion_destajo_pct) ?? "",
    fondo_garantia_pct: fraccionAPorcentaje(obra.fondo_garantia_pct) ?? "",
    umbral_alerta_pct: obra.umbral_alerta_pct === null ? "" : (fraccionAPorcentaje(obra.umbral_alerta_pct) ?? ""),
    iva_acreditable: obra.iva_acreditable,
  };
}

/** Lo que muestra la vista de edición: lo de `valoresDeEdicion` más el código y el tipo, que solo se leen. */
export function valoresDeVistaEdicion(obra: components["schemas"]["Obra"]): z.input<typeof esquemaVistaEdicionObra> {
  return { ...valoresDeEdicion(obra), codigo: obra.codigo, tipo_contrato: obra.tipo_contrato };
}

/**
 * Lo que viaja en `PATCH /obras/{id}`: los seis campos editables y ninguno más. Se arma campo a campo y no con «todo
 * menos los de solo lectura», para que un campo nuevo del formulario no salga al servidor sin decidirlo aquí.
 */
export function cambiosDeEdicion(valores: z.output<typeof esquemaEdicionObra>): ObraCambios {
  return {
    nombre: valores.nombre,
    domicilio: valores.domicilio,
    retencion_destajo_pct: valores.retencion_destajo_pct,
    fondo_garantia_pct: valores.fondo_garantia_pct,
    umbral_alerta_pct: valores.umbral_alerta_pct,
    iva_acreditable: valores.iva_acreditable,
  };
}
