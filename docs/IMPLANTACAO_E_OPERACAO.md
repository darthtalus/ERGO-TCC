# Implantação e operação — ERGO v5

## 1. Arquitetura recomendada

- proxy reverso HTTPS;
- Gunicorn/WSGI;
- aplicação Django sem privilégios administrativos do sistema;
- MySQL/MariaDB separado;
- `STATIC_ROOT` servido pelo proxy/CDN;
- `PRIVATE_MEDIA_ROOT` fora de qualquer rota pública;
- backup de banco e arquivos privados no mesmo ponto lógico.

## 2. Variáveis essenciais

```text
SECRET_KEY
DEBUG=False
ALLOWED_HOSTS
CSRF_TRUSTED_ORIGINS
DATABASE_URL
PRIVATE_MEDIA_ROOT
PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES=False
```

Não versione `.env`.

## 3. Preparação

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check --deploy
```

Execute também a suíte de validação antes de promover.

## 4. Servidor

Exemplo:

```bash
gunicorn ergo.wsgi:application --bind 127.0.0.1:8000 --workers 3 --timeout 120
```

Dimensione workers com base em memória, carga, PDF e gráficos. Relatórios podem consumir CPU/memória.

## 5. Recorrência

Agende:

```bash
python manage.py generate_recurring_tasks
```

Use exclusão mútua no agendador. O banco também possui idempotência por regra/data, mas não substitui monitoramento.

## 6. Arquivos privados

- não use alias público para `PRIVATE_MEDIA_ROOT`;
- permita download somente pela view autenticada;
- bloqueie execução;
- aplique quotas, antivírus e retenção;
- teste restauração.

## 7. Banco

- usuário com privilégios mínimos;
- charset/collation compatíveis;
- conexões monitoradas;
- backup consistente;
- migrações revisadas com `--plan`;
- evitar alterações manuais em estados/avaliações.

## 8. Logs e observabilidade

Monitore:

- 4xx/5xx;
- falhas de login/Axes;
- erros de migração;
- geração de recorrência;
- POST de sensores inválidos;
- consumo de armazenamento;
- tempo do dashboard/PDF;
- falhas de download privado.

Não registre senhas, chaves de sensor, conteúdo de avaliações ou anexos.

## 9. Backup e restauração

Inclua:

- banco;
- `private_media/`;
- configuração segura;
- versão do código e migrações.

Faça testes periódicos de restauração. Restaurar apenas banco ou apenas anexos cria inconsistência.

## 10. Atualização

1. manutenção;
2. backup;
3. código em pasta/release nova;
4. dependências;
5. validadores e testes;
6. `migrate --plan`;
7. `migrate`;
8. `collectstatic`;
9. restart;
10. smoke test.

## 11. Checklist de produção

- `DEBUG=False`;
- HTTPS/HSTS;
- cookies seguros;
- hosts/origens restritos;
- segredo forte;
- banco com menor privilégio;
- diretório privado isolado;
- backups testados;
- rate limiting;
- política de retenção;
- `python manage.py check --deploy`;
- 43 testes e roteiro manual aprovados.
