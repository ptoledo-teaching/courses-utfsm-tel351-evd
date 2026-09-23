# EVD - Arquitecturas event-driven, Amazon SNS y Amazon SQS

Este laboratorio implementa un sistema de distribución y procesamiento de mediciones de la infraestructura de la Holonet. Amazon SNS distribuye eventos hacia una cola Amazon SQS y una suscripción de correo. Una Lambda function procesa las mediciones y una Dead-Letter Queue (DLQ) conserva los mensajes que no logra interpretar.

La infraestructura se configura desde AWS Management Console, con la interfaz en inglés. Para simular los mensajes, se dispone de un generador que permite probar múltiples escenarios, tanto con mensajes individuales como con secuencias.

## Resultados esperados

Al completar el laboratorio, el estudiante podrá:

1. Distinguir recepción, visibilidad y eliminación de mensajes en SQS
2. Distribuir una publicación mediante SNS hacia destinos con responsabilidades diferentes
3. Construir una subscription filter policy a partir de un requisito funcional
4. Integrar una cola SQS con Lambda y observar acumulación y procesamiento de mensajes
5. Interpretar fallas, reintentos y traslado de mensajes hacia una DLQ
6. Distinguir cambios de contrato de mensajes que carecen de información indispensable
7. Adaptar un consumidor manteniendo compatibilidad con los mensajes anteriores
8. Recuperar mensajes mediante redrive sin ocultar errores ni inventar información
9. Delimitar permisos de publicación mediante un role independiente y eliminar los recursos al finalizar su uso

## Preparación previa

- La cuenta AWS personal del estudiante debe estar operativa y disponer de una identidad administrativa con MFA
- Mantenga acceso a una casilla de correo en la que pueda confirmar una suscripción de SNS
- Descargue [el consumidor inicial](assets/lambda_function.py), [la trust policy](assets/tel351-notifier-trust.json) y [los permisos del notificador](assets/tel351-notifier-permissions.json)

## Contexto

La Holonet permite transmitir información y comunicaciones holográficas entre sistemas distantes. En este escenario, su infraestructura incluye repetidores que mantienen los enlaces entre distintos sectores. El equipo de operaciones necesita supervisar esos enlaces para detectar problemas de funcionamiento y contar con información confiable para investigarlos.

Cada repetidor produce mediciones de latencia, expresadas en milisegundos, que permiten observar el tiempo de respuesta de los enlaces. Cuando obtiene una medición, emite un mensaje que identifica al repetidor, el instante de la observación y el valor medido. Cada evento tiene además un identificador que permite reconocer la misma medición a lo largo de su procesamiento, incluso cuando se recibe más de una vez.

Estas mediciones tienen dos destinatarios con responsabilidades diferentes. Un servicio de procesamiento automático debe validar los datos, convertir las mediciones admitidas a una representación común y dejar un registro del resultado. Por otra parte, un operador debe recibir por correo solamente los eventos seleccionados para notificación. El mensaje indica si corresponde enviar ese correo; esta selección es independiente de que el procesamiento automático haya terminado. Recibir una notificación significa que se publicó un evento seleccionado, no que su medición ya fue validada.

El volumen de mensajes no es constante: pueden llegar mediciones aisladas o ráfagas de varios repetidores. Además, el servicio de procesamiento puede detenerse temporalmente por una falla o una actualización. La recepción de mediciones y la distribución de notificaciones deben continuar durante esa interrupción. Por ello, las mediciones pendientes se conservan en una cola hasta que el servicio pueda atenderlas, sin exigir que los repetidores esperen el resultado del procesamiento para seguir enviando información.

Otro problema es la evolución del formato de los mensajes. El contrato de un mensaje define cómo se organizan sus datos, qué información es obligatoria y cómo debe interpretarse. Una actualización del software de un repetidor puede introducir una nueva versión de ese contrato: la medición sigue existiendo, pero su valor o su unidad aparecen organizados de otra manera. Como los repetidores no se actualizan simultáneamente, el sistema puede recibir mensajes de distintas versiones. El procesador disponible reconoce inicialmente una sola versión y rechaza las que todavía no sabe interpretar.

