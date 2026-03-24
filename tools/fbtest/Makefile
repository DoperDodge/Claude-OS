# DRM framebuffer test — build for target or host
#
# Native build:    make
# Cross-compile:   make CROSS_COMPILE=aarch64-linux-gnu-

CC ?= gcc
CROSS_COMPILE ?=
CFLAGS := -Wall -Wextra -O2 $(shell pkg-config --cflags libdrm 2>/dev/null || echo "-I/usr/include/libdrm")
LDFLAGS := $(shell pkg-config --libs libdrm 2>/dev/null || echo "-ldrm")

TARGET := drm_test

.PHONY: all clean

all: $(TARGET)

$(TARGET): drm_test.c
	$(CROSS_COMPILE)$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

clean:
	rm -f $(TARGET)
