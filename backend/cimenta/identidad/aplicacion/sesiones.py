"""Casos de uso de sesión de identidad (TKT-006): `abrir_sesion`, `validar_sesion` y
`cerrar_sesion_vigente`. Cada caso de uso abre su propia
transacción con `fabrica_sesiones().begin()`: el repositorio no confirma, y el rechazo se lanza
siempre fuera del bloque, para que la fila de `intento_acceso` quede confirmada (TC-27).
"""

from __future__ import annotations

import uuid

from cimenta.identidad.aplicacion.contexto import ContextoIdentidad, UsuarioAutenticado
from cimenta.identidad.dominio.acceso import credenciales_aceptadas
from cimenta.identidad.dominio.correo import normalizar_correo
from cimenta.identidad.dominio.vigencia import EstadoSesion, evaluar_vigencia
from cimenta.identidad.infraestructura import repositorio
from contrato_error import SesionInvalida

MENSAJE_SIN_SESION = "No hay una sesión iniciada."
MENSAJE_SESION_CADUCADA = "La sesión caducó. Inicia sesión de nuevo."
MENSAJE_SESION_REVOCADA = "La sesión ya no es válida. Inicia sesión de nuevo."
MENSAJE_CREDENCIALES_INVALIDAS = "El correo o la contraseña no son correctos."


def abrir_sesion(
    contexto: ContextoIdentidad,
    *,
    correo_escrito: str,
    contrasena: str,
    origen_ip: str | None,
    agente_usuario: str | None,
) -> UsuarioAutenticado:
    """M2 · RNF-03 · RNF-04. Verifica exactamente un hash, exista o no el correo. El intento se
    confirma antes de lanzar el 401: lanzar dentro del bloque desharía la fila (objeción 1)."""
    ahora = contexto.reloj()
    configuracion = contexto.configuracion
    abierta: UsuarioAutenticado | None = None
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        credencial = repositorio.buscar_credencial(sesion_bd, normalizar_correo(correo_escrito))
        hash_a_verificar = (
            credencial.password_hash
            if credencial is not None
            else contexto.contrasenas.hash_de_descarte
        )
        coincide = contexto.contrasenas.verificar(contrasena, hash_a_verificar)
        aceptadas = credenciales_aceptadas(
            existe=credencial is not None,
            activo=credencial is not None and credencial.activo,
            coincide=coincide,
        )
        repositorio.insertar_intento(
            sesion_bd,
            email=correo_escrito,
            usuario_id=credencial.id if credencial is not None else None,
            exitoso=aceptadas,
            ocurrido_en=ahora,
            origen_ip=origen_ip,
        )
        if aceptadas and credencial is not None:
            sesion_id = uuid.uuid4()
            expira_en = ahora + configuracion.caducidad_absoluta
            repositorio.insertar_sesion(
                sesion_bd,
                sesion_id=sesion_id,
                usuario_id=credencial.id,
                ahora=ahora,
                expira_en=expira_en,
                origen_ip=origen_ip,
                agente_usuario=agente_usuario,
            )
            repositorio.marcar_ultimo_acceso(sesion_bd, credencial.id, ahora)
            abierta = UsuarioAutenticado(
                usuario_id=credencial.id,
                sesion_id=sesion_id,
                nombre=credencial.nombre,
                email=credencial.email,
                roles=repositorio.roles_de(sesion_bd, credencial.id),
                expira_en=expira_en,
                expira_por_inactividad_en=ahora + configuracion.caducidad_inactividad,
            )
    if abierta is None:
        raise SesionInvalida(
            motivo="CREDENCIALES_INVALIDAS", mensaje=MENSAJE_CREDENCIALES_INVALIDAS
        )
    return abierta


def validar_sesion(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> UsuarioAutenticado:
    """M5 · M6 · M7 · RNF-01. Lee la sesión, el usuario y los roles en cada petición, sin caché.
    Si sigue vigente desliza ultima_actividad con una guarda contra un cierre concurrente."""
    ahora = contexto.reloj()
    inactividad = contexto.configuracion.caducidad_inactividad
    estado: EstadoSesion | None = None
    autenticado: UsuarioAutenticado | None = None
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        fila = repositorio.leer_sesion(sesion_bd, sesion_id)
        if fila is not None:
            estado = evaluar_vigencia(
                ahora=ahora,
                expira_en=fila.expira_en,
                vence_por_inactividad_en=fila.ultima_actividad + inactividad,
                revocada=fila.revocada_en is not None,
                usuario_activo=fila.usuario_activo,
            )
            if estado is EstadoSesion.VIGENTE and not repositorio.tocar_sesion(
                sesion_bd, sesion_id, ahora
            ):
                estado = EstadoSesion.REVOCADA
            if estado is EstadoSesion.VIGENTE:
                autenticado = UsuarioAutenticado(
                    usuario_id=fila.usuario_id,
                    sesion_id=sesion_id,
                    nombre=fila.nombre,
                    email=fila.email,
                    roles=repositorio.roles_de(sesion_bd, fila.usuario_id),
                    expira_en=fila.expira_en,
                    expira_por_inactividad_en=ahora + inactividad,
                )
    if estado is None:
        raise SesionInvalida(motivo="SIN_SESION", mensaje=MENSAJE_SIN_SESION)
    if estado is EstadoSesion.CADUCADA:
        raise SesionInvalida(motivo="SESION_CADUCADA", mensaje=MENSAJE_SESION_CADUCADA)
    if autenticado is None:
        raise SesionInvalida(motivo="SESION_REVOCADA", mensaje=MENSAJE_SESION_REVOCADA)
    return autenticado


def cerrar_sesion_vigente(contexto: ContextoIdentidad, sesion_id: uuid.UUID) -> None:
    """M4: escribe revocada_en; nunca borra la fila. Si un cierre concurrente ganó, no hace nada."""
    with contexto.fabrica_sesiones().begin() as sesion_bd:
        repositorio.revocar_sesion(sesion_bd, sesion_id, contexto.reloj())
