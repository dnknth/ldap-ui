.PHONY: debug run clean tidy docker

export COMPOSE_FILE=docker-demo/docker-compose.yml


debug: app.py .env .venv3 dist
	QUART_APP=$< QUART_ENV=development \
		.venv3/bin/python3 .venv3/bin/quart run

run: app.py .venv3 dist
	.venv3/bin/hypercorn -b 0.0.0.0:5000 --access-logfile - app:app

.env: docker-demo/env.demo
	cp $< $@

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install -U pip wheel
	.venv3/bin/pip3 install -r $<
	touch $@

dist: package.json
	npm install
	npm run build

ldap: docker-demo/data/flintstones-data.ldif
	docker-compose up -d ldap

docker-demo/data/flintstones-data.ldif: docker-demo/flintstones.ldif
	mkdir -p docker-demo/data
	cp $< $@
	
clean:
	rm -rf docker-demo/data __pycache__

tidy: clean
	rm -rf .venv3 dist node_modules

image: clean
	docker build -t dnknth/ldap-ui .

push: image
	docker push dnknth/ldap-ui
