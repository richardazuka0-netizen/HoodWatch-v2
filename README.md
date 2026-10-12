# Hoodwatch v2

Fixed version for Render (and local) deployment.

## What changed from v0.1

- **Checksum fix** — factory addresses are checksummed before being passed to web3 `get_logs`.
- **Cloud startup** — in `--cloud` mode the web server starts immediately so Render health checks pass. Indexing + scoring runs in the background.
- **Smaller default window** on free tier (2000 blocks via env var).
- Includes `render.yaml` and `runtime.txt`.

## Deploy on Render

1. Create a new GitHub repo and upload every file from this folder.
2. On Render: New → Web Service → connect the repo.
3. Render should read `render.yaml` automatically. If not, set:
   - Build: `pip install -r requirements.txt`
   - Start: `python hoodwatch.py --cloud`
   - Health check: `/health`
4. Deploy.

Free tier sleeps and uses an ephemeral disk. Data resets on restart; the app re-indexes a recent window each time.

## Local

```bash
python hoodwatch.py
# open http://127.0.0.1:8787
```

Read-only. No private keys. Testnet only.
