# Poland Power Pulse — News & Signal Monitor · GitHub hosting toolkit (v32)

This folder is a complete GitHub repository. Upload it as-is, switch on GitHub Pages, and the dashboard goes live with:

- **Live news feed** — refreshed every 30 minutes from the RSS feeds in `config/sources.json`
- **Polish → English translation** — Polish headlines keep the original wording, with an English translation underneath
- **Daily link check** — dead article links are detected and hidden automatically

## What's inside

```
index.html                         ← the dashboard (v32)
.nojekyll                          ← tells GitHub Pages to serve files as they are
.github/workflows/update-feed.yml  ← "Update live feed" — every 30 min
.github/workflows/verify-links.yml ← "Verify headlines and links" — daily 05:00 UTC
scripts/feed_fetcher.py            ← reads feeds, filters Polish power news, translates, writes data/signals.json
scripts/verify_links.py            ← checks every article link, writes data/headlines.json + data/link_report.json
config/sources.json                ← list of news feeds (switch feeds on/off here)
data/signals.json                  ← live items (written by the workflow — starts empty)
data/headlines.json                ← dead-link list (written by the workflow — starts empty)
```

No packages to install — both scripts use only standard Python.

---

## Step-by-step setup (about 15 minutes)

### Step 1 — Create the repository
1. Sign in at github.com → **+** (top right) → **New repository**.
2. Name it, e.g. `poland-power-pulse`.
3. Choose **Public** (see the note on privacy at the end). Leave "Add a README" **unticked**. Click **Create repository**.

### Step 2 — Upload the files
**Important:** the `.github` folder starts with a dot, so Windows and Mac often hide it. If it isn't uploaded, the workflows won't appear.

**Option A — Web upload (easiest)**
1. Unzip the toolkit on your computer.
2. Make hidden files visible:
   - **Windows:** in File Explorer, go to **View → Show → Hidden items**.
   - **Mac:** in Finder, press **Cmd + Shift + .**
3. On the empty repository page, click **uploading an existing file**.
4. Open the unzipped folder, select **everything inside it** (including `.github` and `.nojekyll`) and drag it onto the page.
5. Click **Commit changes**.
6. Check that the repository now shows a `.github` folder. If it doesn't, use Option C below.

**Option B — Git command line**
```bash
cd poland-power-pulse-toolkit
git init && git add . && git commit -m "Poland Power Pulse v32"
git branch -M main
git remote add origin https://github.com/<your-user>/poland-power-pulse.git
git push -u origin main
```

**Option C — If `.github` didn't upload (create the workflow files by hand)**
1. In the repository, click **Add file → Create new file**.
2. In the name box type `.github/workflows/update-feed.yml`. The slashes create the folders automatically.
3. Open `update-feed.yml` from the zip in Notepad, copy everything, and paste it in. Click **Commit changes**.
4. Repeat for `.github/workflows/verify-links.yml`.

### Step 3 — Allow the workflows to save data
1. Go to **Settings → Actions → General**.
2. Under **Workflow permissions**, select **Read and write permissions** and click **Save**.

Without this, the workflows run but fail at the "Commit" step with a `403` error.

### Step 4 — Switch on GitHub Pages
1. Go to **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **Deploy from a branch**, **Branch** to `main`, and the folder to `/ (root)`. Click **Save**.
3. After 1–2 minutes the page shows your site address: `https://<your-user>.github.io/poland-power-pulse/`

### Step 5 — Add a translation key (needed for Polish news)
Polish articles are only shown once they've been translated. Without a key, the feed shows English-language news only.

1. Get a key. Either option works:
   - **DeepL API Free** (500,000 characters/month free) — sign up at deepl.com/pro-api, then copy the key from your account. Free keys end in `:fx`.
   - **Azure AI Translator** — create a Translator resource in the Azure portal, then copy **Key 1** and the **Region**.
2. In the repository go to **Settings → Secrets and variables → Actions → New repository secret**.
3. Add the secret(s):
   - **For DeepL:** name `DEEPL_API_KEY`, value = your key
   - **For Azure:** `AZURE_TRANSLATOR_KEY` (your key) and `AZURE_TRANSLATOR_REGION` (e.g. `westeurope`)

Keys are stored encrypted and are never visible in the code or on the website.

### Step 6 — Run the workflows for the first time
1. Open the **Actions** tab.
   - If you see **"Workflows aren't being run on this repository"** / **"I understand my workflows, go ahead and enable them"**, click it. This only appears for forked or copied repositories.
2. Click **Update live feed** in the left list, then **Run workflow → Run workflow**.
3. Wait about a minute until the run shows a green tick.
4. Repeat for **Verify headlines and links**.

After that, both run on their own: the feed every 30 minutes, the link check daily.

### Step 7 — Check it's working
- **Open your Pages address.** The badge at the top should read **"Live · updated …"**. If it reads **"Curated · …"**, the live data hasn't loaded yet (see troubleshooting).
- **Open `data/feed_status.json` in the repository.** It shows each feed (`"ok": true/false`), how many items were kept, and whether translation worked.
- **Open `data/link_report.json`** after the daily check. It shows the status of every article link.

---

## Updating the dashboard later
- **New dashboard version:** upload the new HTML as `index.html` (replacing the old one) and commit. Data files and workflows don't need to change.
- **Add or remove news feeds:** edit `config/sources.json`.
  - To switch a feed off, set `"enabled": false`.
  - For international outlets, `"poland_only": true` keeps only items mentioning Poland or Polish companies and assets.

## How the rules are applied
| Rule | Where |
|---|---|
| Headline shown exactly as the publisher wrote it | `feed_fetcher.py` copies the feed title unchanged |
| Polish headline kept; labelled English translation underneath | `title_pl` = original, `title` = translation; the dashboard shows "English translation:" |
| Untranslated Polish items never shown | the fetcher skips them; the dashboard also filters them |
| Link goes to the publisher's article | link taken from the feed item itself |
| No duplicates of built-in items | URLs already in `index.html` are skipped; similar headlines within 14 days are merged |
| Only Jan 2024 onwards | items before 2024-01-01 are dropped |
| Dead links hidden | the daily check marks 404/410 or unreachable sites; "blocked" (403) links are kept, because they usually work in a browser |

## Troubleshooting
| Problem | Fix |
|---|---|
| No workflows in the Actions tab | The `.github` folder wasn't uploaded. Use Step 2, Option C. |
| Run fails at "Commit" with `403` / `Permission denied` | Step 3: set **Read and write permissions**. |
| Run fails at "Commit" with a push conflict | Re-run it. The two workflows share a queue, so this is rare. |
| Badge shows "Curated", not "Live" | Open the dashboard from the **Pages address**, not by double-clicking `index.html` on your computer (browsers block local data loading). Then run **Update live feed** once. |
| No Polish news appears | Add the translation secret (Step 5), then check `"translation"` in `data/feed_status.json`. |
| A feed shows `"ok": false` | The publisher changed or blocked its feed. Set `"enabled": false` or replace the URL in `config/sources.json`. |
| Scheduled runs start late or skip | GitHub delays scheduled jobs at busy times. Use **Run workflow** for an immediate refresh. |
| Workflows stopped after a long quiet period | GitHub can disable scheduled workflows in inactive repositories. Re-enable them in the Actions tab. |

## Note on privacy
A GitHub Pages site is publicly reachable by anyone with the address, even if the repository is private. Private-repository Pages also require a paid GitHub plan. If the dashboard must stay internal, host `index.html` and the `data/` folder on an internal SharePoint/Azure Static Web App instead, and keep the workflows in a private repository.
