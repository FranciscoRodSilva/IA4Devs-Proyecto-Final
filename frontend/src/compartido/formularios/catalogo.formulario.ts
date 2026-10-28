import { zodResolver } from "@hookform/resolvers/zod";
import { type DefaultValues, type FieldPath, type Resolver } from "react-hook-form";
import type { z } from "zod";

/*
 * Frontera entre Zod y React Hook Form para un esquema genérico (`E`). Con `E` como parámetro de tipo, Zod 4 no
 * demuestra que el esquema cumpla sus propios tipos de entrada y salida, y los tipos de React Hook Form quedan sin
 * resolver. Estas funciones son el único punto donde se fuerza ese enlace: lo que entra y sale ya está tipado por `E`,
 * y el resto del formulario no necesita conversiones. Ningún `any`.
 */

/** Resolver de validación del esquema `E`: Zod valida la forma antes de enviar (CA-11 esc. 3). */
export function resolverCatalogo<E extends z.ZodObject>(esquema: E): Resolver<z.input<E>, unknown, z.output<E>> {
  return zodResolver(esquema) as unknown as Resolver<z.input<E>, unknown, z.output<E>>;
}

/** Los valores iniciales del formulario, como los pide React Hook Form para el mismo `E`. */
export function valoresDeFormulario<E extends z.ZodObject>(valores: z.input<E>): DefaultValues<z.input<E>> {
  return valores as DefaultValues<z.input<E>>;
}

/** Ruta de un campo para React Hook Form. Un nombre de `campos` es una clave del esquema, y es una ruta de primer nivel. */
export function rutaDeCampo<E extends z.ZodObject>(nombre: keyof z.input<E> & string): FieldPath<z.input<E>> {
  return nombre as FieldPath<z.input<E>>;
}
