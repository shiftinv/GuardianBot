all:
	docker build \
		--build-arg "GIT_COMMIT=$(shell git rev-parse --short HEAD)" \
		-t shiftinv/guardianbot \
		.

.PHONY: all
