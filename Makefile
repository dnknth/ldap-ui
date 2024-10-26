.PHONY: debug run clean tidy image push manifest

TAG = latest-$(subst aarch64,arm64,$(shell uname -m))
SITE = backend/ldap_ui/statics

debug: .env .venv3 $(SITE)
	.venv3/bin/uvicorn --reload --port 5000 ldap_ui.app:app

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
	.venv3/bin/twine upload dist/*

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
	docker build --no-cache -t dnknth/ldap-ui:$(TAG) .

push: image
	docker push dnknth/ldap-ui:$(TAG)

manifest:
	docker manifest create \
		dnknth/ldap-ui \
		--amend dnknth/ldap-ui:latest-x86_64 \
		--amend dnknth/ldap-ui:latest-arm64
	docker manifest push --purge dnknth/ldap-ui
	docker compose pull
