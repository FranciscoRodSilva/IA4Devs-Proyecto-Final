import { Link } from "react-router";

/** CA-1 esc. 3 · ruta sin módulo: dentro del armazón, que sigue con su cabecera. */
export function NoEncontrado() {
  return (
    <div className="space-y-3 p-6">
      <h1 className="text-xl font-semibold">Página no encontrada</h1>
      <Link to="/" className="underline">
        Ir al inicio
      </Link>
    </div>
  );
}
