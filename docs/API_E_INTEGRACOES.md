# API e integrações — ERGO v5

## 1. APIs de leitura com sessão

Exigem autenticação Django e aplicam o escopo autorizado:

| Método | Rota | Conteúdo |
|---|---|---|
| GET | `/upgrades/api/tasks/` | até 100 tarefas visíveis |
| GET | `/upgrades/api/effectiveness/` | série diária agregada |
| GET | `/upgrades/api/recommendations/` | recomendações heurísticas |
| GET | `/upgrades/api/charts/` | dados das visualizações |

`?scope=organization` só é aceito para administrador, superadministrador ou superusuário. Usuário comum recebe escopo pessoal.

Essas APIs não implementam OAuth/JWT. Para integração de terceiros, adicione autenticação apropriada, versionamento, CORS, limites e OpenAPI.

## 2. API de sensores

Rota:

```text
/upgrades/api/sensors/
```

### GET

Aceita:

- sessão Django autenticada; ou
- chave de sensor.

Retorna até 100 leituras do usuário autenticado.

### POST

Exige chave dedicada em um destes cabeçalhos:

```text
X-ERGO-API-Key: ergo_...
```

ou:

```text
Authorization: Bearer ergo_...
```

A isenção de CSRF aplica-se somente a essa rota, e o POST continua protegido pela chave.

## 3. Gerar e revogar chave

Na tela `/upgrades/sensors/`:

1. gere uma chave;
2. copie no momento da exibição;
3. armazene em cofre de segredos;
4. revogue quando houver suspeita ou troca do dispositivo.

O banco guarda prefixo, hash SHA-256, estado e última utilização. A chave original não pode ser recuperada.

## 4. Payload

```json
{
  "captured_at": "2026-08-04T10:30:00-03:00",
  "source": "sala-01",
  "temperature_c": 24.5,
  "humidity_percent": 52.0,
  "noise_db": 61.2,
  "luminosity_lux": 430,
  "air_quality_index": 42,
  "note": "leitura automática"
}
```

Campos ambientais são opcionais, mas valores enviados devem respeitar:

- temperatura: -50 a 70 °C;
- umidade: 0 a 100%;
- ruído: 0 a 200 dB;
- luminosidade: 0 a 200.000 lux;
- AQI: 0 a 500;
- origem: até 120 caracteres;
- observação: até 250 caracteres.

Valor zero é preservado; não é convertido em `null`.

## 5. Respostas

Criado:

```json
{"id": 123, "created": true}
```

Erros comuns:

- `400`: JSON ou campos inválidos;
- `401`: sessão/chave ausente ou inválida;
- `405`: método não permitido.

Erros de formulário são retornados de forma estruturada.

## 6. cURL

```bash
curl -X POST "https://SEU_DOMINIO/upgrades/api/sensors/" \
  -H "Content-Type: application/json" \
  -H "X-ERGO-API-Key: SUA_CHAVE" \
  -d '{"source":"sala-01","temperature_c":24.5,"noise_db":61.2}'
```

## 7. PowerShell

```powershell
$headers = @{ "X-ERGO-API-Key" = "SUA_CHAVE" }
$body = @{
  source = "sala-01"
  temperature_c = 24.5
  noise_db = 61.2
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "https://SEU_DOMINIO/upgrades/api/sensors/" `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

## 8. Boas práticas

- HTTPS;
- chave por usuário/dispositivo conforme política;
- rotação e revogação;
- relógio sincronizado;
- repetição com backoff;
- não enviar dados pessoais em `source`/`note`;
- validar unidade e calibração;
- rate limiting e observabilidade no proxy.
