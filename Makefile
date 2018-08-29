SOURCES =  $(wildcard *.md)
SOURCES += $(wildcard *.py)
SOURCES += $(wildcard static/*.html)
SOURCES += $(wildcard static/*.js)
SOURCES += $(wildcard static/*.css)


debug: app.py setup
	FLASK_APP=app.py FLASK_ENV=development venv/bin/flask run --host=0.0.0.0

run: app.py setup
	venv/bin/python3 wsgi.py 5000

setup: venv static/vendor

static/vendor:
	mkdir -p $@
	cd $@; wget -q https://unpkg.com/bootstrap@4.1.3/dist/css/bootstrap.min.css
	cd $@; wget -q https://unpkg.com/bootstrap@4.1.3/dist/css/bootstrap.min.css.map
	cd $@; wget -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.css
	cd $@; wget -q https://cdn.jsdelivr.net/npm/vue/dist/vue.js
	cd $@; wget -q https://unpkg.com/babel-polyfill@7.0.0-beta.3/dist/polyfill.min.js
	cd $@; wget -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.js
	cd $@; wget -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.js.map
	cd $@; wget -q https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js
	cd /tmp; wget -q https://use.fontawesome.com/releases/v5.3.1/fontawesome-free-5.3.1-web.zip
	unzip -q -d $@ /tmp/fontawesome-free-5.3.1-web.zip
	rm -f /tmp/fontawesome-free-5.3.1-web.zip

venv: requirements.txt
	python3 -m venv --system-site-package $@
	venv/bin/pip install -r $<
	touch $@

clean:
	rm -r static/vendor
	find . -name __pycache__ | xargs rm -r
	
edit: $(SOURCES)
	rmate $(SOURCES)

ci: Makefile $(SOURCES)
	git add Makefile $(SOURCES)
	git commit
