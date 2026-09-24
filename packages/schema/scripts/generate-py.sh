#!/bin/sh
# Generates python/questboard_schema/*.py from schemas/*.schema.json. Do not edit the output by hand.
set -eu
cd "$(dirname "$0")/.."
uvx --python 3.12 --from 'datamodel-code-generator==0.83.0' --with 'ruff==0.16.8' datamodel-codegen \
  --input schemas \
  --input-file-type jsonschema \
  --output python/questboard_schema \
  --output-model-type pydantic_v2.BaseModel \
  --target-python-version 3.12 \
  --use-standard-collections \
  --use-union-operator \
  --field-constraints \
  --use-double-quotes \
  --disable-timestamp \
  --formatters ruff-format ruff-check \
  --custom-file-header '# Generated from packages/schema/schemas. Do not edit; run `pnpm schema:gen`.'
