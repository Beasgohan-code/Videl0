# Studio regression checks

- `npm test`: pure formatting, image layout/import, public-summary privacy, and draft validation checks.
- `npm run build`: production compilation and TypeScript checks.
- From the repository root, `.venv/bin/python -m unittest discover -s tests -q`: offline bot API/database checks. Telegram requests are mocked.

## Real-browser checks

Start a **production build** on port 3001:

```sh
npm run build
npx next start -H 0.0.0.0 -p 3001
```

In a second terminal, install a test Chromium (`npx playwright-core install chromium`) and run `npm run test:browser`. Alternatively, set `CHROMIUM_PATH` to an existing Chromium binary. `QA_BASE_URL` overrides the default `http://localhost:3001`.

The browser suite intercepts **every API request**. It never sends a Telegram message or needs bot credentials. It verifies live-summary UI/error handling using fixtures, real PNG/JSON export and import, keyboard positioning, mocked multipart publishing, duplicate confirmation, caption limits, recovery after reload, design persistence, and a 390px mobile viewport. Screenshots/downloads go into the OS temporary directory, not Git.

Photos are deliberately session-only. Recovery restores text and links; editable design JSON contains text/style/layout, not the uploaded background photo.

The browser suite also covers signed-out private-tool gates, every owner screen with mocked API fixtures, group search/settings updates, editable chat quick replies, safe analytics CSV download, keyboard tool-finder navigation, and editable layout/pattern PNG rendering. These checks do not verify your personal Telegram account, real moderation permissions, or live broadcast delivery.
