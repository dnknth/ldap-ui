.PHONY: debug run clean tidy docker

debug: app.py settings.py .env .venv3 dist
	QUART_APP=$< QUART_ENV=development \
		.venv3/bin/python3 .venv3/bin/quart run

run: app.py settings.py .env .venv3 dist
	.venv3/bin/hypercorn -b 0.0.0.0:5000 --access-logfile - app:app

.env: env.example
	cp $< $@

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install -U pip wheel
	.venv3/bin/pip3 install -r $<
	touch $@

dist: package.json
	npm install
	npm run build

clean:
	rm -rf dist __pycache__

tidy: clean
	rm -rf .venv3 node_modules

image: clean
	docker build -t dnknth/ldap-ui .

push: image
	docker push dnknth/ldap-ui
