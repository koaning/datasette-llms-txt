.PHONY: install test test-min test-max serve fixtures build pypi clean

VENV := .venv
PY := $(VENV)/bin/python
PORT ?= 8001

# Datasette compatibility matrix: oldest supported line (0.65.x) and the 1.0
# alpha. The plugin must work on both.
DATASETTE_MIN := datasette<1.0
DATASETTE_MAX := datasette>=1.0a0

install:  ## Create a venv and install the plugin with test dependencies
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(VENV) -e '.[test]'

test: test-min test-max  ## Run the suite against every supported Datasette version

test-min: | .venv-min  ## Run the suite against the oldest supported Datasette (0.65.x)
	.venv-min/bin/datasette --version
	.venv-min/bin/pytest -q

test-max: | .venv-max  ## Run the suite against the newest Datasette (1.0 alpha)
	.venv-max/bin/datasette --version
	.venv-max/bin/pytest -q

# The per-version environments are built once and then reused, so repeat test
# runs are fast. Run `make clean` to rebuild them (for example, after you change
# the dependencies).
.venv-min:
	uv venv --python 3.12 $@
	uv pip install --python $@ -e '.[test]'
	uv pip install --python $@ '$(DATASETTE_MIN)'

.venv-max:
	uv venv --python 3.12 $@
	uv pip install --python $@ -e '.[test]'
	uv pip install --python $@ '$(DATASETTE_MAX)'

fixtures:  ## Download Datasette's fixtures.db for local testing
	curl -sL https://latest.datasette.io/fixtures.db -o fixtures.db

serve: fixtures  ## Run Datasette against fixtures.db (override PORT=xxxx)
	$(VENV)/bin/datasette fixtures.db -p $(PORT)

build:  ## Build the wheel and sdist into dist/
	rm -rf dist
	uv build

pypi: build  ## Upload the built distributions to PyPI (needs UV_PUBLISH_TOKEN)
	uv publish

clean:  ## Remove the venv, downloaded db and build artifacts
	rm -rf $(VENV) .venv-min .venv-max fixtures.db *.egg-info .pytest_cache dist build
