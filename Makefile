# ──────────────────────────────────────────────────────────────────────────────
# livetrail-follow — Podman container build & export
# ──────────────────────────────────────────────────────────────────────────────
VERSION    := $(shell grep -oP '__version__ = "\K[^"]+' src/livetrail_follow/__init__.py)
IMAGE_NAME := livetrail-follow
IMAGE_REF  := $(IMAGE_NAME):$(VERSION)

# Runtime config (override with make run CONFIG_FILE=... DATA_DIR=...)
CONFIG_FILE ?= config/config.example.yml
DATA_DIR    ?= $(CURDIR)/data

.DEFAULT_GOAL := help
.PHONY: help build run clean version

## help   : Show this help message
help:
	@grep -E '^## ' Makefile | sed 's/^## /  /'

## build  : Build the container image
build:
	podman build \
		--file Containerfile \
		--tag $(IMAGE_REF) \
		.

## run    : Run the container (outbound HTTPS only, no listening port)
run: build
	mkdir -p $(DATA_DIR)
	podman run --rm \
		-v $(CURDIR)/$(CONFIG_FILE):/etc/livetrail-follow/config.yml:ro,z \
		-v $(DATA_DIR):/data:z \
		$(IMAGE_REF)

## version : Print the current version
version:
	@echo $(VERSION)

## clean  : Remove the container image and exported archive
clean:
	-podman rmi $(IMAGE_REF)
	-rm -f $(ARCHIVE)
