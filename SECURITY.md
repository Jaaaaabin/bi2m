# Security

## Reporting a problem

Report a vulnerability privately through GitHub: the repository's
**Security** tab → **Report a vulnerability**. Please do not open a public
issue for it.

Only the latest commit on `main` is supported; fixes are not backported.

## What the server trusts

bi2m is a research tool meant to run on your own machine. Its server
(`Interfaces/Frontend/core/server/`, used by `npm run dev`, `npm start` and the
Docker image) has **no login**. Anyone who can reach its port can:

- upload files, which are stored under `data/uploads/` (up to
  `BI2M_MAX_UPLOAD_MB`, default 500 MB, each);
- start recognition runs, which spawn Python processes and write results to
  `public/res/intents/`;
- start tile builds, which write to `public/tiles/`;
- read everything the viewer serves, including every stored result and tile set;
- download the example models in `data/` and, if one is configured, any model
  in the model library (`BI2M_IFC_CORPUS`).

That is why it listens on `127.0.0.1` only, and why `docker-compose.yml`
publishes the port on `127.0.0.1` only. Setting `HOST=0.0.0.0`, or dropping
`127.0.0.1:` from the port mapping, exposes all of the above. Do that only
behind a reverse proxy that requires authentication.

These are design choices, not vulnerabilities. A way to do any of this
without reaching the port, or to read or write files outside the places
listed above, is a vulnerability: please report it.

## Known advisories

`fast-xml-parser`, which comes in through `@thatopen/components` 2.x, has
published advisories. It runs only in the browser, on files you open
yourself. The fix needs ThatOpen 3.x, which waits for the full viewer-stack
upgrade.
