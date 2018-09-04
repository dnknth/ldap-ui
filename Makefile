SOURCES =  $(wildcard *.md)
SOURCES += $(wildcard *.py)
SOURCES += $(wildcard static/*.html)
SOURCES += $(wildcard static/*.js)
SOURCES += $(wildcard static/*.css)


debug: app.py setup
	FLASK_APP=app.py FLASK_ENV=development .venv3/bin/flask run --host=0.0.0.0

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
	cd $@; wget -c -q https://code.getmdl.io/1.3.0/material.teal-orange.min.css
	cd $@; wget -c -q https://code.getmdl.io/1.3.0/material.min.js
	cd $@; wget -c -q https://code.getmdl.io/1.3.0/material.min.js.map
	#
	cd $@; wget -c -q https://cdn.jsdelivr.net/npm/vuetify/dist/vuetify.min.css
	cd $@; wget -c -q https://cdn.jsdelivr.net/npm/vuetify/dist/vuetify.min.js
	#
	# cd $@; wget -c -q https://ajax.googleapis.com/ajax/libs/jquery/3.3.1/jquery.min.js
	#
	mkdir -p $@/fonts
	cd /tmp; wget -c -q https://use.fontawesome.com/releases/v5.3.1/fontawesome-free-5.3.1-web.zip
	unzip -q -o -d $@/fonts /tmp/fontawesome-free-5.3.1-web.zip
	rm -f /tmp/fontawesome-free-5.3.1-web.zip
	#
	cd /tmp; wget -c -q -O /tmp/mdi-fonts.zip https://github.com/Templarian/MaterialDesign-Webfont/archive/master.zip
	unzip -q -o -d $@/fonts /tmp/mdi-fonts.zip
	rm -f /tmp/mdi-fonts.zip
	#
	mkdir -p $@/fonts/roboto
	wget -c -q -O /tmp/roboto.zip 'https://google-webfonts-helper.herokuapp.com/api/fonts/roboto?download=zip&subsets=latin&variants=300,500,700,regular&formats=woff,woff2'
	unzip -q -o -d $@/fonts/roboto /tmp/roboto.zip
	rm -f /tmp/roboto.zip

.venv3: requirements.txt
	python3 -m venv --system-site-packages $@
	.venv3/bin/pip install -r $<
	touch $@

clean:
	rm -rf static/vendor
	find . -name __pycache__ | xargs -r rm -r
	
tgz:
	tar -czvf ../ldap-ui.tgz --exclude=.git --exclude-from=.gitignore .
	
edit: $(SOURCES)
	rmate $(SOURCES)

ci: Makefile $(SOURCES)
	git add Makefile $(SOURCES)
	git commit
