# 🚀 Grayspace Orbit

Grayspace Orbit is a production-grade, highly durable GitHub Action that fully automates your semantic versioning, changelog generation, and GitHub releases. 

Built for massive microservice architectures, it features robust state reconciliation, strict conventional commit enforcement, and an optional AI-driven Business Impact pipeline powered by Google Gemini.

## ⚡ Quick Start (Under 60 Seconds)

To adopt Grayspace Orbit seamlessly, just drop this 10-line snippet into a new workflow file (e.g., `.github/workflows/release.yml`) and push it to your `main` branch.

```yaml
name: Release
on:
  push:
    branches: [main]
permissions:
  contents: write # Required to push tags and releases
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Samuel-Nnadi/grayspace-orbit@v1 # Use the latest version
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
```

---

## 🛡️ Zero-Knowledge Architecture

Grayspace Orbit is designed with absolute security in mind:
- **No Long-Lived Credentials:** It operates exclusively using the short-lived, automatically generated `GITHUB_TOKEN` provided by the Actions runner.
- **Stateless Execution:** No source code or proprietary history is ever transmitted to an external server or telemetry endpoint.
- **In-Memory Parsing:** Commit processing and Git Tag calculations happen entirely locally within the isolated, ephemeral Docker container.

---

## 🌟 AI-Driven Ecosystem Expansion (V3)

Tired of release notes that just regurgitate technical commits like `fix: typo in db config`? 

Grayspace Orbit natively integrates with Google Gemini (`gemini-1.5-flash`). Simply provide a `gemini-api-key`, and the engine will dynamically extract your raw `.patch` diffs, analyze the actual code changes, and synthesize a highly polished, non-technical **Business Impact** summary for your stakeholders.

```yaml
      - uses: Samuel-Nnadi/grayspace-orbit@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          gemini-api-key: ${{ secrets.GEMINI_API_KEY }}
```

---

## 🏗️ Massive Monorepo Support

If you have a 22-microservice architecture, standard release tools will corrupt your tags. Grayspace Orbit allows you to define a `target-directory` to perfectly isolate your tags. A change in `/auth-service` will seamlessly trigger `auth-service-v1.1.0` while leaving `/payment-gateway` completely untouched.

To release multiple services concurrently, utilize a GitHub Actions matrix:

```yaml
    strategy:
      matrix:
        service: [auth-service, payment-gateway, inventory-service]
    steps:
      - uses: Samuel-Nnadi/grayspace-orbit@v1
        with:
          github-token: ${{ secrets.GITHUB_TOKEN }}
          target-directory: ${{ matrix.service }}
```

---

## ⚙️ The action.yml Contract

We strictly type and document all inputs and outputs to ensure flawless integration.

### Inputs

| Name | Required | Default | Description |
|------|----------|---------|-------------|
| `github-token` | **Yes** | N/A | Short-lived GitHub Token for API authentication. `${{ secrets.GITHUB_TOKEN }}`. |
| `target-directory` | No | `''` | Directory to track. Only commits affecting this directory will trigger a release. |
| `webhook-url` | No | `''` | Slack/Discord webhook URL for automated release notifications. |
| `fallback-policy` | No | `'patch'` | Strict policy for handling non-compliant commits: `patch` (default bump), `skip` (graceful exit), or `fail` (quarantine release). |
| `gemini-api-key` | No | `''` | Optional Gemini API key to power AI-driven Business Impact summaries. |

### Outputs

| Name | Description |
|------|-------------|
| `new-version` | The exact semantic version tag that was just published (e.g., `v1.2.3`). |
| `release-url` | The URL to the official GitHub Release page. |

---

## 🔄 State Reconciliation

If your pipeline fails midway through (e.g. the Git tag is pushed but the GitHub REST API times out before publishing the release), Grayspace Orbit will safely resume the process on the exact commit without throwing a fatal error. It also actively cleans up "orphaned tags" to keep your repository state immaculate.
