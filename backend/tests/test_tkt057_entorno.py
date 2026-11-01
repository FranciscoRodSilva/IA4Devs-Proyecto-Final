"""Entorno y pipeline (TKT-057, fila 14, criterio CA-17 · RNF-07): TC-64, TC-65 y TC-66.

Sin Docker: se leen `.env.example` y `.github/workflows/ci.yml`, versionados en el repositorio.

La lógica de cada comprobación vive en una función `problemas_*` que devuelve la lista de
problemas, vacía si el criterio se cumple. Los casos sobre el archivo real afirman que la lista
está vacía; los casos de control demuestran, sobre texto sintético, que la misma función da por
buena la forma correcta y se pone en rojo ante cada forma incorrecta, de modo que un verde sobre
el archivo real no sea una vacuidad.
"""

import re
from pathlib import Path
from typing import Any

import yaml

RAIZ = Path(__file__).resolve().parents[2]
ENV_EJEMPLO = RAIZ / ".env.example"
CI = RAIZ / ".github" / "workflows" / "ci.yml"

ROLES = ("MIGRACION", "APLICACION", "LECTURA")
CLAVES_DE_CONTRASENA = tuple(f"CIMENTA_DB_CONTRASENA_{rol}" for rol in ROLES)
PREFIJO_DE_DESARROLLO = "solo-desarrollo-"
LIMITES_COMENTADOS = (
    "CIMENTA_LIMITE_FALLOS_CUENTA",
    "CIMENTA_LIMITE_FALLOS_ORIGEN",
    "CIMENTA_LIMITE_MINUTOS",
)


# ---------------------------------------------------------------------------------------------
# .env.example
# ---------------------------------------------------------------------------------------------


def _claves_activas(texto: str) -> dict[str, str]:
    """`CLAVE=valor` de las líneas no comentadas, sin el comentario al final de línea."""
    pares: dict[str, str] = {}
    for linea in texto.splitlines():
        contenido = linea.strip()
        if not contenido or contenido.startswith("#") or "=" not in contenido:
            continue
        clave, valor = contenido.split("=", 1)
        pares[clave.strip()] = re.split(r"\s+#", valor, maxsplit=1)[0].strip()
    return pares


def problemas_de_contrasenas_en_env_example(texto: str) -> list[str]:
    """CA-17 esc. 1: las tres claves existen, sin valor, y no queda ninguna cadena `solo-desarrollo-`."""
    problemas: list[str] = []
    activas = _claves_activas(texto)
    for clave in CLAVES_DE_CONTRASENA:
        if clave not in activas:
            problemas.append(f"falta la clave {clave}")
        elif activas[clave] != "":
            problemas.append(f"{clave} lleva valor")
    if PREFIJO_DE_DESARROLLO in texto:
        problemas.append(f"el archivo contiene la cadena {PREFIJO_DE_DESARROLLO}")
    return problemas


def problemas_de_la_seccion_de_tkt057(texto: str) -> list[str]:
    """Fila 14: `CIMENTA_ALMACEN_ORIGEN` documentada y los tres límites comentados, ninguno activo."""
    problemas: list[str] = []
    if not re.search(r"^\s*#?\s*CIMENTA_ALMACEN_ORIGEN=", texto, flags=re.MULTILINE):
        problemas.append("no documenta CIMENTA_ALMACEN_ORIGEN")
    activas = _claves_activas(texto)
    for clave in LIMITES_COMENTADOS:
        if clave in activas:
            problemas.append(f"{clave} está activa; debe ir comentada")
        elif not re.search(rf"^\s*#\s*{clave}=", texto, flags=re.MULTILINE):
            problemas.append(f"no documenta {clave} (comentada)")
    return problemas


ENV_EJEMPLO_VALIDO = """\
CIMENTA_DB_HOST=127.0.0.1
CIMENTA_DB_CONTRASENA_MIGRACION=
CIMENTA_DB_CONTRASENA_APLICACION=   # se define en .env
CIMENTA_DB_CONTRASENA_LECTURA=
# CIMENTA_ALMACEN_ORIGEN=
# CIMENTA_LIMITE_FALLOS_CUENTA=5
# CIMENTA_LIMITE_FALLOS_ORIGEN=20
# CIMENTA_LIMITE_MINUTOS=15
"""


def test_tkt057_ca17_esc01_env_example_lista_las_tres_contrasenas_sin_valor() -> None:
    """TC-64 · CA-17 esc. 1 · RNF-07 — las tres claves de contraseña no llevan valor ni queda `solo-desarrollo-`."""
    texto = ENV_EJEMPLO.read_text(encoding="utf-8")

    assert problemas_de_contrasenas_en_env_example(texto) == []


def test_tkt057_ca17_esc01_env_example_documenta_la_seccion_de_tkt057() -> None:
    """TC-64 · CA-17 · fila 14 — `CIMENTA_ALMACEN_ORIGEN` documentada y los tres límites comentados."""
    texto = ENV_EJEMPLO.read_text(encoding="utf-8")

    assert problemas_de_la_seccion_de_tkt057(texto) == []


