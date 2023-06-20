deploy: clean
	python3.8 setup.py sdist bdist_wheel && python3.8 -m twine upload dist/*

local-install: local-uninstall
	python3 setup.py develop --user

local-uninstall:
	python3 setup.py develop --uninstall --user

clean:
	rm -f dist/oes-*
	rm -f *.egg-info

test:
	python3.8 -m pytest tests
