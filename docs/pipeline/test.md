# Test stage

## Targeted tests

The test stage installs the Python 3.14 test requirements and the recursive requirements for each integration reported by change detection. It runs only `tests/components/<domain>` for those domains. A docs-only change produces an empty integration list and skips this suite.

## Contract suite

The contract suite runs on every pipeline change, in parallel with targeted tests. It covers `tests/test_core.py` and `tests/test_config_entries.py` for core behavior, `tests/components/api` for REST responses, `tests/components/websocket_api` for WebSocket responses, and `tests/helpers/test_entity.py` for the entity helper contract. Syrupy snapshots are checked normally; CI never passes `--snapshot-update`, so an API shape change fails the job.

## Reports

The test job writes JUnit XML for the targeted and contract suites and `coverage.xml` for changed integrations. It renders the suite results in the job summary and uploads them as `test-results-<sha>`, including files from failed test runs. Targeted integrations must reach 90% coverage when the suite succeeds.

## Flaky tests

A failed suite is rerun once with `pytest --lf`. A passing rerun is recorded in `flaky.json` (or `flaky-contract.json`) and reported in the job summary. A second failure keeps the test stage failed. The JSON artifacts provide the flaky count to later pipeline metrics.
