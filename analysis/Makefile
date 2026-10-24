# Full pipeline. Needs the private data archive (see docs/DATA_ACCESS.md).
# `make test` and `make demo` run without it.
UV := uv run
.PHONY: setup test demo check-archive shops fans trends votes lanes accuracy-sample accuracy-packet accuracy-score score benchmark release all clean

setup:
	uv sync
test:
	$(UV) pytest -q
demo:             ## synthetic end-to-end release build, no archive needed
	$(UV) python scripts/demo.py /tmp/nga-demo-release
check-archive:
	$(UV) python -c "from nga.paths import check_archive; print('archive', check_archive())"
shops:
	$(UV) python -m nga.shops
fans:
	$(UV) python -m nga.fans
trends:
	$(UV) python -m nga.trends
votes:
	$(UV) python -m nga.votes
lanes: shops fans trends votes
accuracy-sample:
	$(UV) python -m nga.accuracy sample
accuracy-packet:  ## labelling itself is manual
	$(UV) python -m nga.accuracy packet
accuracy-score:   ## needs reports/accuracy/labels.csv
	$(UV) python -m nga.accuracy score
score:
	$(UV) python -m nga.scoring
benchmark:
	$(UV) python -m nga.benchmark
release:
	$(UV) python -m nga.release
all: check-archive lanes accuracy-sample accuracy-score score benchmark release test
clean:
	rm -rf work
