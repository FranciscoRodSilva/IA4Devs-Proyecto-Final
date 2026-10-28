import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

/** TKT-008 · CA-12 esc. 2. Zod valida el texto antes de enviar; la respuesta del servidor no se valida aquí. */
export const esquemaMotivo = z.object({
  motivo: z.string().trim().min(1, "El motivo es obligatorio.").max(2000, "El motivo admite hasta 2,000 caracteres."),
});

export type EntradaMotivo = z.infer<typeof esquemaMotivo>;

export const resolverMotivo = zodResolver(esquemaMotivo);
