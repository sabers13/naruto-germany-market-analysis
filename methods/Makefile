.PHONY: demo test check

demo:
	PYTHONPATH=src python3 -m market_methods --metrics examples/metrics.json --config examples/config.json --quality examples/quality.json --out /tmp/naruto-methods-demo.json

test:
	PYTHONPATH=src python3 -m unittest discover -s tests -v

check: test demo
	cmp /tmp/naruto-methods-demo.json examples/demo-report.json
