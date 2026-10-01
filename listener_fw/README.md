# Listener firmware (M2, ESP32), v0.4

Firmware for M2, the ESP32-DevKitC module on the listener board
(`listener_hw`, block 8). It plays music from a phone into the MOST ring
and is the listener's host.

What it does now:

- **Bluetooth A2DP sink** "MOST BT audio": Secure Simple Pairing with no
  PIN ("just works"), PIN 0000 for an old phone. It offers AAC-LC (what an
  iPhone sends) and SBC, both at 44.1 and 48 kHz only, and the phone picks.
  The stack hands the media packets over as they came; `main/a2dp_dec.c`
  queues them to a task on core 1 that decodes them with Espressif's
  esp_audio_codec (from the component registry; the build fetches it into
  `managed_components/`). SBC runs with packet loss concealment.
- **I2S out on the listener's clocks**: the ESP32's I2S port is a slave on
  BCLK and LRCK from the FPGA (64 Fs, locked to the ring), so every sample
  lands in a ring frame. Format as the listener's DIN takes it: I2S, 32-bit
  slots, the sample in the top 24 bits.
- **The phone's pace onto the ring's** (`components/ratematch`): a ring buffer,
  a 64-tap polyphase resampler, and a slow PI loop on the buffer's fill. The
  phone's clock and the ring's differ by up to a few hundred ppm, and the
  rates themselves may differ (44.1 kHz from the phone into a 48 kHz ring, or
  back). No ASRC chip: every Bluetooth sink has to match the phone's pace to
  some clock anyway; here that clock is the ring's.
- **The host** (`main/host.c`, `components/mostctl`): control blocks from the
  FPGA's UART, decoded into MOST telegrams; a model of what the amplifier is
  told; from it the commands to the FPGA - our audio into the AUX source's
  frame bytes (02), the amplifier's main zone out on J3 (01) with the head
  unit's volume, mute, balance, bass, treble and loudness (03), and two more
  of its sinks - navigation, phone, chimes - mixed in at their own levels.
  Never a word on the MOST control channel: the listener has no address.
- **The board's TOSLINK input as the second source**, chosen by itself
  (`components/mostctl/ain`): the phone while it streams, otherwise the
  TOSLINK input once its receiver has held lock on PCM for 1 s (IO13 reads the
  DIR9001's ERROR pin, IO27 its AUDIO pin; both pulled up, so a board without
  the receiver never injects from it). Command 02 then names DIN2 - the S/PDIF
  receiver's output through the board's sample-rate converter, on the same
  ring-locked clocks. A parity error's blip on ERROR is no reason to let go;
  the input is lost after 100 ms of ERROR with no lock between (the receiver
  sends zeros while unlocked, so that tail is silence). AUDIO high - AC-3 or
  DTS, which the DIR9001 passes on untouched and the car would get as
  full-scale noise - drops it at the first reading, and the console says to
  set the source to PCM. Its lock time runs while the phone plays, so when the
  phone stops the TOSLINK input takes over at once.
- **The steering wheel's track keys to the phone** (Jaguar XF;
  `components/mostctl/wheel`, `main/phone_ctl.c`): while the phone's audio is
  in the AUX bytes, next and previous on the wheel skip the phone's tracks
  (AVRCP); otherwise the keys stay the car's - the radio, the CD and the USB
  module act on them as before.

Next: the per-car scales from a recording of a real ring.

## Pins (listener board, block 8)

| ESP32 | DevKitC pad | Net | |
|---|---|---|---|
| IO22 | 22 | I2S_BCLK_F | in, the ring's BCLK |
| IO23 | 21 | I2S_LRCK_F | in |
| IO21 | 25 | I2S_DIN_F (through R21) | out, our audio |
| IO4 | 32 | UART_TX_F | in, control blocks, 3 Mbaud |
| IO13 | 15 | OPT_ERR | in, the S/PDIF receiver's ERROR: 1 = no lock or a parity error |
| IO27 | 11 | OPT_NPCM | in, the S/PDIF receiver's AUDIO: 1 = not PCM (board v1.3) |
| IO15 | 35 | UART_RX_F (through R20) | out, host commands, 3 Mbaud |

