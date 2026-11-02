"""Pruebas de `tools/agentes_cursor.py`.

Los agentes de Cursor se generan desde `.claude/agents/`. Estas pruebas fijan la traducción y
comprueban que lo versionado en `.cursor/agents/` no se haya desfasado del original.

Ejecución, desde la raíz del repositorio:

    python -m unittest discover -s tools/tests -v
"""
from __future__ import annotations

import os
import sys
import unittest

HERRAMIENTAS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if HERRAMIENTAS not in sys.path:
    sys.path.insert(0, HERRAMIENTAS)

import agentes_cursor  # noqa: E402

ESCRIBE = """---
name: desarrollador-prueba
description: Escribe código de prueba.
tools: Read, Glob, Write, Edit, Bash
model: haiku
effort: medium
skills:
  - conv-uno
  - conv-dos
---

# Cuerpo

Texto sin tocar.
"""

LEE = """---
name: analista-prueba
description: Solo lee.
tools: Read, Glob, Grep
model: opus
effort: medium
---

# Cuerpo
"""


class TraduccionTest(unittest.TestCase):
    def test_el_modelo_es_composer_sin_fast(self) -> None:
        traducido = agentes_cursor.traducir(ESCRIBE, "desarrollador-prueba.md")
        self.assertIn("model: composer-2.5[fast=false]\n", traducido)
        self.assertNotIn("model: haiku", traducido)

    def test_se_descartan_tools_effort_y_skills_del_frontmatter(self) -> None:
        campos, _ = agentes_cursor.separar(agentes_cursor.traducir(ESCRIBE, "desarrollador-prueba.md"))
        self.assertEqual(sorted(campos), ["description", "model", "name"])

    def test_las_convenciones_pasan_a_una_instruccion_de_lectura(self) -> None:
        traducido = agentes_cursor.traducir(ESCRIBE, "desarrollador-prueba.md")
        self.assertIn("`.claude/skills/conv-uno/SKILL.md`, `.claude/skills/conv-dos/SKILL.md`", traducido)

    def test_el_cuerpo_se_conserva_literal(self) -> None:
        traducido = agentes_cursor.traducir(ESCRIBE, "desarrollador-prueba.md")
        self.assertTrue(traducido.endswith("# Cuerpo\n\nTexto sin tocar.\n"))

    def test_solo_lectura_cuando_no_hay_escritura_ni_consola(self) -> None:
        self.assertIn("readonly: true", agentes_cursor.traducir(LEE, "analista-prueba.md"))
        self.assertNotIn("readonly", agentes_cursor.traducir(ESCRIBE, "desarrollador-prueba.md"))

    def test_los_enlaces_que_salen_de_claude_siguen_resolviendo(self) -> None:
        texto = LEE + "[a](../skills/conv-x/SKILL.md) [b](../../docs/x.md) [c](./)\n"
        traducido = agentes_cursor.traducir(texto, "analista-prueba.md")
        self.assertIn("(../../.claude/skills/conv-x/SKILL.md)", traducido)
        self.assertIn("(../../docs/x.md)", traducido)
        self.assertIn("(../../.claude/agents/)", traducido)

    def test_rechaza_un_agente_sin_descripcion(self) -> None:
        with self.assertRaises(ValueError):
            agentes_cursor.traducir("---\nname: x\n---\ncuerpo\n", "x.md")

    def test_rechaza_un_archivo_sin_frontmatter(self) -> None:
        with self.assertRaises(ValueError):
            agentes_cursor.traducir("# sin frontmatter\n", "x.md")


class RepositorioTest(unittest.TestCase):
    def test_cursor_agents_coincide_con_claude_agents(self) -> None:
        self.assertEqual(agentes_cursor.verificar(), [])

    def test_todos_los_agentes_usan_composer_sin_fast(self) -> None:
        for nombre in os.listdir(agentes_cursor.DESTINO):
            with open(os.path.join(agentes_cursor.DESTINO, nombre), encoding="utf-8") as f:
                campos, _ = agentes_cursor.separar(f.read())
            self.assertEqual(campos["model"], "composer-2.5[fast=false]", nombre)


if __name__ == "__main__":
    unittest.main()