También pueden llegar mensajes incompletos, por ejemplo, sin el valor de la latencia. Este caso es distinto de un cambio de formato: adaptar el procesador permite recuperar una medición que está presente, pero no reconstruir un dato que nunca llegó. Asignar un valor por omisión, como cero, produciría información falsa sobre el funcionamiento del enlace.

Cuando falla el procesamiento, el mensaje puede volver a intentarse. Si el rechazo se repite, debe separarse del flujo habitual y conservarse para investigación en una cola de mensajes fallidos, o Dead-Letter Queue (DLQ). El equipo de operaciones puede examinar estos casos, identificar su causa y solicitar una corrección del procesador cuando corresponda. Tras incorporar compatibilidad con un formato nuevo, los mensajes afectados pueden volver a la cola de procesamiento. Los que carecen de información indispensable deben seguir identificados como fallidos. El propósito es recuperar mediciones válidas sin ocultar problemas de calidad de los datos.

Se disponibiliza un generador de eventos para simular las mediciones de los repetidores, las variaciones de tráfico y los problemas de formato o de información faltante. En este laboratorio se utilizará Amazon SNS para distribuir cada publicación hacia la cola SQS y, cuando el filtro de la suscripción lo autorice, hacia el correo del operador. Una Lambda function procesa los mensajes de SQS; aquellos que fallan reiteradamente se trasladan a la DLQ.

## Interacción y comprobación

### Uso del generador

