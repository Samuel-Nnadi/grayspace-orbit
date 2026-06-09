# Grayspace Orbit

A production-grade, reusable GitHub Action that automates semantic versioning, changelog generation, and GitHub releases. 
Powered by Python and Docker, this action handles parsing Conventional Commits and ensures idempotency for robust deployments.

## Features

- **Semantic Versioning:** Automatically parses Conventional Commits to bump MAJOR, MINOR, or PATCH versions.
- **Monorepo Support:** Pass a `target-directory` to only track commits affecting specific directories.
- **Idempotency:** Safe to run twice! It resumes gracefully if a previous run tagged but failed to release.
- **Rich Notifications:** Post release updates directly to a Slack or Discord webhook.

## Usage

Create a workflow file in your repository (e.g., `.github/workflows/release.yml`):

```yaml
name: Release

on:
  push:
    branches:
      - main

jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Grayspace Orbit Release
        uses: user/grayspace-orbit@v1 # Replace with the actual org/repo of this action
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          target-directory: 'apps/api' # Optional
          webhook-url: ${{ secrets.SLACK_WEBHOOK_URL }} # Optional
```

## Inputs

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `github-token` | Yes | N/A | GitHub Token for API authentication. `${{ secrets.GITHUB_TOKEN }}` usually suffices. |
| `target-directory` | No | `''` | Directory to track. Only commits affecting this directory will trigger a release. Resulting tags will be prefixed (e.g., `apps-api-v1.0.0`). |
| `webhook-url` | No | `''` | Slack or Discord webhook URL for release notifications. |
| `fallback-policy` | No | `'patch'` | Strict policy for handling non-compliant commits. Options: `patch` (default bump), `skip` (graceful exit without release), `fail` (quarantine release and fail pipeline). |

## State Reconciliation (V2)

If a release pipeline fails midway (e.g. tag pushed, but release API times out), Grayspace Orbit will safely resume the release process on the exact commit without throwing a fatal error.
Additionally, it automatically detects and cleans up "orphaned tags" (tags matching the prefix that have no corresponding GitHub release attached to them) so that your repository remains clean.

## Outputs

| Name | Description |
|------|-------------|
| `new-version` | The semantic version that was just published (e.g., `v1.2.3`). |
| `release-url` | The URL to the official GitHub Release page. |