All but OPT_ERR and OPT_NPCM sit on the DevKitC's row next to the FPGA module,
each opposite the FPGA pin it meets (board v1.2). IO15 is a strapping pin (MTDO);
the FPGA's pull-up on UART_RX holds it high through reset, which is what
the ESP32 expects there.

The console (UART0, the DevKitC's USB port) runs at 921600 baud, for the
telegram trace; `idf.ps1 monitor` takes the rate from the configuration.

## The loop in `ratematch`

The fill is taken at its upper envelope - the highest value in each 2 s -
because A2DP packets come late, never early: right after the least late
packet the fill is the true balance of what the phone sent against what the
ring took, while the mean carries the packet jitter. The envelope is
low-passed (10 s); the PI controller (wn = 2 pi x 2.5 mHz, zeta 0.9) trims
the resampler's step. A 200 ppm clock offset moves the buffer by about 5 ms.

Edges: the output fades in and out over 5 ms. If the phone stops, the buffer
runs down, the output fades out and waits for 200 ms of audio again. If the
ring's clocks stop (the Si514 is re-centred, the ring sleeps), the write
waits; the phone keeps sending, the buffer fills and new audio is dropped.
When the clocks come back, what is buffered no longer joins what arrives
next, so it is dropped whole and the output restarts on fresh audio.

## The host

**Link** (`lsn_link`, formats in `lsn_link.h`): one 42-byte packet per
control block from `ctrl_uart.v`, only for a locked, aligned block; 11-byte
commands to `host_cmd.v`. A packet with a wrong XOR costs that block only:
the search for the next A5 5A restarts inside it.

**Telegrams** (`most_msg`, block layout in
`docs/host_control_formats.md`). The CRC cannot be checked (its
polynomial is in no document we have), so a block counts as a telegram only
if everything checkable holds: message type 0x00, target and source in their
address ranges, TelID 0-3, TelLen within 12 (11 to a group address), data not
idle. Segmented messages are put together by source and target; a segment
sent again (a NAKed telegram comes up to 6 times) is skipped, a gap in
MsgCnt or 5 s of silence drops the transfer.

**The model** (`amp_model`): AuxIn (0x24) Allocate / SourceInfo / DeAllocate
give the AUX source's channels; AudioAmplifier (0x22) Connect (StartResult,
then Result) / SinkInfo / DisConnect / Mute give each sink's channels and
state. Ack forms skip their SenderHandle. Every change is idempotent, and a
channel list that is not ascending within 0..59 is ignored.

**Decisions**, sent when they change, at start-up and every 2 s (the FPGA's
injection is off after a core reset; a repeated command changes nothing):

- 02: our audio into the AUX source's frame bytes while an amplifier sink is
  connected to exactly those channels and one of our sources is live: the
  phone while it streams (A2DP started), otherwise the TOSLINK input while its
  receiver holds lock. Otherwise the car's own AUX passes untouched. The bytes are
  swapped on our way out, so only the nodes after the listener hear it: the
  amplifier does only if the listener sits between the AUX source and the
  amplifier, in the direction of the light - on the fiber into the
  amplifier it always does. For listening (J2, J3) any place will do.
- 01: J3 plays the amplifier's sink 1 (the main zone), from the frame as it
  leaves the listener - our audio included while it replaces the AUX source's
  bytes and the amplifier plays them; and on streams 1 and 2 two more of its
  connected sinks (`am_extras`: SinkNr 2 and up on sink 1's amplifier
  instance, lowest first; 2 or 3 channels are 16/24-bit mono, fed to both
  sides, 4 or 6 stereo).
- 03: J3's coefficient set (section below), sent first so that a source is
  never heard at full scale before its gains; while the settings change, at
  most one set every 20 ms, and at once when a sink comes or goes.

