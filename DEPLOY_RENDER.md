# Deploying FlaskShop to Render — Step-by-Step Guide

This guide takes you from zero to a live production URL on Render with a
PostgreSQL database, in about 15 minutes.

---

## Prerequisites

| Requirement | Where to get it |
|---|---|
| GitHub account | https://github.com |
| Render account (free) | https://render.com |
| Git installed locally | https://git-scm.com |

---

## Part 1 — Push the Project to GitHub

### 1.1  Initialise a local Git repo

Open a terminal in the project root (the folder containing `run.py`):

```bash
git init
git add .
git commit -m "Initial commit — FlaskShop"
```

### 1.2  Create a new GitHub repository

1. Go to https://github.com/new
2. Name it `flaskshop` (or anything you like)
3. Leave it **Public** (required for Render free tier) or Private (paid)
4. Do **not** add a README / .gitignore — the project already has one
5. Click **Create repository**

### 1.3  Push your code

GitHub will show you the exact commands — they look like this:

```bash
git remote add origin https://github.com/YOUR_USERNAME/flaskshop.git
git branch -M main
git push -u origin main
```

---

## Part 2 — Create a PostgreSQL Database on Render

1. Log in to https://dashboard.render.com
2. Click **New +** → **PostgreSQL**
3. Fill in the form:

   | Field | Value |
   |---|---|
   | Name | `flaskshop-db` |
   | Database | `flaskshop` |
   | User | `flaskshop` |
   | Region | **Frankfurt (EU Central)** or closest to your users |
   | Plan | **Free** (sufficient to start) |

4. Click **Create Database**
5. Wait ~1 minute for provisioning
6. On the database detail page, click **"Internal Database URL"** to copy it.
   It looks like: `postgresql://flaskshop:PASSWORD@HOST/flaskshop`
   
   > **Keep this URL handy** — you'll paste it in Part 3.

---

## Part 3 — Create the Web Service on Render

1. Click **New +** → **Web Service**
2. Choose **Build and deploy from a Git repository** → click **Next**
3. Connect GitHub if prompted, then select your `flaskshop` repository
4. Configure the service:

   | Field | Value |
   |---|---|
   | Name | `flaskshop` |
   | Region | Same region as your database |
   | Branch | `main` |
   | Runtime | **Python 3** |
   | Build Command | `./build.sh` |
   | Start Command | `gunicorn "app:create_app()" --workers 4 --bind 0.0.0.0:$PORT --timeout 120` |
   | Plan | **Free** |

5. Scroll down to **Environment Variables** and add:

   | Key | Value |
   |---|---|
   | `DATABASE_URL` | Paste the **Internal Database URL** from Part 2 |
   | `SECRET_KEY` | Click **Generate** (Render generates a secure random value) |
   | `PYTHON_VERSION` | `3.11.0` |

6. Click **Create Web Service**

Render will now:
- Pull your code from GitHub
- Run `pip install -r requirements.txt`
- Run `python seeds.py` (creates tables + seeds demo data)
- Start Gunicorn

The first deploy takes 3–5 minutes. Watch the **Logs** tab for progress.

---

## Part 4 — Verify the Deployment

Once the status badge shows **Live**, click the `.onrender.com` URL at the top.

**Check these pages work:**

| URL | Expected |
|---|---|
| `/` | Homepage with featured products |
| `/shop` | Product grid |
| `/auth/login` | Login form |
| `/admin/` | Admin dashboard (after login) |

**Login with the seeded admin account:**
- Email: `admin@shop.com`
- Password: `admin1234`

> ⚠️ Change the admin password immediately via the admin panel after first login.

---

## Part 5 — (Optional) Add a Custom Domain

1. In your Render web service, click **Settings** → **Custom Domains**
2. Click **Add Custom Domain**
3. Enter your domain, e.g. `shop.yourdomain.com`
4. Render shows you a **CNAME record** to add:

   | Type | Name | Value |
   |---|---|---|
   | CNAME | `shop` | `flaskshop.onrender.com` |

5. Add this record in your DNS provider (Cloudflare, GoDaddy, Namecheap, etc.)
6. DNS propagation takes 5–30 minutes
7. Render automatically provisions a **free TLS/SSL certificate** (Let's Encrypt)

---

## Part 6 — Automatic Deploys (CI/CD)

By default, every `git push` to `main` triggers a new deploy automatically.

```bash
# Make a change, commit and push:
git add .
git commit -m "Update product page layout"
git push origin main
# → Render detects the push and redeploys within ~2 minutes
```

To deploy manually: go to your service → click **Manual Deploy** → **Deploy latest commit**.

---

## Environment Variables Reference

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | **Yes** (production) | Full PostgreSQL connection string from Render |
| `SECRET_KEY` | **Yes** | Random 32+ char string for session signing |
| `PYTHON_VERSION` | Recommended | Pin to `3.11.0` for reproducible builds |

Variables you set in the Render dashboard are **never committed to git** — they
are injected at runtime as environment variables, keeping secrets safe.

---

## Troubleshooting

### Build fails: `./build.sh: Permission denied`
```bash
# Fix locally then push:
chmod +x build.sh
git add build.sh
git commit -m "Fix build.sh permissions"
git push
```

### `ModuleNotFoundError: No module named 'psycopg2'`
Check `requirements.txt` contains `psycopg2-binary>=2.9.9` and redeploy.

### `connection refused` / database errors on first deploy
The database might still be provisioning. Wait 2 minutes and click
**Manual Deploy** to retry.

### App shows 500 error in production
1. Click **Logs** in the Render dashboard
2. Look for the Python traceback
3. Common cause: `SECRET_KEY` not set — add it in Environment Variables

### Free tier "spins down" after 15 minutes of inactivity
This is normal on the free plan. The first request after inactivity takes
~30 seconds to wake up. Upgrade to the Starter plan ($7/month) to eliminate
cold starts.

---

## Local Development (after cloning)

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/flaskshop.git
cd flaskshop

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env — leave DATABASE_URL blank to use local SQLite

# 5. Seed demo data
python seeds.py

# 6. Run
flask run
# → http://localhost:5000
```

No PostgreSQL needed locally — the app automatically uses SQLite when
`DATABASE_URL` is not set.

---

## Architecture Summary

```
Browser
  │
  ▼
Render Web Service (Gunicorn + Flask)
  │    app/blueprints/auth/    → /auth/*
  │    app/blueprints/shop/    → / and /shop/*
  │    app/blueprints/admin/   → /admin/*
  │    app/database.py         → unified pg/sqlite layer
  │
  ▼
Render PostgreSQL (production)
  └── users, products, orders, order_items
```

---

*Generated for FlaskShop — Flask + PostgreSQL ecommerce app.*
