# Segurança, privacidade e LGPD — ERGO v5

> Este documento é orientação técnica. A adequação jurídica depende do contexto, finalidade, base legal, contratos e governança da organização.

## 1. Dados tratados

O ERGO pode armazenar:

- identificação e contato;
- empresa, país e outros dados cadastrais;
- tarefas, comentários e anexos;
- avaliações de desempenho percebido;
- efetividade diária e dimensões ABC;
- checklists preventivos;
- leituras ambientais;
- histórico de ações e revisões.

Esses dados podem ser sensíveis no contexto laboral mesmo quando não se enquadram automaticamente como dado pessoal sensível da LGPD.

## 2. Autorização

As permissões são verificadas no backend. Alterar HTML, JavaScript, ID ou URL não concede acesso.

- proprietário/admin: edição, papéis e gestão;
- executor: sua atribuição;
- stakeholder: acompanhamento e avaliação de outros executores;
- externo: somente conteúdo do token público;
- superusuário: privilégio global, ainda sujeito à separação de funções em autoavaliações.

Matriz completa: [`ROTAS_E_PERMISSOES.md`](ROTAS_E_PERMISSOES.md).

## 3. Workflow e auditoria

- ações críticas usam transação;
- estados inválidos são rejeitados;
- conclusão exige autoavaliação;
- revisões guardam ciclo e snapshot;
- revisões são append-only;
- aprovação congela avaliações;
- Django Admin deixa avaliações/revisões somente leitura.

Esses controles melhoram rastreabilidade, mas não substituem logs externos, trilha de acesso e monitoramento de infraestrutura.

## 4. CSRF, sessão e APIs

As telas autenticadas usam sessão e CSRF. O endpoint de sensores é isento de CSRF apenas para POST com chave dedicada. A chave completa é exibida uma vez; o banco guarda hash.

Recomendações:

- HTTPS obrigatório;
- cookies `Secure` e `HttpOnly`;
- rotação/revogação de chaves;
- rate limiting no proxy;
- não registrar chave em logs;
- segredos fora do repositório.

## 5. Anexos

- extensões e tamanho validados;
- diretório privado fora do static/media público;
- download por view autorizada.

Ainda é recomendado em produção:

- antivírus/antimalware;
- Content-Disposition seguro;
- bloqueio de execução no diretório;
- limite de armazenamento;
- retenção e descarte;
- backup criptografado.

## 6. Links públicos

Por padrão:

- nomes de participantes ficam ocultos;
- somente contagens são exibidas;
- o status de solicitação não é consultável por e-mail;
- token pode ser revogado.

`PUBLIC_SHARE_SHOW_PARTICIPANT_NAMES=True` aumenta exposição e deve ser uma decisão consciente.

## 7. Pseudonimização

O CSV adicional remove nome/e-mail e usa identificadores HMAC por exportação. Ainda pode haver reidentificação por datas, padrões e combinação com outras fontes. Trate-o como pseudonimizado.

Para pesquisa:

- mantenha chave de correspondência separada;
- minimize colunas;
- controle acesso;
- defina retenção;
- avalie risco de singling out e inferência.

## 8. Dashboard organizacional e pessoas

Métricas de outras pessoas ficam restritas a perfis privilegiados. A organização deve definir finalidade, transparência, necessidade, proporcionalidade e contestação. Evite ranking punitivo ou decisão automatizada sem supervisão.

## 9. Direitos e governança

A implantação deve definir:

- controlador/operador;
- finalidade e base legal;
- aviso de privacidade;
- canal para direitos do titular;
- retenção e eliminação;
- resposta a incidente;
- registros de operação;
- avaliação de impacto quando apropriado.

## 10. Configuração de produção

- `DEBUG=False`;
- `SECRET_KEY` forte e estável;
- hosts e origens restritos;
- HTTPS e HSTS;
- banco com menor privilégio;
- backups testados;
- `PRIVATE_MEDIA_ROOT` protegido;
- logs sem conteúdo sensível;
- atualizações de dependências;
- execução periódica de `check --deploy` e testes.

## 11. Limites

O pacote não fornece, por si só:

- anonimização garantida;
- DLP;
- antivírus;
- SIEM;
- criptografia de campo;
- MFA customizado;
- parecer jurídico;
- validação científica das heurísticas.
