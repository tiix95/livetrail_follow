# livetrail-follow

Suit un ou plusieurs coureurs sur livetrail.net et envoie une notification
webhook a chaque passage a un point de chronometrage.

## Configuration

Copier `config/config.example.yml` et l'adapter :

```yaml
webhook:
  endpoint: "https://notify.example.net/api/send"
  module: "email"
  topic: "livetrail"

poll_interval_seconds: 30
state_file: "/data/state.json"

admin_recipient: "followers-mas"

runners:
  - name: "Blandine L'Hirondel"
    url: "https://grandraid-reunion.v3.livetrail.net/en/2026/runners/4507?raceId=MAS"
    recipient: "followers-mas"
```

`module`/`topic`/`recipient` peuvent etre definis par coureur (surchargent les
valeurs par defaut de `webhook`).

`admin_recipient` est optionnel. Si defini, au demarrage, le service envoie
pour chaque coureur surveille une notification webhook a ce destinataire
pour signaler le debut de la surveillance (en plus des notifications de
passage envoyees au `recipient` de chaque coureur). Si omis, aucune
notification de demarrage n'est envoyee.

Si un coureur surveille abandonne la course (statut `WITHDRAWN` avec course
terminee), le service envoie une notification webhook dediee au `recipient`
de ce coureur, puis arrete la surveillance.

```json
{
  "title": "Blandine L'Hirondel - Abandon",
  "message": "Blandine L'Hirondel a abandonné la course.",
  "recipient": "followers-mas",
  "module": "sms",
  "topic": "livetrail",
  "url": "https://grandraid-reunion.v3.livetrail.net/en/2026/runners/4507?raceId=MAS"
}
```

Si le coureur termine normalement la course (course terminee avec un statut
different de `WITHDRAWN`), le service envoie une notification webhook dediee
au `recipient` de ce coureur pour signaler son arrivee, puis arrete la
surveillance.

```json
{
  "title": "Blandine L'Hirondel - Arrivée",
  "message": "Blandine L'Hirondel a terminé la course.",
  "recipient": "followers-mas",
  "module": "sms",
  "topic": "livetrail",
  "url": "https://grandraid-reunion.v3.livetrail.net/en/2026/runners/3892?raceId=MAS"
}
```

A chaque nouveau passage, le service envoie un `POST` JSON a `webhook.endpoint` :

```json
{
  "title": "Blandine L'Hirondel - Plaine des Merles",
  "message": "Blandine L'Hirondel a passé le point de contrôle Plaine des Merles à 15.9 km en 3:18:27.",
  "recipient": "followers-mas",
  "module": "sms",
  "topic": "livetrail",
  "url": "https://grandraid-reunion.v3.livetrail.net/en/2026/runners/3892?raceId=MAS"
}
```

## Lancer

```sh
make run   # dans un conteneur podman
```

`make run` monte `config/config.example.yml` (modifiable via `CONFIG_FILE=...`)
sur `/etc/livetrail-follow/config.yml` et un dossier `./data` (via `DATA_DIR=...`)
sur `/data` pour l'etat persistant (`state.json`).

## CI/CD

`make version` affiche la version courante (lue depuis `__version__` dans
`src/livetrail_follow/__init__.py`), utilisee comme tag de l'image conteneur.

Deux workflows GitHub Actions se declenchent a chaque push sur `main` :

- `container.yml` : construit l'image avec `make build`, puis la tague et la
  pousse sur GitHub Container Registry (`ghcr.io/<repo>:latest`).
- `release.yml` : recupere la version via `make version` et cree une release
  GitHub `v<version>` avec notes auto-generees si elle n'existe pas encore.
  Si la release existe deja, le workflow ne fait rien, il est donc sans
  risque de le lancer a chaque push.
