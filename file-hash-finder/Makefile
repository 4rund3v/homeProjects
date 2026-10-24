APP_EXECUTABLE       = file-deduper
APP_BIN_PATH         = ./bin
APP_EXECUTABLE_PATH  = ${APP_BIN_PATH}/${APP_EXECUTABLE}


.PHONY: check-quality fmt vet vendor lint tidy build
.DEFAULT_GOAL := build


check-quality: lint fmt vet

fmt:
	go fmt ./...

vet:
	go vet ./...

lint:
# 	golangci-lint run --enable-all

tidy:
	go mod tidy

vendor: tidy
	go mod vendor

build: check-quality  vendor
	mkdir -p ${APP_BIN_PATH}
	go build -o ${APP_EXECUTABLE_PATH} ./cmd/main.go
