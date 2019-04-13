export BASE_DN = dc=krachbumm,dc=de

.PHONY: debug run setup clean tidy docker


debug: app.py setup
	FLASK_APP=app.py FLASK_ENV=development \
		.venv3/bin/flask run

run: app.py setup
	.venv3/bin/python3 wsgi.py 5000

setup: .venv3 static/vendor static/node_modules

static/node_modules: static/package.json
	cd static ; npm install
	touch $@

static/vendor:
	mkdir -p $@/fonts
	cd /tmp; wget -c -q https://use.fontawesome.com/releases/v5.3.1/fontawesome-free-5.3.1-web.zip
	unzip -q -o -d $@ /tmp/fontawesome-free-5.3.1-web.zip
	rm -f /tmp/fontawesome-free-5.3.1-web.zip

.venv3: requirements.txt
	python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install -r $<
	touch $@

clean:
	rm -rf __pycache__ static/vendor static/node_modules

tidy: clean
	rm -rf .venv

docker: clean
	docker build -t dnknth/ldap-ui .