El [generador de eventos](https://lab05.shareddomain.link) permite publicar mensajes de prueba en el topic SNS creado en la cuenta del estudiante. Para utilizarlo, deben estar creados el topic y el role `TEL351-Notifier`, cuya configuración se describe en la actividad. El sitio genera el tráfico; la comprobación de su distribución y procesamiento se realiza en los servicios AWS y en la casilla de correo del estudiante.

El estudiante debe ingresar el ARN del topic SNS y el RUT normalizado, sin puntos ni guion y con `k` minúscula. El RUT debe coincidir con el External ID configurado en el role. Luego debe seleccionar un escenario y presionar **Iniciar**. Durante el envío, el botón cambia a **Detener**, que permite interrumpir la generación sin eliminar los mensajes que ya fueron publicados.

Cerrar el navegador no detiene una secuencia: el generador continúa hasta completar su duración máxima. Al volver al sitio e ingresar el mismo ARN y RUT, se recupera automáticamente su estado. Solo puede existir una ejecución activa por cuenta.

### Escenarios de prueba

- **Mensaje ejemplo:** publica una medición compatible con el consumidor inicial, sin solicitar correo. Permite comprobar el recorrido desde SNS hasta SQS y, una vez habilitada la Lambda, su procesamiento
- **Mensaje ejemplo con notificación:** publica una medición compatible que también solicita correo. Permite comprobar que SNS distribuye el evento tanto a la cola como a la suscripción de correo
- **Tráfico ejemplo:** publica una secuencia de mediciones compatibles. Permite observar cómo se acumulan y procesan los mensajes cuando cambia la cantidad de eventos que llegan al sistema
- **Tráfico ejemplo con errores:** publica una secuencia que combina mediciones compatibles, mediciones con un formato nuevo y mensajes incompletos. Permite investigar los rechazos del consumidor, los reintentos y la llegada de mensajes a la DLQ

Los dos escenarios de tráfico duran **dos minutos**: generan 1 mensaje por segundo durante los primeros 30 segundos, 5 mensajes por segundo durante los 30 siguientes y 1 mensaje por segundo durante el último minuto. Una secuencia completa contempla hasta 240 mensajes; puede enviar menos si se detiene o se interrumpe. Solo dos mensajes de la secuencia solicitan envío de correo.

### Cómo interpretar los resultados

La información debe comprobarse en distintos puntos del recorrido:

- **Sitio del generador:** muestra cuántas publicaciones fueron aceptadas por SNS. Una ejecución finalizada indica que terminó el envío, no que las mediciones ya fueron procesadas
- **SQS:** permite observar mensajes pendientes en la cola principal y mensajes trasladados a la DLQ después de fallar reiteradamente. Una cola principal vacía también puede indicar que Lambda ya procesó sus mensajes
- **CloudWatch Logs:** permite comprobar qué mediciones procesó la Lambda y cuáles rechazó, junto con el motivo del rechazo
- **Casilla de correo:** permite comprobar que llegaron las notificaciones solicitadas y que los eventos sin notificación fueron excluidos por el filtro

El estudiante puede utilizar `eventId` para relacionar una misma medición entre el mensaje, los logs y el correo. Los reintentos y las posibles entregas duplicadas de SQS pueden producir varios registros para un solo evento; por ello, la cantidad de líneas de logs no tiene que coincidir con el contador de publicaciones. Los contadores y las métricas de AWS también pueden actualizarse con retraso.

## Actividad

### 1. Establecer la identidad y la Región

1. Ingrese a AWS Management Console con la identidad administrativa de uso regular del estudiante, no con el usuario root
2. Seleccione **South America (São Paulo)** y compruebe `sa-east-1`

Todos los recursos regionales se crean en `sa-east-1`. IAM es global y no requiere cambiar la Región. No elimine ni modifique recursos de otros laboratorios.

### 2. Crear el topic SNS y suscribir el correo

#### 2.1 Crear el topic

1. Abra **SNS → Topics → Create topic**
2. Seleccione **Standard**, use el nombre `tel351-evd` y cree el topic
3. Copie el ARN del topic; se utilizará en los permisos del role y en el generador

#### 2.2 Suscribir el correo y construir el filtro

1. En el topic, seleccione **Create subscription**
2. Use **Protocol: Email** y la dirección de correo personal del estudiante como **Endpoint**
3. En **Subscription filter policy**, seleccione el alcance **Message body**
4. Escriba un filtro que cumpla el siguiente requisito: **entregar solamente mensajes cuyo campo `notification` tenga el valor `email`**
5. Cree la suscripción. SNS enviará un correo de confirmación a la dirección indicada como **Endpoint**
6. El estudiante debe abrir ese correo y seleccionar el enlace **Confirm subscription**. Si no aparece en la bandeja de entrada, debe revisar la carpeta de correo no deseado
7. Actualice la vista de suscripciones en SNS y compruebe que la suscripción dejó de estar en estado **Pending confirmation** antes de probar las notificaciones

Crear la suscripción en la consola no basta para habilitar la entrega: mientras el estudiante no la confirme desde el correo recibido, SNS no enviará las notificaciones a esa dirección. El correo de confirmación es distinto de los mensajes que posteriormente enviará el sistema.

Los cambios de filtros pueden tardar hasta 15 minutos en propagarse. Continúe con las actividades siguientes antes de probar tráfico sostenido. No publique una ráfaga mientras la suscripción de correo esté sin filtro o este no haya sido comprobado. Esta suscripción no requiere SES ni salir del SMS sandbox.

### 3. Autorizar al generador mediante un role independiente

1. Abra **IAM → Roles → Create role → Custom trust policy**
2. Utilice el contenido de [`tel351-notifier-trust.json`](assets/tel351-notifier-trust.json) y reemplace `REEMPLAZAR_RUT` por el RUT normalizado del estudiante
3. Mantenga el principal del generador indicado en el archivo
4. Continúe sin asociar managed policies y cree el role con el nombre exacto `TEL351-Notifier`
5. En el role, seleccione **Permissions → Add permissions → Create inline policy → JSON**
6. Utilice [`tel351-notifier-permissions.json`](assets/tel351-notifier-permissions.json), reemplace `REEMPLAZAR_ARN_TOPIC` en el campo `Resource` por el ARN completo del topic SNS copiado al crearlo y guarde como `tel351-evd-send`
7. Confirme que el role solo permite `sns:Publish` sobre el topic del laboratorio

La trust policy permite que el role del generador asuma este role cuando el External ID coincide con el RUT del estudiante. La permissions policy autoriza la publicación en SNS. No edite ni agregue estos permisos a `TEL351-Evaluator`.

### 4. Comprobar la publicación en SNS y la entrega de correo

1. En el generador, ingrese el ARN del topic SNS `tel351-evd` y el RUT normalizado del estudiante
2. Seleccione **Mensaje ejemplo con notificación** y presione **Iniciar**
3. Compruebe que el sitio informa una publicación confirmada y que el correo del estudiante recibe la notificación
4. Abra el contenido del correo y reconozca `eventId`, `source`, `latencyMs` y la indicación `notification: email`. Este mensaje es distinto del correo de confirmación de la suscripción
5. Ejecute **Mensaje ejemplo** y compruebe que el sitio confirma otra publicación, pero esta no genera correo porque contiene `notification: none`

La publicación confirmada permite comprobar que el generador pudo asumir `TEL351-Notifier` y utilizar el permiso de publicación. La llegada del correo permite comprobar la entrega desde SNS a la suscripción confirmada. Estas comprobaciones solo requieren el topic, la suscripción de correo y el role.

Si el generador informa un error de acceso, se deben revisar el ARN del topic, la trust policy, el RUT como External ID y el permiso `sns:Publish`. Si SNS acepta la publicación, pero no llega el correo esperado, se deben revisar la confirmación de la suscripción, el filtro y la carpeta de correo no deseado. Si llegan correos de ambos escenarios, se debe revisar el filtro y su alcance. Los cambios del filtro pueden tardar en propagarse: una ausencia momentánea de correo no basta para confirmar su funcionamiento. Las pruebas deben realizarse con mensajes individuales antes de iniciar una ráfaga.

### 5. Incorporar SQS y comprobar la recepción de mensajes

#### 5.1 Crear la cola de trabajo y su DLQ

1. Abra **SQS → Queues → Create queue**
2. Cree una cola **Standard** llamada `tel351-evd-dlq`
3. Mantenga el cifrado administrado por SQS (**SSE-SQS**) y las demás opciones por omisión
4. Cree otra cola **Standard** llamada `tel351-evd`
5. En **Configuration**, configure **Visibility timeout** en `20` segundos y **Receive message wait time** en `10` segundos
6. En **Dead-letter queue**, habilite la opción, seleccione `tel351-evd-dlq` y establezca **Maximum receives** en `3`
7. Mantenga **SSE-SQS** y cree la cola
8. Copie el ARN de la cola `tel351-evd`; se utilizará para restringir los permisos del consumidor Lambda

La cola principal conserva el trabajo pendiente. La DLQ conserva mensajes recibidos reiteradamente sin que el consumidor confirme su procesamiento. En esta integración, confirmar el procesamiento permitirá eliminar el mensaje de la cola principal.

#### 5.2 Suscribir la cola al topic SNS

1. En SQS, seleccione la cola `tel351-evd` y utilice **Actions → Subscribe to Amazon SNS topic**
2. Seleccione el topic `tel351-evd` creado anteriormente y confirme la suscripción
3. Revise **Access policy** de la cola: debe autorizar a SNS para realizar `sqs:SendMessage` desde el topic correspondiente
4. En SNS, abra la suscripción de tipo **Amazon SQS** y seleccione **Edit**
5. Habilite **Raw message delivery** y guarde los cambios; no agregue un filtro a esta suscripción

El topic tiene ahora dos suscripciones: una de correo que selecciona eventos mediante un filtro y otra de SQS que recibe todas las mediciones. La entrega raw permite que el body recibido desde SQS contenga directamente el JSON publicado, sin la envoltura adicional de SNS. El consumidor inicial utiliza ese formato.

La entrega desde SNS hacia SQS se autoriza mediante la access policy de la cola. El role `TEL351-Notifier` mantiene únicamente el permiso de publicación en el topic; no requiere permisos adicionales sobre SQS.

#### 5.3 Observar recepción, visibilidad y eliminación

1. En el generador, ingrese el ARN del topic **SNS** `tel351-evd` y el RUT normalizado del estudiante
2. Seleccione **Mensaje ejemplo** y presione **Iniciar** para publicar un nuevo mensaje después de suscribir la cola
3. Espere hasta que el sitio confirme la publicación en SNS y el mensaje llegue a la cola suscrita
4. En la cola, abra **Send and receive messages → Poll for messages**
5. Abra el mensaje y reconozca `eventId`, `runId`, `schemaVersion`, `source` y `latencyMs`
6. Detenga el polling y no elimine el mensaje
7. Antes de que terminen los 20 segundos de visibilidad, compruebe que una nueva recepción no lo recupera normalmente; detenga nuevamente el polling
8. Espere a que venza la visibilidad y consulte otra vez. Compare el `eventId` y el contador de recepciones
9. Seleccione el mensaje y utilice **Delete** para eliminarlo

La recepción no elimina el mensaje. Su reaparición permite que otro consumidor reintente el trabajo si el primero falla. No mantenga el polling abierto innecesariamente: las recepciones desde la consola también cuentan y podrían trasladar el mensaje a la DLQ después de varios intentos.

### 6. Observar la acumulación de mensajes

Antes de generar tráfico sostenido, el filtro de correo debe haber superado las pruebas con mensajes individuales del punto 4.

1. En el generador, mantenga el ARN del topic SNS y el RUT del estudiante e inicie **Tráfico ejemplo**
2. Observe las etapas de la secuencia y las publicaciones confirmadas en el sitio. En SQS, compruebe que aumenta la cantidad de mensajes pendientes en la cola `tel351-evd`
3. No utilice **Poll for messages** durante esta observación: la consulta desde la consola recibiría mensajes y modificaría su visibilidad
4. Compruebe que las notificaciones seleccionadas llegan al correo del estudiante mientras los mensajes permanecen pendientes en la cola
5. Espere a que termine la secuencia y observe la cantidad de mensajes acumulados. Mantenga disponible el identificador de ejecución mostrado por el generador para reconocerlos posteriormente en los logs
6. Conserve los mensajes en la cola, sin eliminarlos ni purgarla

SNS distribuye los eventos y entrega las notificaciones aunque todavía no exista un consumidor conectado a SQS. La cola conserva las mediciones pendientes hasta que se incorpore el procesamiento automático.

### 7. Crear el consumidor y procesar los mensajes acumulados

#### 7.1 Crear y configurar la Lambda function

1. Abra **Lambda → Functions → Create function → Author from scratch**
2. Use el nombre `tel351-evd-consumer` y runtime **Python 3.14**
3. Mantenga la creación de un execution role nuevo con permisos básicos de Lambda
4. Reemplace el código de `lambda_function.py` por el [consumidor inicial proporcionado](assets/lambda_function.py) y seleccione **Deploy**
5. En **Configuration → General configuration**, confirme un **Timeout** de `3` segundos
6. Abra **Configuration → Permissions** y siga el enlace al execution role
7. Cree una inline policy mediante el editor visual con las acciones SQS `ReceiveMessage`, `DeleteMessage` y `GetQueueAttributes`, restringidas al ARN de `tel351-evd`
8. Mantenga los permisos básicos de CloudWatch Logs y guarde la policy como `tel351-evd-consume`

#### 7.2 Asociar la cola y comprobar el procesamiento

1. En la función, seleccione **Add trigger → SQS**
2. Seleccione `tel351-evd` y configure **Batch size: 1** y **Batch window: 0**, si se muestra este último campo
3. No configure filtros de eventos ni habilite **Provisioned Mode**
4. Agregue el trigger habilitado y espere a que figure como **Enabled**
5. Abra **Monitor → View CloudWatch logs** y localice registros con `result` igual a `PROCESSED`, correspondientes a los mensajes acumulados en el punto 6
6. Compruebe que el campo `runId` coincide con el identificador de la secuencia ejecutada y reconozca el `eventId` y la latencia de las mediciones procesadas
7. En SQS, compruebe que disminuye la cantidad de mensajes pendientes hasta que se completa el procesamiento. No utilice **Poll for messages** mientras Lambda consume la cola

El procesamiento comienza al habilitar el trigger y puede completar rápidamente el trabajo acumulado. Aunque al volver a SQS la cola ya esté vacía, los registros de CloudWatch permiten comprobar qué mediciones fueron procesadas. Los contadores de SQS pueden actualizarse con retraso.

El servicio Lambda consulta SQS mediante long polling. La función recibe el mensaje y, si termina sin excepción, la integración lo elimina. No debe añadir una llamada a `DeleteMessage` al código. El lote de un mensaje permite observar las fallas individualmente.

### 8. Investigar mensajes rechazados

1. Con el trigger habilitado y el destino SNS, ejecute **Tráfico ejemplo con errores**
2. En CloudWatch, busque registros con `result` igual a `REJECTED`
3. Reconozca el motivo, el contenido del mensaje y las recepciones sucesivas del mismo evento
4. Espere a que los mensajes alcancen la DLQ. No todos aparecerán inmediatamente después de terminar el generador
5. En `tel351-evd-dlq`, utilice **Send and receive messages → Poll for messages** para inspeccionar algunos mensajes; no los elimine
6. Compare al menos un mensaje de cada tipo de rechazo con uno procesado correctamente
7. Detenga el polling antes de continuar

Clasifique los casos a partir de sus datos: ¿la medición existe en otra estructura?, ¿se indica su unidad?, ¿falta completamente?, ¿el identificador corresponde a un mensaje que ya observó en los logs?

SNS y SQS transportan estos mensajes porque su JSON es válido. El rechazo corresponde al contrato de la aplicación y se produce dentro de Lambda. La redrive policy de SQS cuenta recepciones; no interpreta por sí misma el significado del error.

### 9. Adaptar el consumidor sin ocultar errores

Modifique `normalize_message` para cumplir simultáneamente estos requisitos:

- Seguir procesando el contrato original sin cambiar su significado
- Admitir el nuevo formato observado cuando contiene una medición completa y una unidad compatible
- Producir la misma representación interna, con `latencyMs` como número finito no negativo
- Mantener `eventId`, `runId`, `source` y `observedAt`
- Rechazar versiones desconocidas, unidades no admitidas y mensajes sin la medición indispensable

No asigne cero a una medición ausente ni transforme una excepción en una respuesta HTTP de error. En esta integración, retornar `{"statusCode": 500}` sigue siendo una ejecución exitosa si la función no falla, y el mensaje puede eliminarse sin haber sido procesado.

1. Construya tests de Lambda a partir de los mensajes inspeccionados y de la estructura de evento incluida en el apéndice
2. Compruebe un mensaje original válido, uno válido del formato nuevo y uno incompleto
3. Confirme que solo los dos primeros terminan correctamente
4. Seleccione **Deploy** para publicar los cambios de código

### 10. Recuperar y comprobar

1. Confirme que el trigger está habilitado y que el generador no mantiene una ejecución activa
2. Espere a que vuelvan a ser visibles los mensajes recibidos manualmente desde la DLQ
3. En `tel351-evd-dlq`, seleccione **Start DLQ redrive**
4. Elija **Redrive to a custom destination** y seleccione explícitamente la cola `tel351-evd`; no dependa de la detección automática del origen
5. Use una velocidad personalizada de `1` mensaje/s e inicie la tarea
6. En CloudWatch, confirme que los mensajes recuperables ahora producen `PROCESSED` y conservan su `eventId`
7. Compruebe que los mensajes incompletos siguen produciendo `REJECTED` y, tras los nuevos intentos, regresan a la DLQ
8. Envíe nuevamente un mensaje del contrato original y confirme que continúa funcionando

El redrive puede cambiar identificadores del transporte SQS, pero no debe cambiar el `eventId` contenido en el mensaje. La DLQ no necesariamente quedará vacía: los mensajes sin información suficiente deben conservarse para investigación hasta la limpieza. No repita el redrive indefinidamente ni invente datos para obtener una cola vacía.

Al finalizar, debería poder reconocer una publicación aceptada, un mensaje pendiente, una ejecución fallida y una medición procesada como hechos diferentes. No hay una evaluación adicional ni debe entregar un documento.

## Limpieza posterior al laboratorio

Realice esta limpieza fuera del bloque, después de completar las comprobaciones:

1. Detenga cualquier ejecución del generador y confirme su término
2. Deshabilite y elimine el trigger SQS de `tel351-evd-consumer`; espere a que se retire la asociación
3. Elimine la Lambda function `tel351-evd-consumer`
4. Elimine las suscripciones SQS y Email del topic y luego el topic `tel351-evd`
5. Elimine las colas `tel351-evd` y `tel351-evd-dlq`; esto elimina también sus mensajes pendientes
6. Elimine el log group `/aws/lambda/tel351-evd-consumer`
7. Elimine el execution role creado exclusivamente para esa Lambda y el role `TEL351-Notifier`, con sus inline policies

No elimine la identidad administrativa del estudiante ni `TEL351-Evaluator`. No es necesario modificar registros DNS: el sitio del generador se administra de forma independiente. No elimine recursos compartidos con otras actividades.

## Apéndice: referencias para inspección y adaptación

### Contrato inicial

Una medición válida de versión 1 tiene esta forma:

```json
{
  "eventId": "ejecucion:0001",
  "runId": "ejecucion",
  "schemaVersion": 1,
  "observedAt": "2026-09-22T16:00:00+00:00",
  "source": "holonet-relay-01",
  "kind": "link.measurement",
  "notification": "none",
  "latencyMs": 82
}
```

`eventId` identifica la medición y `runId` agrupa los mensajes de una ejecución del generador. `notification` selecciona notificaciones y no determina la validez de la medición. `latencyMs` expresa milisegundos: su ausencia no significa una latencia de cero.

### Evento de prueba para Lambda

Lambda recibe un conjunto `Records`. El campo `body` de cada registro es un string que contiene el JSON publicado. Para probar una medición, sustituya el contenido de `body`, conservando el escape de las comillas:

```json
{
  "Records": [{
    "messageId": "prueba-local",
    "attributes": {"ApproximateReceiveCount": "1"},
    "body": "{\"eventId\":\"prueba:1\",\"runId\":\"prueba\",\"schemaVersion\":1,\"observedAt\":\"2026-09-22T16:00:00+00:00\",\"source\":\"holonet-relay-01\",\"kind\":\"link.measurement\",\"notification\":\"none\",\"latencyMs\":82}"
  }]
}
```

El botón **Test** no recibe desde SQS, no elimina mensajes ni modifica la DLQ. Solo permite comprobar el comportamiento del código con una entrada construida manualmente.

### Herramientas de Python

`json.loads` convierte un string JSON en un objeto Python. `message.get("campo")` retorna su valor o `None` si está ausente; si obtiene otro diccionario, puede inspeccionar sus propiedades. `isinstance(valor, dict)` permite reconocer un objeto, mientras `type(valor) in (int, float)` acepta números y evita tratar `True` o `False` como mediciones. `raise ValueError("motivo")` interrumpe el procesamiento e informa el rechazo.

La normalización transforma representaciones compatibles en una estructura interna común. No debe completar información desconocida ni eliminar las validaciones necesarias para interpretar la medición.
