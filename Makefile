run: app.py venv
	FLASK_APP=app.py FLASK_ENV=development venv/bin/flask run --host=0.0.0.0

venv: requirements.txt
	python3 -m venv --system-site-package $@
	venv/bin/pip install -r $<
