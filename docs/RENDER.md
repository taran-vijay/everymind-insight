# Render hosted demo

The Docker web service runs the existing dashboard and upload API together. GitHub Pages remains unchanged. Render configuration uses the free plan in Virginia, one Python worker, a health check at `/health`, and `EVERYMIND_HOSTED=1`. Render supplies `RENDER_EXTERNAL_HOSTNAME` and `PORT`. The existing local launchers retain their loopback-only behavior.

Hosted visitors receive a signed, Secure, HttpOnly, SameSite=Strict browser-session cookie. Uploads and filter release history are separate for each browser session. Four active sessions are allowed, with 20-minute inactivity expiry checked on API access. Exceeding capacity returns 429 without replacing another visitor's data. Processing is serialized to bound concurrent analysis on the free instance. The hosted file limit is 5 MB. This is a bounded judging demo, not a production multi-tenant service.

Uploads are processed on the server, not just in the browser. Only use authorized data. The hosted page explains the data handling and provides a clear-upload button. Uploads are not intentionally written to disk or logged by the application; restarting the worker clears all sessions. The Docker image contains runtime source, dashboard assets and the synthetic fixture only—not workbooks, private audits or generated report directories. This is not a privacy certification or a guarantee against deliberate abuse of a public endpoint.

Service restarts and free-plan idle sleep can require re-uploading the survey. Render's free tier sleeps after inactivity, so startup delay is possible. No database, persistent disk or paid resource is required. Auto-deploy is off so future code pushes do not unexpectedly replace the running demo.

Local hosting-mode test:

```sh
EVERYMIND_HOSTED=1 RENDER_EXTERNAL_HOSTNAME=127.0.0.1 .venv/bin/python -m uvicorn everymind_insight.server:create_app --factory --host 127.0.0.1 --port 8001
```

For a realistic cookie/session test use HTTPS (Secure cookies are deliberately required); automated TestClient tests use `https://demo.onrender.com`. Normal local use should continue to use `sh run.sh` without hosted mode.
