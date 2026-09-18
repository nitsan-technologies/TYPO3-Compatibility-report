# TYPO3 compatibility report

Cursor skill that turns TYPO3 Extension Manager screenshots into an upgrade compatibility CSV.

It reads the extension list from your screenshot, looks up each key on [TER](https://extensions.typo3.org/), and writes a report in the same layout as `TYPO3 Upgrade Analysis - Sample.csv`. Compatibility columns (`v12.x`, `v13.x`, …) are created from the TYPO3 versions you ask for.

## How to use

1. Open this project in Cursor.
2. Start a new chat and attach one or more **Extension Manager** screenshots (the list of extensions). If the list is paginated, attach every page.
3. In the same message, include whatever you already know:
   - Domain (for example `abc.com`)
   - Current TYPO3 version (for example `11.5.36`)
   - Target TYPO3 version(s) to check (for example `12` and `13`)
4. Ask for a TYPO3 compatibility report (or mention this skill by name: `typo3-compatibility-report`).
5. If domain, current version, or target versions were missing, answer those follow-up questions.
6. The agent writes `{domain}-TYPO3-Upgrade-Analysis.csv` in the project root.

You do not need to type the extension list. The screenshot is the source for name, key, installed (Yes/No), state, and current version.

## What the report contains

| Column | Source |
| --- | --- |
| Name, Key, Installed, State, Current | Extension Manager screenshot |
| Type | `TER` if the key exists on TER; `Custom` if it does not; `System` if the screenshot marks it as a system/core extension |
| Latest | Latest version on TER (`-` for custom and system/core) |
| `v{major}.x` | `Yes` / `No` — TER has a version compatible with that TYPO3 major. System/core rows are `Yes`. Custom rows are `No`. |
| Note | `-` by default. TER notes (joined with `; ` when more than one applies): abandoned → `Extension is not maintained`; branch install (`dev-main`, `dev-*`) → `TER extension but {current} is in use`; TER Compat No but git `composer.json` supports the target → `Compatibility is not released officially on TER but is available in the git repo: {url}`; TER Compat No and the key is in `scripts/eap_extensions.json` → `Compatibility is not released officially on TER but is available via Early Access Program: {url}` |

The CSV header uses your domain and `TYPO3 Upgrade from {current} to {targets}`. The footer counts installed extensions and how many are compatible per target version.

## TER lookup (optional, used by the skill)

The skill runs this helper; you can also run it yourself:

```bash
python3 .cursor/skills/typo3-compatibility-report/scripts/ter_lookup.py --majors 12,13 news seo
```

Requires Python 3 and network access. No extra packages. The helper also returns `eap_url` from [`eap_extensions.json`](.cursor/skills/typo3-compatibility-report/scripts/eap_extensions.json) (extension key → program URL; no TYPO3 majors in that file).

## Sample format

See [TYPO3 Upgrade Analysis - Sample.csv](TYPO3%20Upgrade%20Analysis%20-%20Sample.csv) for the spreadsheet layout. Your generated file follows that structure, with one `v{major}.x` column per target version you requested.
