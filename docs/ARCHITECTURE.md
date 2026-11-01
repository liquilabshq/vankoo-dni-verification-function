# Arquitectura

## Flujo

```
Inversor ──PATCH /investors/:id/profile──▶ profile-service (NestJS)
                                              │ 1. guarda el perfil (kycStatus = PENDING) y responde
                                              │ 2. en segundo plano:
                                              ▼
                              POST /api/verify-dni  (x-functions-key)
                                              │
                              vankoo-dni-verification-function (Azure Functions, HTTP trigger)
                                              │ GET  eldni.com  → token CSRF + cookie de sesión
                                              │ POST eldni.com/pe/buscar-datos-por-dni
                                              ▼
                              { status: VERIFIED | NAME_MISMATCH | NOT_FOUND }
                                              │
                                              ▼
profile-service aplica el veredicto con los mismos comandos del flujo manual:
   VERIFIED → verifyKyc · NAME_MISMATCH / NOT_FOUND → rejectKyc(motivo)
   sin veredicto (502, timeout, función apagada) → queda PENDING para revisión manual
```

## Decisiones

- **Profile decide, la función solo informa.** Es la regla del proyecto ("Risk recomienda, Profile decide y
  guarda"): la función es *stateless*, no conoce al inversor ni escribe en ninguna base de datos. Por eso no
  hace falta autenticarla contra profile ni exponer un callback.
- **HTTP síncrono entre profile y la función.** Más simple de probar en local que un evento Kafka (el trigger de
  Kafka exige plan Premium o Event Hubs en Azure). profile no espera la respuesta para responder al inversor.
- **Un puerto, dos adaptadores.** `DniRegistry` tiene `EldniRegistry` (scraper) y `FakeDniRegistry` (demo/tests).
  Si eldni.com cambia o cae, se sustituye el adaptador sin tocar dominio ni triggers.
- **Fallar hacia revisión manual.** Cualquier respuesta no confiable (HTML irreconocible, DNI distinto al pedido,
  419, timeout) es `RegistryUnavailableError` → 502. Nunca se convierte en `NOT_FOUND`, que provocaría un rechazo.
- **Capas** (como risk-service): `domain` y `application` no importan `azure.functions` ni `httpx`; `function_app.py`
  solo cablea triggers.

## Scraping de eldni.com

El sitio es una aplicación Laravel. El formulario `#buscar-datos-por-dni` envía `POST /pe/buscar-datos-por-dni`
(`multipart/form-data`) con `_token` (CSRF, incrustado en el HTML) y `dni`, junto con la cookie de sesión. No hay
captcha. La respuesta trae una tabla `DNI | Nombres | Apellido Paterno | Apellido Materno`. Si el DNI no existe, la fila
viene vacía **y** la página muestra «No se encontraron datos…» (`.text-error`). Solo con ese aviso explícito se responde
`NOT_FOUND`: una tabla vacía a secas (la página de inicio también la tiene, y es lo que vuelve si el formulario se
rechaza en silencio) cuenta como fuente no disponible, para no rechazar a un inversor válido por un fallo del sitio.

Riesgos conocidos: no es la fuente oficial de RENIEC, el HTML puede cambiar y el sitio puede limitar el tráfico. El
parser exige la forma exacta de la tabla y que el DNI devuelto sea el consultado; si no, falla en lugar de adivinar.
`pytest -m live` sirve de alarma temprana si el sitio cambia. Los fixtures de `tests/fixtures/` son respuestas reales
con los datos personales sustituidos por datos inventados.