def test_tkt057_ca17_esc01_control_el_comprobador_distingue_lo_correcto_de_lo_incorrecto() -> None:
    """TC-64 · CA-17 esc. 1 — control: la forma correcta pasa y cada desvío nombra su problema."""
    assert problemas_de_contrasenas_en_env_example(ENV_EJEMPLO_VALIDO) == []
    assert problemas_de_la_seccion_de_tkt057(ENV_EJEMPLO_VALIDO) == []

    con_valor = ENV_EJEMPLO_VALIDO.replace(
        "CIMENTA_DB_CONTRASENA_MIGRACION=\n", "CIMENTA_DB_CONTRASENA_MIGRACION=x\n"
    )
    assert problemas_de_contrasenas_en_env_example(con_valor) == [
        "CIMENTA_DB_CONTRASENA_MIGRACION lleva valor"
    ]

    sin_clave = ENV_EJEMPLO_VALIDO.replace("CIMENTA_DB_CONTRASENA_LECTURA=\n", "")
    assert problemas_de_contrasenas_en_env_example(sin_clave) == [
        "falta la clave CIMENTA_DB_CONTRASENA_LECTURA"
    ]

    clave_comentada = ENV_EJEMPLO_VALIDO.replace(
        "CIMENTA_DB_CONTRASENA_LECTURA=\n", "# CIMENTA_DB_CONTRASENA_LECTURA=\n"
    )
    assert problemas_de_contrasenas_en_env_example(clave_comentada) == [
        "falta la clave CIMENTA_DB_CONTRASENA_LECTURA"
    ]

    con_prefijo = ENV_EJEMPLO_VALIDO + "# antes valía solo-desarrollo-lectura\n"
    assert problemas_de_contrasenas_en_env_example(con_prefijo) == [
        f"el archivo contiene la cadena {PREFIJO_DE_DESARROLLO}"
    ]

    limite_activo = ENV_EJEMPLO_VALIDO.replace(
        "# CIMENTA_LIMITE_MINUTOS=15", "CIMENTA_LIMITE_MINUTOS=15"
    )
    assert problemas_de_la_seccion_de_tkt057(limite_activo) == [
        "CIMENTA_LIMITE_MINUTOS está activa; debe ir comentada"
    ]
    sin_origen = ENV_EJEMPLO_VALIDO.replace("# CIMENTA_ALMACEN_ORIGEN=\n", "")
    assert problemas_de_la_seccion_de_tkt057(sin_origen) == ["no documenta CIMENTA_ALMACEN_ORIGEN"]


# ---------------------------------------------------------------------------------------------
# Trabajo `humo` de ci.yml
# ---------------------------------------------------------------------------------------------


def _pasos_de_humo(flujo: dict[str, Any]) -> list[dict[str, Any]]:
    return list(flujo["jobs"]["humo"]["steps"])


def _run(paso: dict[str, Any]) -> str:
    return str(paso.get("run", ""))


def problemas_del_trabajo_humo(flujo: dict[str, Any]) -> list[str]:
    """CA-17 esc. 2: el entorno de `humo` nace con contraseñas generadas dentro del trabajo, sin copiar el ejemplo."""
    problemas: list[str] = []
    trabajo = flujo["jobs"]["humo"]
    pasos = _pasos_de_humo(flujo)

    for paso in pasos:
        if re.search(r"\bcp\b[^\n]*\.env\.example", _run(paso)):
            problemas.append("un paso copia .env.example tal cual")

    generadores = [
        i
        for i, paso in enumerate(pasos)
        if "openssl rand -hex" in _run(paso)
        and "CIMENTA_DB_CONTRASENA_" in _run(paso)
        and all(rol in _run(paso) for rol in ROLES)
        and re.search(r">>?\s*\.env\b", _run(paso))
    ]
    if not generadores:
        problemas.append(
            "ningún paso genera las tres contraseñas con openssl rand y las escribe en .env"
        )
    else:
        levantar = next(
            (i for i, paso in enumerate(pasos) if "docker compose up" in _run(paso)), None
        )
        if levantar is None:
            problemas.append("ningún paso levanta la base con docker compose up")
        elif generadores[0] >= levantar:
            problemas.append("las contraseñas se generan después de docker compose up")

    for paso in pasos:
        for asignacion in re.finditer(
            r"CIMENTA_DB_CONTRASENA_(?:[A-Z]+|\$\{\w+\})=([^\s\"']*)", _run(paso)
        ):
            if not asignacion.group(1).startswith("$("):
                problemas.append(f"valor literal para una contraseña: {asignacion.group(0)}")

    for ambito in (trabajo, *pasos):
        entorno = ambito.get("env") or {}
        for clave in entorno:
            if str(clave).startswith("CIMENTA_DB_CONTRASENA_"):
                problemas.append(f"{clave} fijada en env: del trabajo, con un valor literal")
    return problemas


def _cargar_flujo(texto: str) -> dict[str, Any]:
    flujo = yaml.safe_load(texto)
    assert isinstance(flujo, dict)
    return flujo


