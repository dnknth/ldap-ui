.PHONY: debug run setup clean tidy docker


debug: app.py setup
	QUART_APP=app.py QUART_ENV=development \
		.venv3/bin/python3 .venv3/bin/quart run

run: app.py setup
	.venv3/bin/hypercorn -b 0.0.0.0:5000 app:app

setup: .venv3

.venv3: requirements.txt
	python3 -m venv --system-site-packages $@
	.venv3/bin/pip3 install wheel
	.venv3/bin/pip3 install -r $<
	touch $@

clean:
	rm -rf __pycache__

tidy: clean
	rm -rf .venv3

docker: clean
	docker build -t dnknth/ldap-ui .
