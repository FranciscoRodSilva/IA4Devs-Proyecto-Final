import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import type { components } from "@/api/generado/servidor";
import { esquemaMotivo } from "@/compartido/formularios/motivo.formulario";

type ClaveTipoPartida = components["schemas"]["ClaveTipoPartida"];

/** TKT-018a · CA-10. Forma del importe de un tope, igual que el patrón del contrato pero solo con dígitos ASCII. */
export const PATRON_IMPORTE_TOPE = /^[0-9]{1,14}(\.[0-9]{1,4})?$/;

export const MENSAJE_IMPORTE_TOPE =
  "Escribe un importe sin signo ni comas, con hasta 14 enteros y 4 decimales, como 45000.00.";

/** Una fila sin capturar (cadena vacía) es válida; el importe se valida solo si hay algo escrito. Valida forma, no regla. */
const campoTope = z
  .string()
  .trim()
  .refine((valor) => valor === "" || PATRON_IMPORTE_TOPE.test(valor), MENSAJE_IMPORTE_TOPE);

export const esquemaTopes = z.object({
  MUROS: campoTope,
  PLAFONES_Y_CAJILLOS: campoTope,
  ENCHAPES: campoTope,
  GENERALES: campoTope,
} satisfies Record<ClaveTipoPartida, unknown>);

export type EntradaTopes = z.infer<typeof esquemaTopes>;

export const resolverTopes = zodResolver(esquemaTopes);

/** TKT-018a · recaptura. El tope es obligatorio y el motivo usa las mismas reglas que el resto de la aplicación. */
export const esquemaRecaptura = z.object({
  tope: z
    .string()
    .trim()
    .min(1, "El tope es obligatorio.")
    .regex(PATRON_IMPORTE_TOPE, MENSAJE_IMPORTE_TOPE),
  motivo: esquemaMotivo.shape.motivo,
});

export type EntradaRecaptura = z.infer<typeof esquemaRecaptura>;

export const resolverRecaptura = zodResolver(esquemaRecaptura);
