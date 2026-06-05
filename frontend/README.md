# LiSA Frontend

Interface React (Vite) simple pour analyser un texte et afficher la probabilité
qu'il s'agisse d'un jailbreak / prompt injection.

- **Gauche** : zone de saisie du texte.
- **Droite** : verdict global + score par scanner (prompt injection, secrets, …).

## Développement

```bash
npm install
npm run dev
```

L'application appelle l'API définie par `VITE_API_URL`
(défaut : `http://localhost:8000/analyze`). Copiez `.env.example` en `.env`
pour la personnaliser.

L'API doit accepter `POST { "data": "<texte>" }` et renvoyer un objet de la forme :

```json
{
  "content": "…",
  "predictions": { "PromptInjection": true, "Secrets": false },
  "scores": { "PromptInjection": 0.92, "Secrets": 0.0 },
  "process_time": 0.123
}
```

## Docker

```bash
docker build -t lisa-frontend ./frontend
docker run -p 8080:80 lisa-frontend
```
