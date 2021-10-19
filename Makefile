.PHONY: debug run clean tidy docker

export COMPOSE_FILE=docker-demo/docker-compose.yml

ifeq (${BASE_DN},)
export BASE_DN=dc=flintstones,dc=com
export BIND_DN=cn=Fred Flintstone,ou=People,dc=flintstones,dc=com
export BIND_PASSWORD=yabbadabbado
endif

debug: app.py .venv3
	QUART_APP=$< QUART_ENV=development \
		.venv3/bin/python3 .venv3/bin/quart run

run: .venv3
	.venv3/bin/hypercorn -b 0.0.0.0:5000 app:app

.venv3: requirements.txt
	[ -d $@ ] || python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install -U pip wheel
	.venv3/bin/pip3 install -r $<
	touch $@

ldap: docker-demo/data/flintstones-data.ldif
	docker-compose up -d ldap

docker-demo/data/flintstones-data.ldif: docker-demo/flintstones.ldif
	mkdir -p docker-demo/data
	cp $< $@
	
clean:
	rm -rf docker-demo/data __pycache__

tidy: clean
	rm -rf .venv3

docker: tidy
	docker build -t dnknth/ldap-ui .
	docker push dnknth/ldap-ui
