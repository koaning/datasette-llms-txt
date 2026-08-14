.PHONY: install test serve fixtures build publish clean

VENV := .venv
PY := $(VENV)/bin/python
PORT ?= 8001

install:  ## Create a venv and install the plugin with test dependencies
	uv venv --python 3.12 $(VENV)
	uv pip install --python $(VENV) -e '.[test]'

test:  ## Run the test suite
	$(VENV)/bin/pytest -q

fixtures:  ## Download Datasette's fixtures.db for local testing
	curl -sL https://latest.datasette.io/fixtures.db -o fixtures.db

serve: fixtures  ## Run Datasette against fixtures.db (override PORT=xxxx)
	$(VENV)/bin/datasette fixtures.db -p $(PORT)

build:  ## Build the wheel and sdist into dist/
	rm -rf dist
	uv build

publish: build  ## Upload the built distributions to PyPI (needs UV_PUBLISH_TOKEN)
	uv publish

clean:  ## Remove the venv, downloaded db and build artifacts
	rm -rf $(VENV) fixtures.db *.egg-info .pytest_cache dist build
