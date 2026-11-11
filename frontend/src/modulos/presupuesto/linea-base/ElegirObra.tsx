import { Link } from "react-router";
import { type ClaveSeccion, seccion } from "@/app/navegacion/secciones";

/**
 * D-7 · Las secciones «Línea base» y «Presupuesto de control» del menú no tienen obra elegida: remiten a «Obras»,
 * donde cada fila lleva a la pantalla de su obra. No pide nada al servidor.
 */
export function ElegirObra({ clave }: { clave: ClaveSeccion }) {
  const { titulo } = seccion(clave);
  return (
    <section className="grid gap-3 p-6">
      <h1 className="text-xl font-semibold">{titulo}</h1>
      <p>Elige la obra en «Obras»: su línea base y su presupuesto de control están en la misma pantalla.</p>
      <div>
        <Link to="/obras" className="underline">
          Ir a Obras
        </Link>
      </div>
    </section>
  );
}
