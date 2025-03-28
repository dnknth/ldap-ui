.PHONY: debug run clean tidy image push manifest

SITE = backend/ldap_ui/statics
VERSION = $(shell fgrep __version__ backend/ldap_ui/__init__.py | cut -d'"' -f2)
TAG = $(VERSION)-$(subst aarch64,arm64,$(shell uname -m))
IMAGE = dnknth/ldap-ui

debug: .venv3 $(SITE)
	DEBUG=true .venv3/bin/uvicorn --reload --port 5000 ldap_ui.app:app

.env: env.example
	cp $< $@

.venv3: pyproject.toml
	[ -d $@ ] || python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install -U build pip httpx twine
	.venv3/bin/pip3 install --editable .
	touch $@

dist: .venv3 $(SITE)
	.venv3/bin/python3 -m build --wheel

pypi: clean dist
	- .venv3/bin/twine upload dist/*

$(SITE): node_modules
	npm audit
	npm run build

node_modules: package.json
	npm install
	touch $@

clean:
	rm -rf build dist $(SITE) __pycache__

tidy: clean
	rm -rf .venv3 node_modules

image:
	docker build --no-cache -t $(IMAGE):$(TAG) .

push: image
	docker push $(IMAGE):$(TAG)
	docker pushrm $(IMAGE)

manifest:
	docker manifest create \
		$(IMAGE) \
		--amend $(IMAGE):$(VERSION)-x86_64 \
		--amend $(IMAGE):$(VERSION)-arm64
	docker manifest push --purge $(IMAGE)
	docker compose pull
