SOURCES =  $(wildcard *.md)
SOURCES += $(wildcard *.py)
SOURCES += $(wildcard static/*.html)
SOURCES += $(wildcard static/*.js)
SOURCES += $(wildcard static/*.css)

export BASE_DN = dc=scheer-group,dc=com
export LOGIN_ATTR = cn


debug: app.py setup
	FLASK_APP=app.py FLASK_ENV=development \
		.venv3/bin/flask run --host=0.0.0.0

run: app.py setup
	.venv3/bin/python3 wsgi.py 5000

shell: app.py
	.venv3/bin/python3 -i $<
	
setup: .venv3 static/vendor

static/vendor:
	mkdir -p $@
	cd $@; wget -c -q https://unpkg.com/babel-polyfill@7.0.0-beta.3/dist/polyfill.min.js
	cd $@; wget -c -q https://cdn.jsdelivr.net/npm/vue/dist/vue.js
	cd $@; wget -c -q https://cdn.jsdelivr.net/npm/vue/dist/vue.min.js
	#
	cd $@; wget -c -q https://unpkg.com/bootstrap@4.1.3/dist/css/bootstrap.min.css
	cd $@; wget -c -q https://unpkg.com/bootstrap@4.1.3/dist/css/bootstrap.min.css.map
	cd $@; wget -c -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.min.css
	cd $@; wget -c -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.min.js
	cd $@; wget -c -q https://unpkg.com/bootstrap-vue@2.0.0-rc.11/dist/bootstrap-vue.min.js.map
	#
	#
	mkdir -p $@/fonts
	cd /tmp; wget -c -q https://use.fontawesome.com/releases/v5.3.1/fontawesome-free-5.3.1-web.zip
	unzip -q -o -d $@/fonts /tmp/fontawesome-free-5.3.1-web.zip
	rm -f /tmp/fontawesome-free-5.3.1-web.zip

.venv3: requirements.txt
	python3 -m venv $@
	.venv3/bin/pip3 install -r $<
	touch $@

clean:
	rm -rf __pycache__ static/vendor
	
edit: $(SOURCES)
	rmate $(SOURCES)

ci: Makefile $(SOURCES)
	git add Makefile $(SOURCES)
	git commit

docker: clean
	docker build -t dnknth/ldap-ui .
