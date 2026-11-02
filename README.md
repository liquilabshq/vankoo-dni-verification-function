# vankoo-dni-verification-function

Función serverless (Azure Functions, Python 3.12) que verifica el DNI de un inversor: comprueba que el
DNI existe y que los nombres declarados coinciden con los registrados. Lo llama `vankoo-profile-service`
cuando el inversor completa su perfil. Es el entregable **3.5 Funciones serverless**; el documento de
entrega está en `vankoo-infra/docs/funciones-serverless.md`.

> **Fuente de datos.** Consulta [eldni.com](https://eldni.com/) reproduciendo su formulario público. No es el
> servicio oficial de RENIEC (el propio sitio avisa de que sus datos pueden contener errores). Por eso la
> fuente está detrás de un puerto (`DniRegistry`) y hay un proveedor `fake` para demos y pruebas.

## Contrato

`POST /api/verify-dni` — header `x-functions-key` (clave de función). `GET /api/health` es anónimo.

```jsonc
// Solicitud
{ "investorId": "uuid (opcional)", "dni": "12345678", "firstName": "Juan Carlos", "lastName": "Perez Gomez" }

// 200
{
  "investorId": "uuid",
  "dni": "12345678",
  "status": "VERIFIED",            // VERIFIED | NAME_MISMATCH | NOT_FOUND
  "registeredName": { "firstNames": "JUAN CARLOS", "paternalSurname": "PEREZ", "maternalSurname": "GOMEZ" },
  "source": "eldni.com",
  "checkedAt": "2026-11-01T12:00:00+00:00"
}
```

| Código | Cuándo |
|---|---|
| 200 | Hay veredicto (`VERIFIED`, `NAME_MISMATCH` o `NOT_FOUND`) |
| 400 | JSON inválido, faltan `firstName`/`lastName` o el DNI no tiene 8 dígitos |
| 401 | Falta la clave de función (solo en Azure) |
| 502 | La fuente no respondió o respondió algo irreconocible: no hay veredicto, reintentar luego |

Regla de coincidencia de nombres: se ignoran mayúsculas, tildes y orden; se aceptan declaraciones parciales
(solo el primer nombre, solo el apellido paterno) pero toda palabra declarada debe existir en el registro y el
apellido paterno debe estar completo.

La función **no guarda nada** y **nunca registra el DNI completo** (`1234****`): es dato personal (Ley 29733).

## Configuración

| Variable | Default | Descripción |
|---|---|---|
| `DNI_PROVIDER` | `eldni` | `eldni` (web real) o `fake` (datos de demostración, sin internet) |
| `ELDNI_BASE_URL` | `https://eldni.com` | |
| `ELDNI_TIMEOUT_SECONDS` | `8` | Tiempo máximo por petición |
| `ELDNI_RETRIES` | `1` | Reintentos ante fallo (cada uno abre una sesión nueva) |

Con `DNI_PROVIDER=fake`: `12345678` → JUAN CARLOS PEREZ GOMEZ, `87654321` → MARIA ELENA QUISPE HUAMAN,
`00000503` → simula la fuente caída (502); cualquier otro → `NOT_FOUND`.

## Probar en local con VS Code

Requisitos (una sola vez):

```bash
winget install Microsoft.Azure.FunctionsCoreTools   # comando `func` (v4)
winget install astral-sh.uv
uv python install 3.12                               # Azure Functions no soporta 3.14
```

Extensiones de VS Code: **Azure Functions** (`ms-azuretools.vscode-azurefunctions`), Python y, para
`requests.http`, REST Client. VS Code las recomienda al abrir la carpeta (`.vscode/extensions.json`).

```bash
uv sync                                              # crea .venv con Python 3.12
cp local.settings.json.example local.settings.json   # DNI_PROVIDER=fake para empezar
```

1. Abre la carpeta en VS Code y pulsa **F5** (o ejecuta `func start` dentro del `.venv`).
2. La función queda en `http://localhost:7071/api/verify-dni`. En local no pide clave.
3. Abre `requests.http` y pulsa *Send Request* sobre cada caso (verificado, no coincide, no existe, DNI inválido, fuente caída).
4. Para probar contra eldni.com de verdad, pon `"DNI_PROVIDER": "eldni"` en `local.settings.json` y reinicia.
   Funciona desde Perú; **desde Azure (Central US) eldni.com responde 404**, por lo que el Function App desplegado usa
   `DNI_PROVIDER=fake` (ver `vankoo-infra/docs/funciones-serverless.md`, «Limitaciones conocidas»).

Integración con profile-service: en su `.env` pon `DNI_VERIFICATION_ENABLED=true` y
`DNI_VERIFICATION_URL=http://localhost:7071/api/verify-dni` (si profile corre en Docker:
`http://host.docker.internal:7071/api/verify-dni`). Al completar el perfil de un inversor
(`PATCH /api/v1/investors/:id/profile`) su `kycStatus` pasa a `VERIFIED` o `REJECTED` unos segundos después.

## Pruebas y calidad

```bash
uv run pytest                 # unitarias, sin red
uv run pytest -m live         # humo contra eldni.com de verdad (a demanda; no corre en CI)
uv run ruff check .
uv run mypy .                 # strict
```

## Despliegue

- **CI** (`.github/workflows/ci.yml`): ruff, mypy y pytest en cada push/PR a `main` y `develop`.
- **CD** (`.github/workflows/deploy.yml`): al fusionar en `develop` corre las pruebas, entra en Azure con OIDC, publica en
  el Function App con `Azure/functions-action` (plan Flex Consumption, build remoto) y hace un `GET /api/health`.
- **Infraestructura**: capa `functions` de Terraform en `vankoo-infra/terraform/functions`.

Configuración del repositorio en GitHub (Settings → Secrets and variables → Actions):

| Nombre | Tipo | Valor |
|---|---|---|
| `AZURE_FUNCTIONAPP_NAME` | Variable | `terraform output -raw function_app_name` (capa `functions`) |
| `AZURE_CLIENT_ID` | Secreto | `az identity show -g liquilabs-vankoo -n vankoo-github-ci --query clientId -o tsv` |
| `AZURE_TENANT_ID` | Secreto | `az account show --query tenantId -o tsv` |
| `AZURE_SUBSCRIPTION_ID` | Secreto | `az account show --query id -o tsv` (la suscripción que contiene `liquilabs-vankoo`) |

Y un *environment* `development` en el repositorio (lo usa `deploy.yml`). Además, quien administre la suscripción debe
crear en la identidad `vankoo-github-ci` una credencial federada con el sujeto
`repo:liquilabshq@<id-org>/vankoo-dni-verification-function@<id-repo>:environment:development` y darle el rol
Contributor sobre el Function App (los ids: `gh api orgs/liquilabshq --jq .id` y
`gh api repos/liquilabshq/vankoo-dni-verification-function --jq .id`). La clave que profile envía en
`x-functions-key`: `az functionapp keys list -g liquilabs-vankoo -n <app> --query functionKeys.default -o tsv`.

## Estructura

```
function_app.py                      # triggers: solo cableado
dni_verification/
  domain/          DniNumber, modelos, name_matcher
  application/     VerifyDniService + puerto DniRegistry
  infrastructure/  eldni_registry (scraper), fake_registry, settings
  interfaces/      http (handlers), composition (elige el proveedor)
tests/             unit/ por capa + fixtures/ HTML
```

Convenciones del equipo: código en inglés, docs en español, Conventional Commits, ramas `feature/*` hacia `develop`.
