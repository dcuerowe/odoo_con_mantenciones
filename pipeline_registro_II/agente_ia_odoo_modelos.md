# Instructivo de Modelos y Campos de Odoo para Agente de Inteligencia Artificial

## Contexto Operativo
Este documento define los límites de interacción de datos para el Agente de Inteligencia Artificial (IA) incrustado en el entorno de Odoo. El agente debe utilizar exclusivamente los modelos, campos y métodos descritos a continuación al procesar integraciones de formularios (p.ej., operaciones derivadas de `data_processing.py` y `processor.py`), asegurando así la integridad de la base de datos de Mantenimiento e Inventario.

---

## 1. Módulo: Integración Personalizada
### Modelo: `x_inbox_integracion`
**Propósito:** Actúa como bandeja de entrada de los datos capturados y procesados antes de ser transformados en registros formales de Odoo.

* **Operaciones Permitidas:** Creación (`create`)
* **Campos de Escritura:**
  * `x_name`: Nombre o referencia generada (Ej: N° de OT).
  * `x_studio_tcnico`: ID del técnico ejecutor.
  * `x_studio_punto_de_monitoreo`: ID relacional a la ubicación/punto de monitoreo.
  * `x_studio_tipo_de_trabajo`: Clasificación del trabajo (Ej: MP, MC, I).
  * `x_studio_origen`: Identificador del origen de los datos.
  * `x_studio_stage_id`: Estado del registro (Nuevo, En Proceso, Resuelto).
  * `x_studio_e_i`: Equipo o instrumento involucrado.
  * `x_studio_modelo`: Modelo del equipo reportado.
  * `x_studio_nmero_de_serie`: Número de serie del equipo reportado.
  * `x_studio_etiqueta`: Etiqueta contextual sobre la incidencia del equipo.
  * `x_studio_mensaje`: Descripción o mensaje para revisión.
  * `x_studio_carpeta`: Enlace a repositorio documental (Ej: SharePoint).
  * `x_studio_fecha_de_ejecucin`: Fecha de la operación.
* **Métodos Específicos a Invocar:**
  * `message_subscribe`: Suscribir usuarios clave (partners) para seguimiento del registro.
  * `message_post`: Publicar notificaciones de validación en el *chatter* junto a los reportes generados.

---

## 2. Módulo: Mantenimiento (Equipos)
### Modelo: `maintenance.equipment`
**Propósito:** Gestionar la base instalada de sondas, tableros y dispositivos.

* **Operaciones Permitidas:** Búsqueda y Lectura (`search`, `search_read`, `read`)
* **Campos de Búsqueda (Domain):**
  * `serial_no`: Utilizado de forma estricta para cruzar el dispositivo físico con el sistema.
* **Campos de Lectura:**
  * `id`: Identificador interno (Primary Key).
  * `x_studio_location`: Identificador relacional para validar si un equipo ha sido movido o carece de instalación oficial.
* **Métodos Específicos a Invocar:**
  * `message_post`: Alertar sobre traslados no registrados o inconsistencias directamente en el historial del equipo.

---

## 3. Módulo: Mantenimiento (Operaciones)
### Modelo: `maintenance.request`
**Propósito:** Trazabilidad de las Órdenes de Trabajo (OT) de instalación, mantenimientos preventivos/correctivos y configuraciones.

* **Operaciones Permitidas:** Búsqueda, Lectura, Creación, Actualización (`search`, `read`, `create`, `write`)
* **Campos de Búsqueda (Domain):**
  * `equipment_id`: ID relacional del equipo intervenido.
  * `maintenance_type`: Tipo de mantenimiento nativo de Odoo.
  * `x_studio_tipo_de_trabajo`: Subclasificación personalizada del trabajo.
  * `id`: ID único de la petición.
* **Campos de Escritura y Actualización:**
  * `name`: Título descriptivo (Ej: "Mantenimiento Correctivo | Sonda XYZ").
  * `equipment_id`: Equipo a vincular.
  * `stage_id`: Control del estado del ticket (En proceso, Finalizado, Desechado).
  * `x_studio_tipo_de_trabajo`: Clasificación del trabajo.
  * `schedule_date`: Fecha de la ejecución real.
  * `close_date`: Fecha de cierre del ticket (Actualización).
  * `description`: Anotaciones del técnico sobre la visita.
  * `x_studio_tcnico`: Asignación del responsable del cierre.
  * `x_studio_informe`: Archivo binario Base64 (Informe PDF consolidado).
* **Métodos Específicos a Invocar:**
  * `message_post`: Añadir actualizaciones o adjuntar los PDF generados en el *chatter* de la petición.

---

## 4. Módulo: Mantenimiento (Ubicaciones)
### Modelo: `x_maintenance_location`
**Propósito:** Representar los puntos geográficos o faenas de monitoreo (Proyectos).

* **Operaciones Permitidas:** Búsqueda y Lectura (`search_read`)
* **Campos de Interacción:**
  * `x_name`: Búsqueda por nombre de proyecto y punto concatenados.
  * `id`: Lectura del identificador para relaciones posteriores.

---

## 5. Módulo: Inventario y Logística
### Modelo: `stock.move.line`
**Propósito:** Controlar e identificar equipos que se encuentren en etapa de tránsito logístico (despachados pero no procesados en destino).

* **Operaciones Permitidas:** Búsqueda y Lectura (`search_read`)
* **Campos de Búsqueda (Domain):**
  * `location_usage`: Validar si está en tránsito (`transit`).
  * `location_dest_usage`: Validar si su destino final es cliente (`customer`).
  * `lot_id.name`: Buscar correspondencia por Número de Serie.
  * `state`: Validar que el movimiento siga vivo (ni `done`, ni `cancel`).

---

## 6. Módulo: Documentos Base
### Modelo: `ir.attachment`
**Propósito:** Almacenar de manera centralizada los reportes PDF generados y cualquier evidencia recolectada en terreno.

* **Operaciones Permitidas:** Creación (`create`)
* **Campos de Escritura:**
  * `name`: Nombre del archivo (Ej: "informe_OT-1234_MC.pdf").
  * `datas`: Cadena codificada en Base64 con el contenido del archivo.
  * `res_model`: Modelo al que se atará el adjunto (`maintenance.request`, `x_inbox_integracion`).
  * `res_id`: ID del registro al que se ancla.
  * `mimetype`: Tipo de archivo (`application/pdf`).

---

## 7. Módulo: Productividad y Tareas
### Modelo: `mail.activity`
**Propósito:** Gestionar y completar dinámicamente los "To-Dos" o tareas que el sistema genera automáticamente para los usuarios.

* **Operaciones Permitidas:** Búsqueda, Lectura, Resolución rápida (`search_read`, `action_feedback`)
* **Campos de Búsqueda (Domain):**
  * `res_model`: Filtrar actividades por modelo subyacente (usualmente `maintenance.request`).
  * `res_id`: Filtrar por el ID del ticket de mantenimiento.
* **Campos de Lectura:**
  * `id`: ID de la actividad a cerrar.
* **Métodos Específicos a Invocar:**
  * `action_feedback`: Marcar la actividad en Odoo como Completada, añadiendo el comentario de que la resolución ha sido ejecutada desde la API/IA.

---
> **Nota para el Agente:** Siempre que proceses lotes de datos y debas generar notificaciones, prioriza el uso de `message_post` sobre el registro específico. En caso de no encontrar un equipo (`maintenance.equipment`), delega la alerta usando el Inbox (`x_inbox_integracion`) para intervención humana.
