import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";

/** Zod valida la forma del formulario antes de enviar (CA-6 esc. 4). La respuesta del servidor no se valida aquí. */
export const esquemaInicioSesion = z.object({
  email: z.email("Escribe un correo válido."),
  contrasena: z.string().min(1, "Escribe tu contraseña."),
});

export type EntradaInicioSesion = z.infer<typeof esquemaInicioSesion>;

export const resolverInicioSesion = zodResolver(esquemaInicioSesion);
