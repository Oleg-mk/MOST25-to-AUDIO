# Host tests for the portable parts of the listener firmware.
#   make        build and run
# Needs a C11 compiler with <stdatomic.h> (gcc).
CC ?= cc
CFLAGS ?= -std=gnu11 -O2 -Wall -Wextra -Werror
RM = ../components/ratematch
MC = ../components/mostctl

all: run

test_rate_match: test_rate_match.c $(RM)/rate_match.c $(RM)/include/rate_match.h
	$(CC) $(CFLAGS) -I$(RM)/include -o $@ test_rate_match.c $(RM)/rate_match.c -lm

test_lsn_link: test_lsn_link.c $(MC)/lsn_link.c $(MC)/include/lsn_link.h
	$(CC) $(CFLAGS) -I$(MC)/include -o $@ test_lsn_link.c $(MC)/lsn_link.c

test_mostctl: test_mostctl.c $(MC)/most_msg.c $(MC)/amp_model.c $(MC)/include/most_msg.h $(MC)/include/amp_model.h
	$(CC) $(CFLAGS) -I$(MC)/include -o $@ test_mostctl.c $(MC)/most_msg.c $(MC)/amp_model.c

test_sound: test_sound.c $(MC)/sound.c $(MC)/dsp_img.c $(MC)/include/sound.h $(MC)/include/dsp_img.h $(MC)/include/dsp_map.h
	$(CC) $(CFLAGS) -I$(MC)/include -o $@ test_sound.c $(MC)/sound.c $(MC)/dsp_img.c -lm

run: test_rate_match test_lsn_link test_mostctl test_sound
	./test_rate_match
	./test_lsn_link
	./test_mostctl
	./test_sound
	python check_image.py

clean:
	rm -f test_rate_match test_rate_match.exe test_lsn_link test_lsn_link.exe test_mostctl test_mostctl.exe \
	      test_sound test_sound.exe image_example.txt

.PHONY: all run clean
