.PHONY: push

push:
	docker pull alpine
	docker buildx build --push \
		--platform linux/amd64,linux/arm64 \
		-t dnknth/ldap-demo .
