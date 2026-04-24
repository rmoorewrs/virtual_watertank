CC = gcc
CFLAGS = -Wall -Wextra -O2
LDLIBS = -lcurl -lcjson
TARGET = controller
SRC = controller.c

.PHONY: all clean

all: $(TARGET)

$(TARGET): $(SRC)
	$(CC) $(CFLAGS) -o $(TARGET) $(SRC) $(LDLIBS)

clean:
	rm -f $(TARGET)
