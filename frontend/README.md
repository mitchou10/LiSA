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

L'application appelle l'API définie par `VITE_API_URL`, fixée **au moment du
build** : en développement, `http://localhost:8000` (copiez `.env.example` en
`.env.local` pour la changer). Vide, c'est la même origine : les appels vont
vers `/api/v1/...` sur l'hôte qui sert l'application, ce qui est le défaut de
l'image Docker. Pour une API sur un autre hôte, passez
`--build-arg VITE_API_URL=https://api.example.com`.

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
