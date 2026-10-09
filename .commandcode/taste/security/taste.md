# Security

- Prefers traditional OAuth redirect flow over Google Identity Services (GIS); no popups, no client_secret in the frontend, no parallel/secondary auth system. Confidence: 0.9
- Preserves the existing session/refresh mechanism and token storage (e.g., localStorage) instead of doing architectural migrations mid-task. Confidence: 0.85
- Never places secrets in the frontend. Confidence: 0.9
- Validates OAuth state against CSRF and redirect_uri, and does not trust identity or email supplied by the client (requires a verified email). Confidence: 0.9
- Never logs authorization codes, secrets, or tokens, and keeps real credentials out of the repository. Confidence: 0.9
- Never sends access/refresh tokens, authorization codes, or secrets in redirect URLs; for the OAuth callback handoff prefers an HttpOnly cookie session, or (when incompatible with the existing session) a single-use, short-lived, atomically-consumed exchange code. Confidence: 0.9
