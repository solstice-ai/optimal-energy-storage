local-install:
	python3 setup.py develop --user

local-uninstall:
	python3 setup.py develop --uninstall --user

clean:
	rm -r dist/
	rm -r *.egg-info

test:
	python3 -m pytest tests
