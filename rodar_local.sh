#!/bin/bash

# Script para rodar o projeto ERGO localmente
# Baseado nas instruções do README.md

echo "--- Iniciando Ambiente Local ERGO ---"

# 1. Verificar se o ambiente virtual existe, se não, criar
if [ ! -d "venv" ]; then
    echo "Criando ambiente virtual (venv)..."
    python3 -m venv venv
fi

# 2. Ativar o ambiente virtual
echo "Usando ambiente virtual..."
# source venv/bin/activate

# 3. Instalar dependências
echo "Instalando/Atualizando dependências..."
venv/bin/pip install -r requirements.txt

# 4. Verificar arquivo .env
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        echo "Aviso: Arquivo .env não encontrado. Copiando de .env.example..."
        cp .env.example .env
        echo "Por favor, verifique as configurações no arquivo .env antes de continuar se necessário."
    else
        echo "Aviso: Arquivo .env não encontrado e .env.example também não existe."
    fi
fi

# 5. Rodar migrações
echo "Rodando migrações do banco de dados..."
venv/bin/python manage.py migrate

# 6. Iniciar o servidor de desenvolvimento
echo "Iniciando o servidor em http://127.0.0.1:8000"
echo "Pressione Ctrl+C para encerrar."
venv/bin/python manage.py runserver
