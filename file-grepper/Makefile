hello:
	echo "Hello"


build:
	echo "Building file-grepper"
	mkdir -p ./bin
	go build -o ./bin/file-grepper ./cmd/file-grepper/main.go
	ls -la ./bin/file-grepper

fmt:
	echo "Formatting the go project"
	go fmt ./...

vet:
	echo "Vetting the go project"
	go vet ./...

lint:
	echo "Linting the go project"
	go lint ./...

test:
	echo "Running unit tests for file-grepper"
	go test  -v ./internal

run: build
	echo "Build Completed, Running"
	./bin/file-grepper

clean:
	rm ./bin/file-grepper
	go clean
