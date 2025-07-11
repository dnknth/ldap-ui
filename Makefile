.PHONY: clean debug deploy image manifest push pypi tidy 

SITE = backend/ldap_ui/statics
VERSION = $(shell fgrep __version__ backend/ldap_ui/__init__.py | cut -d'"' -f2)
TAG = $(VERSION)-$(subst aarch64,arm64,$(shell uname -m))
IMAGE = dnknth/ldap-ui

debug: $(SITE)
	DEBUG=true uv run uvicorn --reload --port 5000 ldap_ui.app:app

.env: env.example
	cp $< $@

dist: clean $(SITE)
	uv run python -m build --wheel

pypi: dist
	- uv run twine upload dist/*

deploy: clean $(SITE)
	rsync -a --delete $(SITE)/ mx:/opt/ldap-ui/venv/lib/python3.12/site-packages/ldap_ui/statics/

$(SITE): node_modules
	npm audit
	npm run build

node_modules: package.json
	npm install
	touch $@

clean:
	rm -rf build dist $(SITE) __pycache__

tidy: clean
	rm -rf .venv node_modules

image:
	docker build --no-cache -t $(IMAGE):$(TAG) .

push: image
	docker push $(IMAGE):$(TAG)
	- docker pushrm $(IMAGE)

manifest:
	docker manifest create \
		$(IMAGE) \
		--amend $(IMAGE):$(VERSION)-x86_64 \
		--amend $(IMAGE):$(VERSION)-arm64
	docker manifest push --purge $(IMAGE)
	docker compose pull
