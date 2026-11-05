Capture the complete Kadal Mitra walkthrough: $ARGUMENTS

Arguments: `<capture-apk> <live-apk> [langs]` (spec §17.14). No languages means every language released in
`config/languages.yaml`.

1. Make sure the laptop backend runs in snapshot mode with capture on: `.env` has `CAPTURE_SCENARIOS=1`, a
   `CAPTURE_TOKEN` and `DATA_MODE=snapshot`; channels, mcp, agent and ty-copilot run with `CACHE_DISABLED=1`.
   Then run `scripts/capture_all.sh $ARGUMENTS` and note the output folder it prints.
2. If a flow fails, open its log under `<folder>/<lang>/maestro/<flow>.log` (or the Playwright report), find the
   failing step, fix the flow in `apps/app/e2e/` (selectors are `testID`s; never change app code or test data
   for this), and re-run that language. Stop after three attempts and report it.
3. Run `python scripts/check_coverage.py <folder> --langs <langs>` and fix every gap it lists by adding the missing
   step to the right flow — never by deleting a feature from `apps/app/e2e/coverage.yaml`. A gap that needs a
   missing feature or a test account is reported, not hidden.
4. Read every PNG of every language in order. Confirm each shows the screen its name says, in that language's
   script (right-to-left where expected), with no blank, loading, crash or permission screen left by mistake and
   no real person's data. Replace each `TODO caption` in `README.md` with a one-line caption, in English.
5. Check each `manifest.json` (flows passed, video longer than 10 minutes) and `apk/SHA256SUMS` against the
   release page.
6. Zip the folder and run `gh release upload <tag> <zip>`.
7. Report: languages captured, screenshots per language, video length per language, gaps, anything fixed.
