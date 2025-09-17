build-guard:
	@echo "Building LISA Guard Docker image..."
	docker build -t lisa-guard:latest --target=guard .


build-analyser:
	@echo "Building LISA Analyser Docker image..."
	docker build -t lisa-analyser:latest --target=analyser .

build-test:
	@echo "Building LISA Test Docker image..."
	docker build -t lisa-test:latest --target=test .


run-test: build-test
	@echo "Running LISA Test Docker container..."
	docker run --rm -it -v ${PWD}/apps/server/worker:/app/worker -v ${PWD}/apps/server/tests:/app/tests --env-file ${PWD}/.env.example lisa-test:latest
