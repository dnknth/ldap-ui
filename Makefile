.PHONY: debug run clean tidy image push manifest

ARCH=$(shell uname -m)
TAG=latest-$(ARCH)

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

dist: node_modules
	npm run build

node_modules: package.json
	npm install
	npm audit
	touch $@

clean:
	rm -rf dist __pycache__

tidy: clean
	rm -rf .venv3 node_modules

image: clean
	docker build -t dnknth/ldap-ui:$(TAG) .

push: image
	docker push dnknth/ldap-ui:$(TAG)

manifest:
	docker manifest create \
		dnknth/ldap-ui \
		--amend dnknth/ldap-ui:latest-x86_64 \
		--amend dnknth/ldap-ui:latest-aarch64
	docker manifest push dnknth/ldap-ui
