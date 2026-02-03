.PHONY: clean debug deploy image manifest push pypi tidy 

SITE = backend/ldap_ui/statics
VERSION = $(shell fgrep __version__ backend/ldap_ui/__init__.py | cut -d'"' -f2)
IMAGE = dnknth/ldap-ui

debug: $(SITE) .env
	DEBUG=true uv run ldap-ui --reload --port 5000

.env: env.demo
	cp $< $@

dist: clean $(SITE)
	uv build

pypi: dist
	- uv publish dist/*

deploy: clean $(SITE)
	rsync -a --delete $(SITE)/ mx:/opt/ldap-ui/venv/lib/python3.12/site-packages/ldap_ui/statics/

$(SITE): node_modules
	pnpm audit
	pnpm run build

node_modules: package.json
	pnpm install
	touch $@

clean:
	rm -rf build dist $(SITE) backend/ldap_ui.egg-info
	-find backend -name __pycache__ -exec rm -rf {} \;

tidy: clean
	rm -rf .venv node_modules

# See: https://docs.docker.com/build/building/multi-platform/#multiple-native-nodes
push:
	docker buildx build --push \
		--platform linux/amd64,linux/arm64 \
		-t $(IMAGE):$(VERSION) -t $(IMAGE):latest .
	# docker pushrm $(IMAGE)