No packet for 0.5 s means the ring is down or restarting. A restart hands the
channels out anew, and a model that kept the old ones could put our audio into
another source's bytes before the new Allocate is seen; so the model starts
over and both commands go off. What that costs: if the ESP32 starts while the
ring is already up, it knows nothing until the head unit next connects a
source (it will not ask: the listener has no address). That is the ordinary
cold start, not an exception: the ESP32 is powered with the ring (WAKE), and
whether it is listening before the head unit's first Connect is a race the
head unit usually loses by a few seconds, but not always.

**J3's sound** (`sound`, `dsp_img`). What the amplifier gets on the ring is
the source before any volume; the head unit tells the amplifier the rest.
`sound` collects it from the telegrams. Where the volume travels depends on
the car (`sound.h` has the table): SpeakerLevel 0x22.0x46D in dB (JLR AUD3),
BMW's AudioMaster 0x20.0x200, 0xF0.0x409 byte 2 (Jaguar XF), or the
catalogue's 0x22.0x400; the first of these heard wins. Tone: 0x22.0x200 /
0x202 / 0x203 / 0x201 (balance, bass, treble, loudness), or BMW's 0x20.0x220
/ 0x222 / 0x223. Mute: the amplifier model's main sink (0x113), or volume 0.
`dsp_img` turns that into the FPGA's words (map `dsp_map.h`, generated by
`listener_gw/sim/dsp_asm.py`): a low shelf at 100 Hz for bass plus
loudness, a high shelf at 10 kHz for treble (RBJ, designed in double for the
ring's measured rate, stability checked on the rounded words), and L / R
gains from the volume and balance, gliding at k = 1/256 per frame (~5 ms).
The settings are kept in NVS 10 s after the last change: after a restart J3
starts where it was, as the factory amplifier does. Until a volume has been
heard once, J3 is silent.

The amplifier's other sinks - navigation, phone, chimes: whatever it mixes
into its speakers, under whichever sink numbers a car gives them - go to J3
on streams 1 and 2, so J3 is what the factory amplifier would play and no
per-brand table of which sink is which is needed. Each plays at its own level
where the car sends one: SpeakerLevel to that sink (JLR AUD3, dB), else byte
8 of 0xF0.0x409 (Jaguar XF: navigation and phone), else the volume; then
every sink, sink 1 too, at its MixerLevel on top (0x22.0x467, catalogue 2V4-3
2.1.31: InputLevel, Balance, Fader per sink, the whole array or one sink by
its position; a balance of 0x80 follows the main one). Each is silent while
its own Mute (0x113) is on; the main sink's mute is the main sink's only.
No tone on them, as an amplifier plays prompts. If an amplifier also turns
the music down by itself while a prompt plays, the bus does not say so, and
J3 does not do it.

The scales are placeholders (`snd_cfg_default`) for every car but JLR AUD3,
whose SpeakerLevel carries dB: raw volume -> dB on a square law over an
assumed maximum (BMW 63, known; 40 elsewhere, a guess), 1 dB per bass /
treble step (+-12 dB), 2 dB per balance step with the other side silent from
10 steps, loudness +8 dB of bass at -40 dB and below, 1 dB per MixerLevel
step. A recording of the car's ring while stepping each control fixes them.

**Steering-wheel keys** (`wheel`, `phone_ctl`). On the Jaguar XF the gateway
(0x161) sends the wheel's track keys to the touchscreen (0x16E), which tells
the playing source; with the factory screen in the car they are on the ring.
FktID 0xCA1: next track Data0 0x03 with Data1 0x01, previous Data0 0x04 with
Data2 0x01 - as SocketMost (branch usb), standing in for the screen, acts on
them; it checks nothing else of the telegram, and neither does `wheel`. The
same telegram again within 200 ms counts once (a NAKed one comes up to 6
times), and a different one in between - a release - ends that. While
command 02 puts the phone into the AUX bytes, a key goes to the phone as an
AVRCP passthrough, Forward or Backward, pressed and released: M2 is the AVRCP
controller, and the phone connects it with the stream. Otherwise the key is
the car's alone, and the console says so. Other cars' keys, if they travel on
the ring at all, are not known yet; the trace shows every telegram, so a
recording while pressing them finds them.

**Capture** (`listener_gw/rtl/capture.v`, command 04): the FPGA keeps the
line's first 65536 runs after power-up - the ring's start-up - and captures
anew or dumps on command. Keys on the console: `c` captures now and dumps
when full, `d` dumps what was captured, `h` help. The dump's 41-byte packets
(sync A5 C5) come on the same UART as the control blocks, in the gaps between
them; `lsn_link` hands them to the host, which collects them (64 KB in PSRAM)
and, when the trailer has come, prints them from the low-priority task:

```text
CAP BEGIN runs=65536 packets=2048 missing=0
CAP 0 <64 hex digits: 32 run lengths in samples of 1.26 ns> <8 hex digits: glitch flags>
CAP 1 ...
CAP 7 -                      (a packet that never came)
CAP END
```

`python tools/capture_analyse.py console.log` turns that into the UI and the
ring's rate, every frame, the preamble patterns and the one that marks a
block, the parity rule, the frame control bits, the boundary descriptor and
the pulse-width distortion. Record the console at 921600 baud with timestamps;
a dump takes about 2 s to print.

**Trace**: every telegram goes to the console, e.g.
`0001F2A0 0100>0180 22.01.111 SetGet/StartResult [6] 01 00 08 09 0A 0B` -
frame, source > target, FBlock.Inst.FktID, OPType, length, data. A
low-priority task prints them; when the console falls behind, lines are
dropped and counted, never UART bytes. A status line every 10 s counts
packets, bad packets, blocks lost in the FPGA, telegrams, refused blocks and
dropped transfers.

## Build

ESP-IDF v6.1. From PowerShell, `idf.ps1` sets up the environment itself
(ESP-IDF in `~\toolchains\esp-idf`, its tools in `~\toolchains\espressif`,
unless IDF_PATH / IDF_TOOLS_PATH say otherwise):

```text
.\idf.ps1 set-target esp32
.\idf.ps1 build
.\idf.ps1 -p COM5 flash monitor
```

## Tests

Host tests of `ratematch` and `mostctl` (gcc with C11 atomics; the last
step needs Python):

```text
make -C test
```

1. The resampler alone: a sine in the buffer read at random fractional
   positions, against the exact sine.
2. The whole path in simulated ring time, 600 s: a phone whose clock is off
   by -200, 0 or +200 ppm sends 1024-frame packets up to 40 ms late with a
   70 ms hold every 10 s; the I2S side pulls 240-frame blocks.
3. Events: the phone pauses for 1 s; the ring's clocks stop for 3 s.
4. `test_lsn_link`: packets as `ctrl_uart.v` sends them, with noise between
   them, a corrupted byte, a lost byte and A5 5A inside the payload; capture
   packets among them (one corrupted, a trailer); the command packets byte
   for byte, the inject command from the TOSLINK input among them, J3's
   stream 1 in mono and stream 2 in stereo and off.
5. `test_mostctl`: blocks built to the documented layout. Decoding: fields;
   5 kinds of block refused, system and MOST High Protocol messages skipped;
   11 bytes to a group address; a segmented message with a segment sent
   twice; a lost segment; a transfer left open; two senders interleaved.
   The model: the head unit puts AUX on the amplifier and takes it off in
   every order; the amplifier moves to another source; Ack forms; the state
   rebuilt from SourceInfo / SinkInfo alone; 0xFF lists; lists that make no
   sense; 24 bit; Mute. The other sinks for J3: 16-bit mono and 24-bit
   stereo, the lowest two SinkNr on sink 1's instance, a second instance
   passed over, Mute, DisConnect, a list J3 cannot take passed over, no main
   sink. And the chain, raw blocks to the decision. The
   source (`ain`), read every 10 ms: no receiver; the phone over a locked
   TOSLINK input; the lock's 1 s, run while the phone plays; a parity blip
   and 90 ms of ERROR kept; AC-3 dropped at once, PCM again after 1 s, the
   phone untouched by it; 100 ms of ERROR lost; plugged in again. The
   wheel keys (`wheel`): next and previous; the same telegram again within
   200 ms once, after 200 ms of quiet a new press, a release between ending
   that; 04 01 00, another FktID and one byte no key; across the frame
   counter's wrap; and a raw block 0161 > 016E, sent twice.
6. `test_sound`: every volume source and their order, tone and loudness
   telegrams, Increment ignored, repeats no change; the other sinks' levels -
   MixerLevel for every sink and for one, a record's field (y) ignored, its
   balance or the main one, Jaguar XF's byte 8, SpeakerLevel to a sink over
   both, a sink beyond 8; the coefficient words for flat tone, volume, balance
   (to one side, to silence), mute, clamps, streams 1 and 2 (a level, muted,
   the main balance or their own, off); both shelves at -12..+12 dB at 44.1
   and 48 kHz judged on the rounded words.
7. `check_image.py`: two sets from `test_sound` run through the FPGA engine's
   bit-exact model (`listener_gw/sim/dsp_asm.py`): volume -20 dB, balance
   +4, bass +6, treble -4 with sines at 50 Hz, 1 kHz and 12 kHz; and three
   sinks mixed - sink 1 at -20 dB, sink 2 on stream 1 in mono at -10 dB,
   sink 3 on stream 2 at -26 dB with a balance of its own - a sine on each.

## Verified

| Check | Result |
|---|---|
| Resampler SNR, 1/10/15 kHz, all four rate pairs (44.1/48 either way) | 90.0-93.0 dB (the 16-bit input's limit) |
| 48 -> 44.1 kHz, a 23 kHz tone (would fold to 21.1 kHz) | -90.7 dB |
| Loop settles at the phone's offset (-200/0/+200 ppm, 3 rate pairs) | within 3 ppm |
| Pitch wander (sd of the step correction) | 8-15 ppm |
| Tone over the last 100 s against the phone's | within 7 ppm |
| Fill, target 200 ms | 72-235 ms; no underflow, skip or drop |
| Largest sample step (clicks) | as the tone's own slope |
| Phone pauses 1 s | one fade out, silence, fade in |
| Ring clocks stop 3 s | one backlog dropped, back to 194 ms, no click |
| UART link: 6 packets after noise, one with a flipped bit, one short of a byte, A5 5A inside each | the 4 intact ones, byte by byte and in one call; the packet right after the short one survives |
| Telegram decoding, 23 blocks (see test 5) | 6 telegrams out, 5 blocks refused; the gapped and the stale transfer dropped |
| Model: AUX on and off in every order, Ack forms, Info recovery, 24 bit | each decision as expected |
| The source: phone and TOSLINK input, lock, settle, blips, not PCM, loss | each pick as expected; seven broken variants of `ain.c` each caught |
| Sound settings from telegrams: 4 volume sources, tone, loudness, balance | each as sent; the source order holds |
| The other sinks: which ones, their levels, balance and mute | each as expected; eight broken variants of `amp_model.c`, `sound.c` and `dsp_img.c` each caught |
| Steering-wheel keys: next, previous, a NAKed telegram sent again, a release, other layouts | each as expected; eight broken variants of `wheel.c` each caught |
| Shelves on the rounded words, -12..+12 dB, 44.1 and 48 kHz | full gain within 0.008 dB (15 Hz, 0.45 fs), the other band within 0.001 dB; every setting stable |
| The firmware's set through the FPGA engine's model | L and R within 0.0002 dB of volume + balance + shelves at 50 Hz, 1 kHz, 12 kHz |
| Three sinks mixed, through the same model | every sink's sine on L and R within 0.0003 dB of its level and balance, the mono one on both sides |
| Firmware build, ESP-IDF v6.1, esp32, with AAC, SBC, AVRCP, the host and J3's sound | no compiler warnings; app 983 KB of a 1.5 MB partition (4 MB flash) |

Not proved: nothing has run on an ESP32 yet, and the decoder has never seen
a real control block - which blocks the checks let through, whether the
car's AUX and amplifier say what the MOST documents say, and the scales of
J3's sound, only a car shows.
