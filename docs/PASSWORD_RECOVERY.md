# Recuperacao de conta (esqueci minha senha)

Recuperacao por codigo de verificacao em dois canais: e-mail (codigo gerado pelo
backend) e SMS (Twilio Verify). O fluxo e o mesmo nos dois canais:

1. pedir codigo;
2. verificar codigo e obter um `reset_token` opaco de curta duracao;
3. definir a nova senha com o `reset_token`.

## Endpoints

| Metodo | Rota | Autenticacao | Resposta |
| --- | --- | --- | --- |
| POST | `/api/v1/auth/password-recovery/request` | publica + Turnstile | `202 {"status":"accepted"}` |
| POST | `/api/v1/auth/password-recovery/verify` | publica | `200 {"reset_token":"...","expires_in":600}` |
| POST | `/api/v1/auth/password-recovery/reset` | reset_token | `204` |
| POST | `/api/v1/account/phone/verification/start` | JWT | `202 {"status":"accepted"}` |
| POST | `/api/v1/account/phone/verification/check` | JWT | `200 {"verified":true}` |
| GET | `/api/v1/account/phone/verification` | JWT | `{"verified":bool,"phone_masked":"..."}` |

`request` exige exatamente um entre `email` e `phone` (XOR; ambos ou nenhum
retornam 422 Problem Details). `verify` tem o mesmo XOR.

## Fluxo de e-mail

```text
request(email)
  -> Turnstile (fail-closed)
  -> rate limit IP/identificador/diario
  -> resolve usuario por email (ACTIVE)
  -> cooldown 60 s por usuario
  -> gera 6 digitos com secrets
  -> Redis: HMAC(PEPPER, user_id:codigo) + tentativas + locale
  -> Celery: codigo via broker, sem result backend
  -> 202 generico

verify(email, codigo)
  -> rate limit de verify
  -> compara com hmac.compare_digest
  -> consome o codigo atomicamente
  -> gera reset_token (secrets.token_urlsafe)
  -> Redis: apenas SHA-256(token), TTL 600 s

reset(reset_token, nova_senha)
  -> valida 8-128 caracteres (validate_password_strength)
  -> consome o token com GETDEL antes de gravar
  -> UPDATE users.password_hash (Argon2id) sob RLS
  -> incrementa credential_epoch na mesma transacao
  -> auditoria sem PII
  -> aviso de senha alterada por e-mail
  -> revoga sessoes antigas pela epoca (cache Redis + banco)
```

## Fluxo de SMS

```text
request(phone)
  -> Turnstile (fail-closed)
  -> rate limit IP/identificador/diario
  -> resolve user/company por telefone verificado (SECURITY DEFINER)
  -> confere ACTIVE e cooldown 60 s
  -> Celery: PhoneVerificationService.start (Twilio Verify)
  -> 202 generico

verify(phone, codigo)
  -> rate limit de verify
  -> resolve telefone verificado e usuario ACTIVE
  -> chama Twilio Verify tambem quando nao ha conta (tempo equivalente)
  -> contador proprio de tentativas SMS (maximo 5, TTL 600 s)
  -> aprovado: reset_token com channel=sms

reset(reset_token, nova_senha)
  -> mesmo fluxo do e-mail; auditoria registra channel=sms
```

## Tabelas

- `user_verified_phones`: `id`, `user_id`, `company_id`, `phone_e164`,
  `verified_at`, `created_at`. Telefone unico globalmente e unico por usuario.
  FORCE RLS por `company_id`.
- `user_credential_state`: `user_id` (PK logica), `company_id`,
  `credential_epoch`, `password_changed_at`, `updated_at`. FORCE RLS.
- Funcoes SECURITY DEFINER novas: `public.resolve_user_by_verified_phone` e
  `public.claim_verified_phone`. A segunda usa advisory locks e aplica a
  politica "quem provou controle por ultimo vence".

## Chaves Redis

| Chave | Conteudo | TTL |
| --- | --- | --- |
| `password_recovery:code:{user_id}` | HMAC do codigo, tentativas, locale | 600 s |
| `password_recovery:cooldown:{user_id}` | marcador de reenvio | 60 s |
| `password_recovery:sms_attempts:{user_id}` | contador de tentativas SMS | 600 s |
| `password_recovery:reset:{sha256(token)}` | user_id, company_id, locale, channel | 600 s |
| `credential_epoch:{user_id}` | epoca atual para access tokens | 60 s |
| `rl:password_recovery:*` | baldes de rate limit | conforme politica |
| `rl:phone_verification:*` | baldes de rate limit | conforme politica |

