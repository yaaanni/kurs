# Makefile - сборка программы сравнения производительности процессоров
#
# Ключи -march=x86-64 -mtune=generic обеспечивают формирование машинного кода,
# не содержащего инструкций, специфичных для конкретной микроархитектуры.
# Ключ -static включает статическую компоновку: исполняемый файл не зависит
# от версий системных библиотек целевой машины. Благодаря этому один и тот же
# файл запускается на обеих вычислительных системах без повторной компиляции,
# а исполняемый машинный код на них байт-идентичен.

CC      = gcc
CFLAGS  = -std=c11 -O2 -march=x86-64 -mtune=generic -Wall -Wextra -pedantic
LDFLAGS = -static -pthread -lm

SRCDIR  = src
OBJDIR  = build
TARGET  = fibbench

SOURCES = $(SRCDIR)/main.c $(SRCDIR)/fib.c $(SRCDIR)/timer.c \
          $(SRCDIR)/stats.c $(SRCDIR)/sysinfo.c $(SRCDIR)/report.c
OBJECTS = $(patsubst $(SRCDIR)/%.c,$(OBJDIR)/%.o,$(SOURCES))

all: $(TARGET)

$(TARGET): $(OBJECTS)
	$(CC) $(OBJECTS) -o $@ $(LDFLAGS)
	@sha256sum $@ | awk '{print $$1}' > $@.sha256
	@echo "контрольная сумма: $$(cat $@.sha256 | cut -c1-16)..."

$(OBJDIR)/%.o: $(SRCDIR)/%.c | $(OBJDIR)
	$(CC) $(CFLAGS) -c $< -o $@

$(OBJDIR):
	mkdir -p $(OBJDIR)

clean:
	rm -rf $(OBJDIR) $(TARGET) $(TARGET).sha256

.PHONY: all clean
