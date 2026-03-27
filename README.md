# JanSetu (AI Sakhi)

AI-powered Government Scheme Discovery Platform for India.

## Run locally

```bash
python manage.py runserver 127.0.0.1:8000
```

Open: `http://127.0.0.1:8000/`

## Push to GitHub

Run these commands in this project folder:

```bash
git init
git add .
git commit -m "Initial JanSetu app"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

## Deploy to browser (Render)

This repo includes `render.yaml` for one-click deployment.

1. Create a new repo on GitHub and push this code.
2. In Render, choose **New +** -> **Blueprint**.
3. Select your GitHub repo and deploy.
4. After deploy, open the generated Render URL in browser.

No Render Shell is required for first launch.
The app now runs migrations and seeds schemes automatically on startup when the database is empty.

If your Render app name is different, update:
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`

Both can be changed in Render environment variables.

## Notes

- Django apps cannot be hosted on GitHub Pages (static-only).
- Use GitHub for code hosting, and Render/Railway/Fly for live deployment.
