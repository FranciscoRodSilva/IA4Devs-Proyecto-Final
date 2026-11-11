import { z } from "zod";
import type { components } from "@/api/generado/servidor";
import type { CampoCatalogo } from "@/compartido/formularios/FormularioCatalogo";
import { porcentajeAFraccion } from "@/compartido/dinero/dinero";

type ObraNueva = components["schemas"]["ObraNueva"];

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
