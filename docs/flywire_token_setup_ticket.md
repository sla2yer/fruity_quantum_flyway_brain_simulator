# Clarify FlyWire token setup and add browser helper script for CAVE API token retrieval

**Type:** Developer Experience / Setup / Documentation  
**Priority:** Medium

## Summary

The current repo setup around `FLYWIRE_TOKEN` is confusing. The project uses **FlyWire Codex** for web browsing/downloads and **CAVE / caveclient / fafbseg** for programmatic access, but the repo does not clearly explain that these are separate auth contexts.

We need to:
1. Clearly document the token system
2. Distinguish **FlyWire Codex login** from **CAVE API token** usage
3. Add a helper script that opens the browser-based token flow so the user can retrieve their token and paste/save it for local use

## Problem

Right now the repo includes:

```env
FLYWIRE_TOKEN=
```

but there is no clear explanation of:
- what this token is
- where it comes from
- why being signed into **FlyWire Codex** in the browser is not sufficient
- whether the token is for FlyWire Codex, CAVE, `caveclient`, or `fafbseg`
- how the user should actually obtain it

This creates confusion during setup, especially because the user may already be signed into the FlyWire Codex website and assume that means the Python tooling is authenticated too.

## Desired Outcome

Make the auth flow explicit and low-friction.

The repo should make it obvious that:

- **FlyWire Codex** = website/UI + CSV/static downloads
- **CAVE / caveclient** = programmatic API access
- **fafbseg** = helper library that also needs the same token for mesh/skeleton-related access
- `FLYWIRE_TOKEN` in `.env` refers to the **CAVE/FlyWire API token**, not the website login itself

## Requested Changes

### 1. Update README setup docs

Add a dedicated section called something like:

## FlyWire Authentication

This section should explain:

- being logged into **FlyWire Codex** in the browser does **not automatically configure Python access**
- the repo expects a **FlyWire/CAVE API token**
- the token is used by:
  - `caveclient`
  - `fafbseg`
  - repo scripts that read `FLYWIRE_TOKEN` from `.env`
- recommended setup flow:
  1. run helper script
  2. browser opens token page
  3. user copies token
  4. paste token into `.env`
  5. optionally save token to local CAVE secret storage

Also update wording throughout the README to always say **FlyWire Codex** when referring to `codex.flywire.ai`, to avoid confusion with any other “Codex” naming.

### 2. Add helper script to launch token flow

Add a script, e.g.:

```bash
scripts/setup_flywire_token.py
```

or

```bash
scripts/open_flywire_token_flow.py
```

This script should:

- explain what it is doing before opening anything
- open the browser flow for token retrieval
- default to **retrieving an existing token** flow first
- optionally support a `--new-token` flag for generating a new token
- print next-step instructions after launch:
  - copy token from browser
  - paste into `.env` as `FLYWIRE_TOKEN=...`
  - optionally save token via `caveclient` / `fafbseg`

### 3. Add post-launch terminal instructions

After opening the browser, the script should print something like:

- “This opens the CAVE/FlyWire API token flow”
- “This is separate from your FlyWire Codex website login”
- “Copy the token from the browser page”
- “Paste it into `.env` under `FLYWIRE_TOKEN`”
- “Then rerun `scripts/00_verify_access.py`”

### 4. Optional quality-of-life improvement

Add a second flag like:

```bash
--write-env
```

that prompts the user for the token and writes/updates:

```env
FLYWIRE_TOKEN=...
```

in the local `.env` file.

This is optional, but would reduce setup friction.

## Acceptance Criteria

- README clearly distinguishes:
  - **FlyWire Codex website login**
  - **CAVE/FlyWire API token**
- README explicitly states what `FLYWIRE_TOKEN` is used for
- A helper script exists that opens the browser token flow
- Script defaults to the safer “retrieve existing token” path
- Script provides clear terminal instructions for what to do after the browser opens
- A new user can follow the documented flow and understand why `.env` still needs a token even if they are already signed into FlyWire Codex in the browser

## Suggested UX Copy

Suggested wording for docs/script output:

> This project uses FlyWire Codex for web browsing/downloads and CAVE/fafbseg for programmatic access.  
> Your browser login to FlyWire Codex does not automatically populate the API token expected by local Python scripts.  
> The `FLYWIRE_TOKEN` value in `.env` should be your FlyWire/CAVE API token.

## Implementation Notes

The repo already reads `FLYWIRE_TOKEN` from `.env`, so this work is mostly:
- documentation cleanup
- consistent terminology
- helper script for browser launch and setup guidance

The helper script does **not** need to fully automate OAuth/token retrieval. It just needs to reliably launch the correct browser flow and explain the manual copy/paste step.

## Out of Scope

- Full automatic token provisioning
- Secret sync across machines
- Cloud secret manager integration
- Reworking the rest of the data pipeline
