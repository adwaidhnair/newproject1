# Demo deployment: Vercel, Render, and Neon

This setup keeps the frontend, API, and database in cloud services; it does not
use a laptop or home network as a server.

It is intended for a demo with non-sensitive data, not production ERP data.
Render's free web service may sleep when idle, and free plans from all providers
can change or be withdrawn. Vercel's Hobby plan is for personal,
non-commercial use; a commercial project may require a paid plan. Review the
current [Vercel pricing](https://vercel.com/pricing),
[Render free service limits](https://render.com/docs/free), and
[Neon pricing](https://neon.tech/pricing) before creating resources.

## 1. Push the deployment configuration to GitHub

Commit and push the project, including `render.yaml` and this guide, to the
GitHub repository you will connect to the providers. Do not commit `.env`
files, database exports, setup tokens, or passwords.

## 2. Create the PostgreSQL database

1. Create a Neon project and choose a region close to the Render service.
2. In Neon, copy the **direct** connection string and keep it private.
3. For SQLAlchemy with this backend's psycopg 3 driver, set its scheme to
   `postgresql+psycopg://` (instead of `postgresql://`). Keep Neon's
   `sslmode=require` parameter.
4. Do not put this URL in GitHub or in a frontend environment variable.

## 3. Deploy the API to Render

1. In Render, create a **Blueprint** from the connected GitHub repository.
   Render reads `render.yaml` and creates the API web service.
2. When prompted for unsynced environment values, enter:
   - `DATABASE_URL`: the Neon connection string from step 2.
   - `AUTH_TOKEN_SECRET`: a unique random value of at least 32 characters.
   - `BOOTSTRAP_SETUP_TOKEN`: another unique random value of at least 32
     characters. You will use this once to create the first owner.
   - `CORS_ORIGINS`: the exact final frontend origin, without a trailing slash,
     for example `https://flouxi.work.gd`.
3. Wait for the service to deploy and check its Render URL at `/healthz`.
   It should return `{"status":"ok"}`. The blueprint runs database migrations
   before starting the API.
4. Add `api.flouxi.work.gd` as a custom domain on the Render service. Render
   will show the DNS record target to use. Do not guess the target.

## 4. Deploy the frontend to Vercel

1. Import the same GitHub repository into Vercel.
2. Set **Root Directory** to `frontend`. Use the Vite defaults:
   - Build command: `npm run build`
   - Output directory: `dist`
3. Add the environment variable `VITE_API_URL` with the value
   `https://api.flouxi.work.gd/api/v1`, then redeploy.
4. Add `flouxi.work.gd` as the Vercel project's custom domain. Follow the DNS
   records Vercel shows for that domain.

Using the frontend and API on subdomains of the same custom domain keeps the
HTTP-only session cookie in the same site while still requiring the API's
explicit CORS allowlist. If you choose different domains, browser cookie
restrictions may prevent sign-in from working.

## 5. Point DNS to the cloud services

At the DNS provider for `flouxi.work.gd`, replace the old home-server record
only after both cloud services are ready:

- Use Vercel's displayed record for `flouxi.work.gd`.
- Use Render's displayed record for `api.flouxi.work.gd`.

DNS interfaces and required targets can vary, so copy the exact values from
each provider's domain screen. Do not create router port forwards or expose
your laptop. After DNS resolves, verify:

- `https://flouxi.work.gd` loads the frontend.
- `https://api.flouxi.work.gd/healthz` returns `{"status":"ok"}`.

If you use a different frontend domain, update `CORS_ORIGINS` in Render to
that exact HTTPS origin and redeploy the API.

## 6. Create the first owner account

Open the site and use the first-owner registration flow. Enter the
`BOOTSTRAP_SETUP_TOKEN` configured in Render. After the owner account has been
created, remove `BOOTSTRAP_SETUP_TOKEN` from the Render service environment and
redeploy. Keep the owner password private and enable any account protections
available to you.

The database starts empty; this deployment guide does not load sample or
production records. Do not import sensitive ERP data into this free demo
deployment.
