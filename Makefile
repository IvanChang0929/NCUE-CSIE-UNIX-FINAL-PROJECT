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

clean:
	rm -rf sandbox/build
	rm -rf sandbox/tmp/build

run: $(TARGET)
	./$(TARGET) sandbox/tmp/test/main.c

.PHONY: all clean run