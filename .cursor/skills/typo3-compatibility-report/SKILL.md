---
name: typo3-compatibility-report
description: Generates a TYPO3 upgrade compatibility CSV from Extension Manager screenshots. Extracts extension name, key, installed, state, and current version; looks up latest version and TYPO3 compatibility on TER; writes the sample CSV layout with dynamic v12.x/v13.x (or other) columns. Use when the user shares an Extension Manager screenshot, asks for a TYPO3 compatibility report, or mentions a TYPO3 upgrade analysis.
---

# TYPO3 Compatibility Report

Turn Extension Manager screenshot(s) into a compatibility CSV matching `TYPO3 Upgrade Analysis - Sample.csv`.

## Workflow

Copy and track:

```
- [ ] Collect missing inputs
- [ ] Parse screenshot(s) into extension rows
- [ ] Run TER lookup script
- [ ] Merge Type / Latest / Compatibility
- [ ] Write CSV and footer totals
```

### 1. Collect missing inputs

Ask **only** for fields not already in the first message (or screenshot):

- Domain (e.g. `abc.com`)
- Current TYPO3 version
- Target TYPO3 major version(s) to check (e.g. `12` and `13`)

Do not ask for fields the user already gave. Accept one or many target majors.

Upgrade title: `TYPO3 Upgrade from {current} to {targets}` (targets joined with ` / ` if more than one).

### 2. Parse screenshots

From every Extension Manager screenshot, extract one row per extension:

| Field | Source |
|---|---|
| Name | Screenshot |
| Key | Screenshot |
| Installed | Screenshot → `Yes` or `No` |
| State | Screenshot → `Stable` / `Beta` / `Alpha` / `Experimental` / `Obsolete` |
| Current | Screenshot version |
| EM type | Screenshot if shown (`System` / `Local` / similar) |

Rules:

- Accept multiple screenshots; merge and dedupe by **Key**.
- If a row is unreadable, ask for a clearer screenshot. Do not guess keys or versions.
- Include every extension visible in the screenshot(s).

### 3. TER lookup

Run (from the project root):

```bash
python3 .cursor/skills/typo3-compatibility-report/scripts/ter_lookup.py --majors 12,13 key1 key2 key3
```

Replace `--majors` with the user's target majors. Pass every extension key.

Or pipe JSON:

```bash
python3 .cursor/skills/typo3-compatibility-report/scripts/ter_lookup.py <<'EOF'
{"keys": ["news", "seo"], "majors": [12, 13]}
EOF
```

The script calls `https://extensions.typo3.org/api/v1` with `User-Agent: TYPO3 13.4.0`. Do not fetch TER in the browser unless the script fails.

### 4. Merge fields

**Note**

Stack matching notes in this order, joined with `; `. If none match, use `-`.

1. Abandoned TER (`abandoned: true`, owner `abandoned_extensions`): `Extension is not maintained`
2. Type is `TER` and Current is a Composer/git branch version (`dev-main`, `dev-master`, or any `dev-*`): `TER extension but {current} is in use`
3. Type is `TER`, a requested major is Compat **No**, and `git_compatibility` for that major is true: `Compatibility is not released officially on TER but is available in the git repo: {repository_url}`
4. Type is `TER`, a requested major is Compat **No**, and `eap_url` is set: `Compatibility is not released officially on TER but is available via Early Access Program: {eap_url}`

Custom and System rows stay `-` (no abandoned, `dev-*`, git, or EAP notes). Git and EAP never change Compatibility; columns stay TER-only Yes/No. `eap_url` comes from `scripts/eap_extensions.json` (extension key → URL only; no TYPO3 majors). The Note appears for whatever majors the user requested that are TER **No**, and stops when live TER reports **Yes**.

**System/core** (screenshot EM type is System / System Extension / Core):

- Type = `Custom` only for local/project extensions, **not** for System
- For System/core: Type = `System`, Latest = `-`, every requested compatibility column = `Yes`

If the screenshot has no System marker, use TER:

| TER result | Type | Latest | Compatibility |
|---|---|---|---|
| `found: true` | `TER` | `latest` (or `-` if empty) | `Yes`/`No` per major from script |
| `found: false` | `Custom` | `-` | `No` for every major |

Compatibility values in the CSV must be `Yes` or `No` (not booleans).

### 5. Write the CSV

Path: `{sanitized-domain}-TYPO3-Upgrade-Analysis.csv` in the project root.

Sanitize the domain for the filename: lowercase, replace characters other than letters, digits, `.`, `-` with `-`.

Keep the sample Excel layout: leading empty column, grouped headers, dynamic Compatibility columns, footer totals.

Column order after the leading empty cell:

`#`, `Name`, `Key`, `Installed`, `Type`, `State`, `Current`, `Latest`, one `v{major}.x` per requested major (same order the user gave), `Note`

Example grouped header for majors 12 and 13:

```
,abc.com,,,,,TYPO3 Upgrade from 11.5.x to 12 / 13,,,,,
,Extension Details,,,,,,Extension Version,,Compatibility,,Note
,#,Name,Key,Installed,Type,State,Current,Latest,v12.x,v13.x,
```

`Extension Details` spans `#` through `State`. `Extension Version` spans `Current` and `Latest`. `Compatibility` spans every `v{major}.x` column. `Note` is the last column.

Footer on the last row:

- Installed column: `{n} Installed` where `n` is the count of `Yes`
- Each `v{major}.x` column: `{n} Compatible` where `n` is the count of `Yes` in that column

Use the Python `csv` module (or equivalent) so commas in names are quoted. Number rows from 1. Do not pad empty placeholder rows.

## TER script output

```json
{
  "news": {
    "found": true,
    "latest": "14.1.1",
    "compatibility": {"12": true, "13": true},
    "abandoned": false,
    "repository_url": "https://github.com/georgringer/news",
    "git_compatibility": {"12": false, "13": false},
    "eap_url": null
  },
  "powermail": {
    "found": true,
    "latest": "13.3.0",
    "compatibility": {"12": true, "13": true},
    "abandoned": false,
    "repository_url": "https://github.com/in2code-de/powermail",
    "git_compatibility": {"12": false, "13": false},
    "eap_url": "https://www.in2code.de/en/agency/typo3-extensions/early-access-program/"
  },
  "sourceopt": {
    "found": true,
    "latest": "5.2.8",
    "compatibility": {"12": true, "13": false},
    "abandoned": false,
    "repository_url": "https://github.com/lochmueller/sourceopt",
    "git_compatibility": {"12": false, "13": true},
    "eap_url": null
  },
  "news_ttnewsimport": {
    "found": true,
    "latest": "2.0.0",
    "compatibility": {"12": false, "13": false},
    "abandoned": true,
    "repository_url": "https://github.com/fsaris/news_ttnewsimport",
    "git_compatibility": {"12": false, "13": false},
    "eap_url": null
  },
  "my_site_ext": {
    "found": false,
    "latest": null,
    "compatibility": {"12": false, "13": false},
    "abandoned": false,
    "repository_url": null,
    "git_compatibility": {"12": false, "13": false},
    "eap_url": null
  }
}
```

`found: true` and empty `latest` means the key exists on TER but has no published versions (treat Latest as `-`; compatibility from the script, usually `No` unless System override applies).

`git_compatibility` is filled only when a requested major is TER-incompatible and a GitHub/GitLab `repository_url` exists. Otherwise those flags stay `false`.

`eap_url` is the program URL from `scripts/eap_extensions.json` when the extension key is listed there; otherwise `null`. It does not depend on which majors were requested. The CSV Note uses it only if Type is `TER` and at least one of those majors is Compat **No**.
