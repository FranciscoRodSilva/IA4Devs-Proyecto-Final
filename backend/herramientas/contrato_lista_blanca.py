"""Contrato propio de import-linter (TKT-004): lo que alcanzan los módulos de `origen`,
directa o indirectamente, es de la biblioteca estándar, de `permitidos` o del propio
origen. Sustituye la lista negra de dominio-sin-framework (deuda O1 de TKT-002).

grimp trata la biblioteca estándar como un paquete externo más: se reconoce con
sys.stdlib_module_names del intérprete que ejecuta lint-imports.
"""

from __future__ import annotations

import itertools
import sys
from typing import Any, cast

from grimp import ImportGraph
from importlinter import Contract, ContractCheck, fields, output
from importlinter.application.contract_utils import render_broken_contract_guidance
from importlinter.domain.helpers import module_expressions_to_modules
from importlinter.domain.imports import Module, ModuleExpression


def _es_permitido(modulo: str, permitidos: tuple[str, ...]) -> bool:
    if modulo.partition(".")[0] in sys.stdlib_module_names:
        return True
    return any(modulo == p or modulo.startswith(f"{p}.") for p in permitidos)


class ContratoListaBlanca(Contract):
    origen = fields.ListField(subfield=fields.ModuleExpressionField())
    permitidos = fields.ListField(subfield=fields.ModuleField(), required=False)
    broken_contract_guidance = fields.TextField(required=False)

    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        expresiones = cast("list[ModuleExpression]", self.origen)
        origenes = sorted(m.name for m in module_expressions_to_modules(graph, expresiones))
        if not origenes:
            raise ValueError(f"Ningún módulo coincide con {[e.expression for e in expresiones]}.")
        permitidos = tuple(m.name for m in cast("list[Module] | None", self.permitidos) or [])
        for nombre in (*origenes, *permitidos):
            if nombre not in graph.modules:
                raise ValueError(f"El módulo '{nombre}' no existe.")
        violaciones: list[dict[str, Any]] = []
        for origen in origenes:
            for alcanzado in sorted(graph.find_upstream_modules(origen, as_package=True)):
                if _es_permitido(alcanzado, permitidos):
                    continue
                cadena = graph.find_shortest_chain(
                    importer=origen, imported=alcanzado, as_packages=True
                ) or (origen, alcanzado)
                eslabones = [
                    (
                        a,
                        b,
                        tuple(
                            d["line_number"]
                            for d in graph.get_import_details(importer=a, imported=b)
                        ),
                    )
                    for a, b in itertools.pairwise(cadena)
                ]
                violaciones.append(
                    {"origen": origen, "alcanzado": alcanzado, "eslabones": eslabones}
                )
        return ContractCheck(kept=not violaciones, metadata={"violaciones": violaciones})

    def render_broken_contract(self, check: ContractCheck) -> None:
        for violacion in check.metadata["violaciones"]:
            output.print_error(f"{violacion['origen']} no puede alcanzar {violacion['alcanzado']}:")
            for importador, importado, lineas in violacion["eslabones"]:
                output.indent_cursor()
                output.print_error(
                    f"{importador} -> {importado} (l.{', '.join(map(str, lineas))})", bold=False
                )
            output.new_line()
        render_broken_contract_guidance(cast("str | None", self.broken_contract_guidance))
