# Contributing

Thanks for helping improve Image Provenance Inspector. Keep changes focused,
explainable, and covered by tests. Public API changes should update the
Pydantic models, tests, CLI/UI consumers, and README examples together.

## Development

The project targets Python 3.12 and uses `uv`:

```bash
uv sync --extra dev --extra c2pa --extra ui --extra analysis
uv run ruff check .
uv run ruff format --check .
uv run pytest --cov=app --cov-report=term-missing --cov-fail-under=80
```

Use Conventional Commits for changes. Do not include credentials, private
images, or unlicensed fixture assets in the repository. See
[`fixtures/README.md`](fixtures/README.md) for fixture requirements.

## Release maintainers

The release workflow in [`.github/workflows/publish.yml`](.github/workflows/publish.yml)
runs when a GitHub Release is published. It builds the wheel and source
distribution, then uses PyPI Trusted Publishing through GitHub Actions OIDC.
No long-lived PyPI token should be stored in the repository.

Before the first release, configure a pending publisher at
<https://pypi.org/manage/account/publishing/>:

- PyPI project: `image-provenance-inspector`
- GitHub owner: `KageRyo`
- GitHub repository: `image-provenance-inspector`
- Workflow filename: `publish.yml`
- GitHub environment: `pypi`

The setup follows the [PyPI Trusted Publishing guide](https://docs.pypi.org/trusted-publishers/)
and the [PyPA GitHub Actions publishing guide](https://packaging.python.org/en/latest/guides/publishing-package-distribution-releases-using-github-actions-ci-cd-workflows/).
