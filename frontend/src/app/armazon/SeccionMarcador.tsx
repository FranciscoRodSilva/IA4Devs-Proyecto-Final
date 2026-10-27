import { type ClaveSeccion, seccion } from "@/app/navegacion/secciones";

/** Pantalla provisional de una sección cuyo módulo aún no la implementa. */
export function SeccionMarcador({ clave }: { clave: ClaveSeccion }) {
  const { titulo } = seccion(clave);
  return (
    <div className="p-6">
      <h1 className="text-xl font-semibold">{titulo}</h1>
      <p>Esta sección aún no está disponible.</p>
    </div>
  );
}
