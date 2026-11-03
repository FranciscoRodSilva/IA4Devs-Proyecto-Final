-- TKT-070 · CA-5, CA-7, CA-R1. Ejecutar con rol cimenta_migracion por el túnel (guía §7).
SELECT 'rol_existe_cimenta_migracion' AS comprobacion,
       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cimenta_migracion') AS ok
UNION ALL
SELECT 'rol_existe_cimenta_aplicacion',
       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cimenta_aplicacion')
UNION ALL
SELECT 'rol_existe_cimenta_lectura',
       EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'cimenta_lectura')
UNION ALL
SELECT 'login_cimenta_aplicacion',
       (SELECT rolcanlogin FROM pg_roles WHERE rolname = 'cimenta_aplicacion')
UNION ALL
SELECT 'login_cimenta_lectura',
       (SELECT rolcanlogin FROM pg_roles WHERE rolname = 'cimenta_lectura')
UNION ALL
SELECT 'contrasena_cimenta_aplicacion',
       (SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname = 'cimenta_aplicacion')
UNION ALL
SELECT 'contrasena_cimenta_lectura',
       (SELECT rolpassword IS NOT NULL FROM pg_authid WHERE rolname = 'cimenta_lectura')
UNION ALL
SELECT 'aplicacion_sin_update_bitacora',
       NOT has_table_privilege('cimenta_aplicacion', 'bitacora', 'UPDATE')
UNION ALL
SELECT 'aplicacion_sin_delete_bitacora',
       NOT has_table_privilege('cimenta_aplicacion', 'bitacora', 'DELETE')
UNION ALL
SELECT 'aplicacion_sin_truncate_bitacora',
       NOT has_table_privilege('cimenta_aplicacion', 'bitacora', 'TRUNCATE')
UNION ALL
SELECT 'aplicacion_sin_update_intento_acceso',
       NOT has_table_privilege('cimenta_aplicacion', 'intento_acceso', 'UPDATE')
UNION ALL
SELECT 'aplicacion_sin_delete_intento_acceso',
       NOT has_table_privilege('cimenta_aplicacion', 'intento_acceso', 'DELETE')
UNION ALL
SELECT 'aplicacion_sin_truncate_intento_acceso',
       NOT has_table_privilege('cimenta_aplicacion', 'intento_acceso', 'TRUNCATE')
UNION ALL
SELECT 'aplicacion_sin_update_linea_base_concepto',
       NOT has_table_privilege('cimenta_aplicacion', 'linea_base_concepto', 'UPDATE')
UNION ALL
SELECT 'aplicacion_sin_delete_linea_base_concepto',
       NOT has_table_privilege('cimenta_aplicacion', 'linea_base_concepto', 'DELETE')
UNION ALL
SELECT 'aplicacion_sin_truncate_linea_base_concepto',
       NOT has_table_privilege('cimenta_aplicacion', 'linea_base_concepto', 'TRUNCATE')
UNION ALL
SELECT 'lectura_sin_select_sesion',
       NOT has_table_privilege('cimenta_lectura', 'sesion', 'SELECT')
UNION ALL
SELECT 'lectura_sin_select_usuario',
       NOT has_table_privilege('cimenta_lectura', 'usuario', 'SELECT')
UNION ALL
SELECT 'disparador_trg_linea_base_concepto_inmutable',
       EXISTS (
           SELECT 1 FROM pg_trigger
           WHERE tgname = 'trg_linea_base_concepto_inmutable'
             AND NOT tgisinternal
             AND tgenabled = 'O'
       )
UNION ALL
SELECT 'disparador_trg_explosion_presupuesto_inmutable',
       EXISTS (
           SELECT 1 FROM pg_trigger
           WHERE tgname = 'trg_explosion_presupuesto_inmutable'
             AND NOT tgisinternal
             AND tgenabled = 'O'
       )
UNION ALL
SELECT 'disparador_trg_linea_base_solo_avanza',
       EXISTS (
           SELECT 1 FROM pg_trigger
           WHERE tgname = 'trg_linea_base_solo_avanza'
             AND NOT tgisinternal
             AND tgenabled = 'O'
       )
UNION ALL
SELECT 'usuario_sin_filas',
       NOT EXISTS (SELECT 1 FROM usuario);
