# Agent guide

This file gives guidance to agents that work in this repository. `CLAUDE.md` is a
symlink to this file.

## Project

`datasette-llms-txt` is a Datasette plugin. It generates `llms.txt` documentation
for a Datasette instance. The generation code is in
`datasette_llms_txt/generate.py`. The plugin hooks and routes are in
`datasette_llms_txt/__init__.py`.

## Development

- Install the plugin and test dependencies: `make install`.
- Run the test suite: `make test`.
- Run Datasette against a sample database: `make serve`.

## Changelog

`CHANGELOG.md` records the notable changes for each release.

**Before you write or edit any changelog entry, apply the
`simplified-technical-english` skill.** The skill keeps the entries clear and
consistent. Do not add a changelog entry without it.

Add each user-visible change to the top section of `CHANGELOG.md`. Group the
change under `Added`, `Changed`, `Fixed`, or `Removed`.

## Pull requests

Apply the `simplified-technical-english` skill when you write the title and body
of a pull request. The skill keeps the text clear for every reader.

## Releases

To prepare a release:

1. Set the new version in `pyproject.toml`.
2. Add a version section to `CHANGELOG.md`. Apply the
   `simplified-technical-english` skill first.
3. Run `make test`.
4. Build and publish with `make pypi`.
