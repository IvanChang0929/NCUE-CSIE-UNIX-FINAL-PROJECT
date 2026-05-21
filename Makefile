CC = gcc
CFLAGS = -Wall -Wextra -O2 -Isandbox/include 

SRC_SANDBOX = \
	sandbox/src/sandbox.c \
	sandbox/src/payload.c \
	sandbox/src/result_writer.c \
	sandbox/src/limit.c \
	sandbox/src/namespace.c \
	sandbox/src/filesystem.c \
	sandbox/src/seccomp.c

TARGET_SANDBOX = sandbox/build/sandbox

all: $(TARGET_SANDBOX) 

$(TARGET_SANDBOX): $(SRC_SANDBOX)
	mkdir -p sandbox/build
	$(CC) $(CFLAGS) $(SRC_SANDBOX) -o $(TARGET_SANDBOX) -lseccomp

worker: all
	@echo "[System] Starting Sandbox Worker Polling Loop..."
	python3 sandbox/worker.py

run: all
	@echo "[System] Executing single manual sandbox test with ID: test_job..."
	sudo ./$(TARGET_SANDBOX) test_job

clean:
	@echo "[System] Cleaning up build and dynamic container folders..."
	sudo rm -rf sandbox/build
	sudo rm -rf sandbox/tmp/job_*
	sudo rm -rf sandbox/containers/job_*
	sudo rm -rf sandbox/result/job_*
	sudo rm -rf /tmp/sandbox/job_*

clean-all: clean
	@echo "[System] Deep cleaning... Removing base_rootfs template..."
	sudo rm -rf sandbox/images

.PHONY: all clean clean-all run worker