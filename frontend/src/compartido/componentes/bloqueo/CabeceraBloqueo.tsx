import type { ErrorBloqueo } from "@/api/errores";

export interface PropsCabeceraBloqueo {
  error: ErrorBloqueo;
  /** Id del título: lo referencia el `aria-labelledby` del contenedor. */
  id: string;
  /** `bloque` para la pantalla; `linea` para el conflicto dentro de un formulario. */
  tamano: "bloque" | "linea";
}

/** La cabecera que corresponde a cada `tipo` de bloqueo. Nunca se decide por el texto del mensaje. */
export function CabeceraBloqueo({ error, id, tamano }: PropsCabeceraBloqueo) {
  const Titulo = tamano === "bloque" ? "h2" : "h3";
  const claseTitulo = tamano === "bloque" ? "text-lg font-semibold" : "font-semibold";
  switch (error.tipo) {
    case "REGLA_NEGOCIO":
      return (
        <>
          <Titulo id={id} className={claseTitulo}>Operación bloqueada</Titulo>
          <p className="text-sm font-medium">Regla {error.regla}</p>
        </>
      );
    case "CONFLICTO":
      return (
        <>
          <Titulo id={id} className={claseTitulo}>No se puede completar</Titulo>
          <p className="text-sm font-medium">{error.codigo}</p>
        </>
      );
    case "CONCURRENCIA":
      return <Titulo id={id} className={claseTitulo}>Inténtalo de nuevo</Titulo>;
  }
}
