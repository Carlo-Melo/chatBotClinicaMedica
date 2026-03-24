# Chatbot Clinica Medica

Backend FastAPI para substituir a logica do n8n de um chatbot de WhatsApp usado por uma clinica medica.

## O que esta pronto

- Endpoint `POST /webhook` para receber eventos do WAHA.
- Normalizacao da mensagem recebida.
- Cadastro e busca de paciente no Supabase.
- Maquina de estados da conversa armazenada no Redis.
- Buffer de mensagens com debounce e lock por usuario no Redis.
- Processamento multimodal com Gemini para texto, audio e imagem.
- Fluxo estruturado de agendamento.
- Pausa da IA para atendimento humano.
- Envio de mensagens via WAHA com divisao de respostas longas.
- Historico de conversa no Supabase.
- Logs estruturados com `loguru`.
- Tratamento centralizado de erros.

## Estrutura

```text
app/
  main.py
  config.py
  api/
  bot/
  services/
  repositories/
  flows/
  models/
  utils/
```

## Variaveis de ambiente

1. Copie `.env.example` para `.env`.
2. Preencha as credenciais do Redis, Supabase, WAHA e Gemini.

## Como executar

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Webhook esperado

Exemplo minimo:

```json
{
  "from": "556299999999",
  "body": "quero marcar consulta",
  "type": "text",
  "name": "Joao"
}
```

Configure o WAHA para enviar os eventos para:

```text
POST http://SEU_HOST:8000/webhook
```

## Tabelas Supabase

O arquivo `supabase_schema.sql` contem uma sugestao minima para:

- `patients`
- `conversation_history`
- `appointment_requests`

## Observacoes de arquitetura

- O `n8n` pode ficar apenas como pass-through ou ser removido do fluxo.
- O processamento principal agora esta centralizado em `app/bot/handler.py`.
- O estado da conversa fica em Redis, e o historico persistente fica em Supabase.
- O fluxo de agendamento foi implementado de forma estruturada, enquanto perguntas abertas seguem para Gemini.
