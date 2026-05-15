CC = gcc

CFLAGS = -Wall -Wextra -O2 -Isandbox/include

SRC = \
	sandbox/src/sandbox.c \
	sandbox/src/compiler.c \
	sandbox/src/limit.c \
	sandbox/src/namespace.c

TARGET = sandbox/build/sandbox

all: $(TARGET)

$(TARGET): $(SRC)
	mkdir -p sandbox/build
	$(CC) $(CFLAGS) $(SRC) -o $(TARGET)

worker: $(TARGET)
	@echo "[System] Starting Sandbox Worker Polling Loop..."
	python3 sandbox/worker.py

run: $(TARGET)
	./$(TARGET) sandbox/tmp/test/main.c

clean:
	@echo "[System] Cleaning up build and temporary files..."
	rm -rf sandbox/build
	rm -rf sandbox/tmp/build
	rm -rf sandbox/tmp/job_*

.PHONY: all clean run worker