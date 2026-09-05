# Serveur de streaming vidéo

Serveur de diffusion vidéo en temps réel, en **Flask** et **Flask-SocketIO**, avec
traitement des images par **OpenCV**.

## Pile

- **Flask** pour le serveur et les routes
- **Flask-SocketIO** pour la diffusion en temps réel vers les clients connectés
- **OpenCV** pour la capture et le traitement des images
- **python-dotenv** pour la configuration

## Organisation

| Chemin | Rôle |
|---|---|
| `run.py` | Point d'entrée, démarre le serveur SocketIO |
| `app/__init__.py` | Fabrique de l'application (`create_app`) |
| `app/config.py` | Configuration lue depuis l'environnement |
| `app/routes/` | Routes HTTP |
| `app/models/` | Modèles de données |
| `app/utils/` | Utilitaires, dont le traitement vidéo |
| `app/templates/` | Gabarits HTML |

## Lancer

```bash
pip install -r requirements.txt
cp .env.example .env      # puis renseigner vos valeurs
python run.py
```

Le serveur écoute sur `http://0.0.0.0:5000`.

## Configuration

Toutes les valeurs sensibles passent par le fichier `.env`, qui **n'est pas
versionné**. Le modèle `.env.example` liste les clés attendues.

## Auteur

RAMANATENANIAVO Nasandratra Alfa