O codigo de e-mail em texto puro nunca vai para PostgreSQL, Redis, logs,
auditoria, metricas ou result backend. Ele existe apenas no argumento da task
Celery, que trafega pelo broker. O worker nao roda com `-E`, eventos de task
estao desligados e as tasks usam `ignore_result`.

## Ameacas mitigadas

- **Enumeracao:** request sempre 202 com corpo fixo; verify sempre 400 generico
  para codigo invalido, expirado, conta inexistente/inativa e telefone nao
  verificado. O caminho sem conta executa trabalho equivalente (probe Redis no
  request; check Twilio no verify).
- **Forca bruta:** rate limit por IP/identificador, cooldown de reenvio, maximo
  de tentativas no e-mail e contador SMS proprio, alem do limite do Twilio.
- **Replay:** codigo consumido atomicamente; reset_token consumido com GETDEL e
  hash apenas no Redis.
- **Corrida de reset:** GETDEL garante que apenas uma requisicao consome o
  token; a epoca de credencial e incrementada na mesma transacao da senha.
- **Turnstile:** fail-closed em token invalido, timeout, rede ou resposta
  inesperada.
- **Redis fora:** fail-closed com 503 generico no fluxo de recuperacao.
- **Sessoes antigas:** access token carrega `cep`; refresh token guarda a epoca;
  tokens de epoca anterior sao recusados.
- **PII:** logs, auditoria e metricas nao recebem e-mail, telefone, codigo,
  token ou senha. A auditoria usa apenas user_id/company_id e channel.
- **Respostas:** nao incluem user_id, company_id, hash de senha ou detalhes do
  provedor. Todas as rotas da feature enviam `Cache-Control: no-store` e
  `Pragma: no-cache`.

## Limitacoes conhecidas

- SMS so e enviado para telefone previamente verificado e unico; telefone nao
  verificado recebe a mesma resposta generica, sem envio.
- Conta Twilio em modo trial so envia SMS para numeros verificados no console.
- O aviso de senha alterada de um reset por SMS usa locale `None` e cai no
  fallback pt-BR, pois o usuario nao possui locale persistido.
- Se o cache de epoca falhar apos o reset, a convergencia depende do TTL de
  60 s; a senha e a epoca no banco ja foram commitadas.
- Nao ha WAF/edge; o rate limit e de aplicacao.
- O reset nao autentica o usuario em seguida; ele volta ao login.

## Checklist de deploy

### Render (backend + worker)

- [ ] `PASSWORD_RECOVERY_ENABLED=true` somente no final da ativacao.
- [ ] `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `RESEND_FROM`.
- [ ] `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_VERIFY_SERVICE_SID`.
- [ ] `TURNSTILE_SECRET_KEY`.
- [ ] Worker Celery e RabbitMQ ativos; Redis disponivel.
- [ ] Worker sem `-E`; eventos de task desligados (`worker_send_task_events=False`).
- [ ] Migrations `0043` e `0044` aplicadas antes do codigo.
- [ ] `PHONE_VERIFICATION_DRY_RUN=false` em producao.
- [ ] `TRUSTED_PROXY_COUNT` coerente com Render + Vercel (normalmente 2).

### Vercel (frontend)

- [ ] `NEXT_PUBLIC_TURNSTILE_SITE_KEY` configurada.
- [ ] `NEXT_PUBLIC_PASSWORD_RECOVERY_ENABLED=true`.
- [ ] Dominio da Vercel adicionado em Hostnames do widget no painel Cloudflare.
- [ ] Dominio verificado no Resend para o remetente.

### Ordem segura

1. aplicar migrations;
2. configurar segredos e worker;
3. validar health/readiness e um request interno;
4. publicar frontend com a flag ainda desligada;
5. ligar `PASSWORD_RECOVERY_ENABLED=true` no backend por ultimo;
6. ligar `NEXT_PUBLIC_PASSWORD_RECOVERY_ENABLED=true` no frontend.

## Roteiro manual em producao

1. Com a flag desligada, confirme que `/api/v1/auth/password-recovery/request`
   responde 404 e que o link nao aparece no login.
2. Ligue a flag no backend e confirme que um e-mail de teste recebe o codigo em
   ate 1 minuto.
3. Tente codigo errado 5 vezes e confirme o mesmo 400 generico; o sexto envio
   deve respeitar o cooldown/limite.
4. Verifique o fluxo completo de e-mail: request, verify, reset, login com a
   nova senha e rejeicao do access token antigo.
5. Em uma conta com telefone verificado, faca o fluxo SMS; em telefone nao
   verificado, confirme o 202 generico sem SMS.
6. Confirme `Cache-Control: no-store` e ausencia de PII nas respostas e logs do
   Render.
7. Confirme no painel Twilio o consumo de SMS e o teto diario configurado.
