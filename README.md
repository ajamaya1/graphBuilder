# Graph Builder — deploy to graphbuilder.io

A static site: three files served over HTTPS by GitHub Pages, behind your domain.

## What goes in the repo

```
graph-blocks.html          the app
graph-paths.js             the full Graph path index (~2.5 MB)
index.html                 redirects / to graph-blocks.html
CNAME                      contains: graphbuilder.io
.github/workflows/deploy.yml   auto-deploys on every push
```

## One-time setup

### 1. Create the GitHub repo
1. github.com → sign in (make a free account if needed) → **New repository**.
2. Name it `graphbuilder` (or anything), set **Public**, click **Create**.
3. On the repo page → **Add file → Upload files**. Drag in all four files above
   PLUS the `.github` folder. (To upload a folder, drag the whole `site_scaffold`
   contents in — GitHub keeps the folder structure.)
4. Click **Commit changes**.

### 2. Turn on Pages
1. Repo → **Settings** → **Pages** (left sidebar).
2. Under **Build and deployment → Source**, choose **GitHub Actions**.
   (Not "Deploy from a branch" — we use the Action.)
3. The deploy workflow runs automatically. Watch it under the **Actions** tab;
   a green check means it published. First run takes ~1–2 min.

### 3. Point graphbuilder.io at GitHub
At your domain registrar (where you bought graphbuilder.io), add these DNS records:

```
Type   Name   Value
A      @      185.199.108.153
A      @      185.199.109.153
A      @      185.199.110.153
A      @      185.199.111.153
AAAA   @      2606:50c0:8000::153
AAAA   @      2606:50c0:8001::153
AAAA   @      2606:50c0:8002::153
AAAA   @      2606:50c0:8003::153
CNAME  www    YOURUSERNAME.github.io
```

(These four A record IPs are GitHub's — current as of 2026; verify against
docs.github.com "Managing a custom domain" if a record is rejected.)

Then: repo → **Settings → Pages → Custom domain** → enter `graphbuilder.io` → Save.
Tick **Enforce HTTPS** once the certificate provisions (can take up to an hour).

### 4. Update the Entra app registration
In your GraphBuilder app registration → **Authentication**:
- Add a **Single-page application** redirect URI: `https://graphbuilder.io`
- And `https://graphbuilder.io/graph-blocks.html`
- Confirm **Supported account types** = *Accounts in any organizational directory*
  (multi-tenant) so users from any tenant can sign in.

## Updating the site later
Edit a file → commit (or re-upload) → the Action redeploys automatically in ~1 min.
No manual publish step.