HUMO_VALIDO = """\
jobs:
  humo:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@abc
      - name: Preparar el entorno con contraseñas de prueba generadas
        run: |
          grep -v '^CIMENTA_DB_CONTRASENA_' .env.example > .env
          for rol in MIGRACION APLICACION LECTURA; do
            echo "CIMENTA_DB_CONTRASENA_${rol}=$(openssl rand -hex 24)" >> .env
          done
      - name: Levantar PostgreSQL
        run: docker compose up -d --wait db
"""

PASO_GENERADOR = """\
      - name: Preparar el entorno con contraseñas de prueba generadas
        run: |
          grep -v '^CIMENTA_DB_CONTRASENA_' .env.example > .env
          for rol in MIGRACION APLICACION LECTURA; do
            echo "CIMENTA_DB_CONTRASENA_${rol}=$(openssl rand -hex 24)" >> .env
          done
"""
PASO_LEVANTAR = """\
      - name: Levantar PostgreSQL
        run: docker compose up -d --wait db
"""


def test_tkt057_ca17_esc02_humo_no_copia_el_ejemplo_tal_cual() -> None:
    """TC-65 · CA-17 esc. 2 · RNF-07 — ningún paso de `humo` hace `cp .env.example .env`."""
    flujo = _cargar_flujo(CI.read_text(encoding="utf-8"))

    copias = [
        _run(paso)
        for paso in _pasos_de_humo(flujo)
        if re.search(r"\bcp\b[^\n]*\.env\.example", _run(paso))
    ]

    assert copias == []


def test_tkt057_ca17_esc02_humo_genera_las_tres_contrasenas_antes_de_levantar_la_base() -> None:
    """TC-65 · CA-17 esc. 2 · RNF-07 — un paso genera las tres con `openssl rand -hex`, antes de `docker compose up`."""
    flujo = _cargar_flujo(CI.read_text(encoding="utf-8"))

    problemas = [
        p
        for p in problemas_del_trabajo_humo(flujo)
        if p.startswith(("ningún paso", "las contraseñas se generan"))
    ]

    assert problemas == []


def test_tkt057_ca17_esc02_humo_no_fija_ningun_valor_literal_para_las_contrasenas() -> None:
    """TC-65 · CA-17 esc. 2 · RNF-07 — ni asignaciones ni `env:` con valor literal, y `solo-desarrollo-` no está en ci.yml."""
    texto = CI.read_text(encoding="utf-8")
    flujo = _cargar_flujo(texto)

    problemas = problemas_del_trabajo_humo(flujo)

    assert problemas == []
    assert PREFIJO_DE_DESARROLLO not in texto


def test_tkt057_ca17_esc02_control_el_comprobador_distingue_lo_correcto_de_lo_incorrecto() -> None:
    """TC-65 · CA-17 esc. 2 — control: el paso del diseño pasa y cada mutante nombra su problema."""
    assert problemas_del_trabajo_humo(_cargar_flujo(HUMO_VALIDO)) == []

    copia = HUMO_VALIDO.replace(PASO_GENERADOR, "      - run: cp .env.example .env\n")
    assert problemas_del_trabajo_humo(_cargar_flujo(copia)) == [
        "un paso copia .env.example tal cual",
        "ningún paso genera las tres contraseñas con openssl rand y las escribe en .env",
    ]

    despues = HUMO_VALIDO.replace(PASO_GENERADOR + PASO_LEVANTAR, PASO_LEVANTAR + PASO_GENERADOR)
    assert problemas_del_trabajo_humo(_cargar_flujo(despues)) == [
        "las contraseñas se generan después de docker compose up"
    ]

    literal = HUMO_VALIDO.replace("$(openssl rand -hex 24)", "hunter2")
    assert problemas_del_trabajo_humo(_cargar_flujo(literal)) == [
        "ningún paso genera las tres contraseñas con openssl rand y las escribe en .env",
        "valor literal para una contraseña: CIMENTA_DB_CONTRASENA_${rol}=hunter2",
    ]

    con_env = HUMO_VALIDO.replace(
        "    runs-on: ubuntu-24.04\n",
        "    runs-on: ubuntu-24.04\n    env:\n      CIMENTA_DB_CONTRASENA_APLICACION: abc\n",
    )
    assert problemas_del_trabajo_humo(_cargar_flujo(con_env)) == [
        "CIMENTA_DB_CONTRASENA_APLICACION fijada en env: del trabajo, con un valor literal"
    ]


# ---------------------------------------------------------------------------------------------
# TC-66 · regresión de TKT-003
# ---------------------------------------------------------------------------------------------


def test_tkt057_ca17_regresion_las_tres_contrasenas_de_env_example_existen_y_estan_vacias() -> None:
    """TC-66 · CA-17 — contrapartida de TC-64/TC-65 de TKT-003: las tres claves existen y no llevan valor."""
    activas = _claves_activas(ENV_EJEMPLO.read_text(encoding="utf-8"))

    contrasenas = {clave: activas.get(clave) for clave in CLAVES_DE_CONTRASENA}

    assert contrasenas == {clave: "" for clave in CLAVES_DE_CONTRASENA}
