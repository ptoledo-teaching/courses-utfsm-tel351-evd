"""Consumidor inicial de mediciones de la Holonet: contrato versión 1."""
import json
import math


def normalize_message(message):
    if not isinstance(message, dict):
        raise ValueError('El mensaje debe ser un objeto JSON')
    for field in ('eventId', 'runId', 'observedAt', 'source'):
        if not isinstance(message.get(field), str) or not message[field].strip():
            raise ValueError(f'Falta un campo obligatorio de texto: {field}')
    if message.get('kind') != 'link.measurement':
        raise ValueError('Tipo de evento no soportado')
    version = message.get('schemaVersion')
    if type(version) is not int or version != 1:
        raise ValueError(f'Versión de contrato no soportada: {version}')
    latency = message.get('latencyMs')
    if type(latency) not in (int, float) or not math.isfinite(latency) or latency < 0:
        raise ValueError('latencyMs debe ser un número finito no negativo')
    return {
        'eventId': message['eventId'], 'runId': message['runId'],
        'source': message['source'], 'observedAt': message['observedAt'], 'latencyMs': latency,
    }


def lambda_handler(event, context):
    for record in event['Records']:
        body = record['body']
        try:
            normalized = normalize_message(json.loads(body))
        except (ValueError, TypeError, KeyError) as error:
            print(json.dumps({
                'result': 'REJECTED', 'sqsMessageId': record['messageId'],
                'receiveCount': record.get('attributes', {}).get('ApproximateReceiveCount'),
                'reason': str(error), 'body': body,
            }, ensure_ascii=False))
            raise
        print(json.dumps({'result': 'PROCESSED', **normalized}, ensure_ascii=False))
    # SQS no interpreta statusCode HTTP. Lambda confirma éxito si no hay excepción.
    return {'processed': len(event['Records'])}
