# Diagramas — ERGO v5

## Atuais

- [`ergo_architecture_2026.svg`](ergo_architecture_2026.svg) — componentes, clientes, serviços e armazenamento;
- [`ergo_data_model_2026.svg`](ergo_data_model_2026.svg) — relações principais do núcleo, auditoria e funcionalidades integradas.

Também são entregues versões PNG e os fontes Graphviz `.dot`.

## Legados

- `ergo_core_models_v3.png`;
- `ergo_schemas_v3.png`.

Os diagramas legados são históricos e não representam todas as constraints, ciclos, snapshots, chaves de sensores ou campos da v5. Use os diagramas atuais e [`ARQUITETURA_E_MODELO_DE_DADOS.md`](ARQUITETURA_E_MODELO_DE_DADOS.md).

## Regenerar

Com Graphviz:

```bash
dot -Tsvg docs/ergo_architecture_2026.dot -o docs/ergo_architecture_2026.svg
dot -Tpng docs/ergo_architecture_2026.dot -o docs/ergo_architecture_2026.png
dot -Tsvg docs/ergo_data_model_2026.dot -o docs/ergo_data_model_2026.svg
dot -Tpng docs/ergo_data_model_2026.dot -o docs/ergo_data_model_2026.png
```
