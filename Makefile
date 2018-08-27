SOURCES =  $(wildcard *.py)
SOURCES += $(wildcard static/*.html)
SOURCES += $(wildcard static/*.js)
SOURCES += $(wildcard static/*.css)


debug: app.py venv
	FLASK_APP=app.py FLASK_ENV=development venv/bin/flask run --host=0.0.0.0

run: app.py venv
	FLASK_APP=app.py venv/bin/flask run --host=0.0.0.0

venv: requirements.txt
	python3 -m venv --system-site-package $@
	venv/bin/pip install -r $<

edit: $(SOURCES)
	rmate $(SOURCES)

ci: Makefile $(SOURCES)
	git add Makefile $(SOURCES)
