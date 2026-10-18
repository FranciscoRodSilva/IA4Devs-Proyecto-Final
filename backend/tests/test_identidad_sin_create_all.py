"""Revisión estática del arnés (TKT-003, fila 6): TC-17.

Sin Docker. El esquema de las pruebas sale de `alembic upgrade head`, nunca de la creación
automática de tablas del ORM, y ninguna prueba ni migración habla con un motor que no sea PostgreSQL.

Las cadenas buscadas se construyen por concatenación para que este archivo no se encuentre a sí
mismo. Por la misma razón, el nombre de la función de prueba no contiene la llamada buscada: el
escaneo lee este archivo como cualquier otro y un nombre con la llamada, seguido de paréntesis,
lo delataría.
"""

import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]

CARPETAS_REVISADAS = (BACKEND / "tests", BACKEND / "migraciones", BACKEND / "herramientas")

ARCHIVOS_QUE_LA_REVISION_DEBE_INCLUIR = {
    "conftest.py",
    "env.py",
    "v0001_identidad_roles_y_esquema.py",
    "v0002_semilla_roles_de_negocio.py",
    "test_identidad_credenciales.py",
    "test_identidad_esquema.py",
    "test_identidad_migracion.py",
    "test_identidad_migracion_cli.py",
    "test_identidad_migracion_ciclo.py",
    "test_identidad_permisos.py",
    "test_identidad_permisos_tablas.py",
    "test_identidad_privilegios_por_omision.py",
    "test_identidad_semilla.py",
    "test_identidad_sin_create_all.py",
    "test_identidad_tiempos_maximos.py",
    "test_identidad_uso_del_esquema.py",
}


def test_tkt003_ca09_esc01_esquema_sin_creacion_automatica() -> None:
    """TC-17 · CA-9 esc. 1 — ningún archivo del arnés ni de las migraciones construye el esquema a mano.

    Ni la creación automática de tablas del ORM, ni un controlador o una URL de SQLite. La revisión exige haber leído el
    arnés, las dos migraciones y los archivos de prueba del ticket: una carpeta vacía o un archivo
    que no se revisó no puede dar por bueno el resultado.
    """
    archivos = sorted(ruta for carpeta in CARPETAS_REVISADAS for ruta in carpeta.rglob("*.py"))
    nombres = {ruta.name for ruta in archivos}
    faltan = ARCHIVOS_QUE_LA_REVISION_DEBE_INCLUIR - nombres
    assert faltan == set(), faltan

    cadena_prohibida = "create_" + "all("
    motor_prohibido = re.compile("sqlite" + r"(?:3|:|\+)|aio" + "sqlite", re.IGNORECASE)
    infractores: list[str] = []
    for ruta in archivos:
        texto = ruta.read_text(encoding="utf-8")
        if cadena_prohibida in texto:
            infractores.append(f"{ruta.name}: llama a {cadena_prohibida}")
        if motor_prohibido.search(texto):
            infractores.append(f"{ruta.name}: usa un motor que no es PostgreSQL")

    assert infractores == []
