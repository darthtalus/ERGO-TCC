# Internacionalização — ERGO v5

## Idiomas

- Português do Brasil: `pt-br`, catálogo `locale/pt_BR/`;
- Inglês: `en-us`, catálogo `locale/en/` quando aplicável.

O seletor usa o mecanismo de idioma do Django. Templates, formulários, mensagens de backend, labels dos gráficos e relatórios devem usar funções/tags de tradução.

## Templates

```django
{% load i18n %}
{% trans "Task" %}
{% blocktrans %}Text with {{ variable }}{% endblocktrans %}
```

Evite texto visível fixo em JavaScript. Quando necessário, injete a tradução via template ou `gettext` do JavaScript.

## Python

```python
from django.utils.translation import gettext as _
message = _('Task completed successfully.')
```

Para labels de modelo, use `gettext_lazy`.

## Atualização de catálogos

```bash
python manage.py makemessages -l pt_BR -l en
python manage.py compilemessages
```

O pacote inclui `.mo` PT-BR compilado. Após alterar `.po`, recompile.

## Testes

A validação estática verifica mensagens essenciais e os testes alternam o idioma em fluxos relevantes. Faça ainda smoke test manual:

1. abrir em português;
2. percorrer criação, conclusão, revisão e dashboard;
3. alternar para inglês;
4. repetir mensagens de sucesso e erro;
5. gerar PDF e verificar labels;
6. abrir página pública nos dois idiomas.

## Regras editoriais

- não traduzir códigos (`DOING`, `APPROVED`) quando forem dados técnicos; mostrar label traduzido ao usuário;
- manter “Stakeholder” se essa for a terminologia institucional;
- usar “pseudonimizado”, não “anonimizado”, na exportação adicional;
- distinguir “Ambiente/Acesso” conforme a documentação teórica;
- mensagens de segurança não devem revelar existência de usuário, e-mail ou status privado.
