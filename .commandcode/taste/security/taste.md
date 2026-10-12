# Security

- Prefers traditional OAuth redirect flow over Google Identity Services (GIS); no popups, no client_secret in the frontend, no parallel/secondary auth system. Confidence: 0.9
- Preserves the existing session/refresh mechanism and token storage (e.g., localStorage) instead of doing architectural migrations mid-task. Confidence: 0.85
- Never places secrets in the frontend. Confidence: 0.9
- Validates OAuth state against CSRF and redirect_uri, and does not trust identity or email supplied by the client (requires a verified email). Confidence: 0.9
- Never logs authorization codes, secrets, or tokens, and keeps real credentials out of the repository. Confidence: 0.9
- Never sends access/refresh tokens, authorization codes, or secrets in redirect URLs; for the OAuth callback handoff prefers an HttpOnly cookie session, or (when incompatible with the existing session) a single-use, short-lived, atomically-consumed exchange code. Confidence: 0.9
- For system-to-system webhooks, authenticates via HMAC-SHA256 signature of the body and puts the tenant/company id inside the signed payload (never in an unverified header), rather than adding a SECURITY DEFINER bypass. Confidence: 0.85
- Verifies webhook HMAC over the raw, original request body (read before any parsing) using constant-time comparison, with the secret from secure configuration and invalid signatures rejected. Confidence: 0.85
- Keeps authentication/security enabled on infrastructure services (e.g., never disables Elasticsearch `xpack.security`); credentials come from environment variables, not hardcoded or disabled. Confidence: 0.8
- Never binds service ports to `0.0.0.0`; exposes them on loopback (`127.0.0.1`) only, documenting host vs internal addresses separately. Confidence: 0.75
- Accepts unencrypted (no-TLS) transport only on the internal Docker network during development, with authentication, explicitly documented as a dev-only decision; requires TLS in production (and never disables TLS verification as a permanent fix). Confidence: 0.75
- Never trusts tenant/company identifiers sent by the client; derives them from the authenticated context, and enforces mandatory authorization/visibility filters server-side on every request regardless of what the client sends. Confidence: 0.8
- Does not expose internal failure details (the specific infrastructure/backend error) to the client, returning only an appropriate generic status/error code. Confidence: 0.7
- Uses least-privilege application credentials for production external services (e.g., a restricted API key scoped to the needed index/alias) instead of the admin/superuser account; the API key takes precedence over basic-auth passwords. Confidence: 0.75
