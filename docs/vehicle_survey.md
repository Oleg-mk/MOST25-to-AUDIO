# Which cars carry audio on MOST25, and how they control it

Desk research, 2026-09-23. Nothing here has been measured on a car.
Every row carries a confidence label:

- **C** — primary source: OEM training/service manual, OEM diagnostic data,
  the MOST specification, a vendor installation manual, or working code that
  talks to a real car.
- **F** — credible forum report or vendor marketing.
- **I** — inference. Treat as a hypothesis, not a fact.

Gaps are left as gaps. "not found" means searched and not found, not "absent".

## 1 The standard layer (MOST Specification 2V5, §2.3.2)

Read from `MOST-specifications/.../Specification_2V5-0` (core spec, 10/2006),
Tables 2-1, 2-2, 2-3. **C**.

**FBlockID ranges**

| Range | Owner |
|---|---|
| 0x00–0x6F | MOST Cooperation (standard FBlocks, list below) |
| 0x70–0x9F | reserved |
| **0xA0–0xC7, 0xC9–0xEF** | **System Specific = the carmaker** |
| 0xC8 | reserved |
| **0xF0–0xFB** | **Supplier Specific** (not reported in NetBlock.FBlockIDs) |
| 0xFC | Secondary Node (MOST25 only) |
| 0xFF | all FBlocks in a device |

Note: the MOST Book 2 table puts "Supplier" at 0xFC; the 2V5 spec changelog
explicitly corrected it to 0xF0–0xFB. The spec wins.

**Standard FBlockIDs relevant to audio**: 0x01 NetBlock, 0x02 NetworkMaster,
0x03 ConnectionMaster, 0x04 PowerMaster, 0x05 Vehicle, 0x06 Diagnosis,
0x0F EnhancedTestability, 0x10 HMI, **0x20 AudioMaster**, 0x21 AudioDSP,
**0x22 AudioAmplifier**, 0x23 HeadphoneAmplifier, 0x24 AuxIn,
0x26 MicrophoneInput, 0x28 HandsfreeProcessor, 0x31 AudioDiskPlayer,
0x34 DVDVideoPlayer, 0x40 AmFmTuner, 0x42 TVTuner, 0x43 DABTuner,
0x44 SatRadio, 0x50 Telephone, 0x52 Navigation.

**FktID ranges**: 0x000–0x1FF coordination, 0x200–0x3FF mandatory,
0x400–0x9FF extensions, 0xA00–0xBFF unique,
**0xC00–0xEFF carmaker**, **0xF00–0xFFE supplier**.

So a passive listener can tell from the IDs alone whether a telegram is
standard or proprietary. It cannot tell what a proprietary one means.

**AudioAmplifier 0x22 functions** (FBlock catalogue 2V4-3, **C**):
0x111 Connect `[SinkNr, SrcDelay, ch…]`, 0x112 DisConnect,
0x113 Mute `[SinkNr, Status]` (from GeneralFBlock), 0x200 Balance,
0x201 Loudness, 0x202 Bass, 0x203 Treble, 0x204 Fader (signed bytes),
**0x400 Volume (TUByte)**, 0x402 Subwoofer, 0x441 SpeakerDelay,
0x461 EqualizerSettings, 0x465 MidTones, 0x466 MuteParameters,
0x467 MixerLevel, 0x46D SpeakerLevel. The catalogue fixes the types, not the
ranges or curves ("specified in the application").

**AudioMaster 0x20** is a standard ID, but **no public catalogue of its
functions exists** in the 2V5/3V0 FBlock libraries. Anything using 0x20 is
standard in address, OEM-defined in content.

## 2 Vehicle table

"Audio on MOST" means: is the entertainment audio carried to the amplifier as
synchronous PCM on the ring. It is almost never unconditional: **cars without
the optional external amplifier keep the audio inside the head unit** and the
ring carries little or none of it.

### BMW / MINI / Rolls-Royce

| Car | Years | Bus | Ring rate | Audio on MOST | Standard data seen | Model-specific data | Conf. / source |
|---|---|---|---|---|---|---|---|
| E38/E39/E46/E53, E83 X3, E85 Z4 | –2010 | **none** (I/K-bus) | – | no, analog | – | – | C, BMW training ST052/ST040/E83 |
| E65/E66 7-series (ASK, later CCC) | 2001–08 | MOST25 | **44.1 kHz** | Logic7 only; basic HiFi analog | 0x22 on amp | AudioMaster 0x20 (below); aftermarket boxes exclude E65 | C, ST042 E65 Audio/Bus |
| E60/E61, E63/E64 (M-ASK, CCC, CIC) | 2003–10 | MOST25 | not stated (I: 44.1) | Top-HiFi Logic7 only; CD changer sends direct to amp | 0x22 Bass 0x202/Treble 0x203, GraphEq 0x463 inst 0x02 | 0x20 VolumeActual 0x200, Balance 0x220, Fader 0x221, Bass 0x222, Treble 0x223, AMSD 0x260 | C, ST046 + SGBD MASK60/AMP_60 |
| E81–E93 (RAD2, M-ASK, CCC, CIC) | 2004–13 | MOST25 | CIC: 44.1 (F) | Top-HiFi only; HiFi analog | as above | as above | C (E90 manuals), E8x I |
| E70/E71 X5/X6 | 2006–14 | MOST25 | not stated | Top-HiFi 9-ch only | as above | – | C, E70 Audio Systems |
| E84 X1, E89 Z4 | 2009–16 | MOST | not stated | E89 Top-HiFi is a ring node; E84 unknown | – | – | C (bus), I (audio) |
| F01/F02 7-series (CIC, NBT) | 2008–15 | MOST25 (22.5 Mbit/s ⇒ **44.1 kHz**) | 44.1 | Top-HiFi 10-ch only, 5.1 decoded in amp; HiFi analog (explicit) | volume "for the Top HiFi amplifier" on control channel | – | C, ST811 F01 |
| F10/F20/F30/F15 etc. (CIC, NBT, NBT EVO, EntryNav) | 2010–19 | MOST25 per vendors | not stated | Top-HiFi/HK/B&O; some NBT EVO / EntryNav variants have **no MOST** | – | F25 manual says Top-HiFi amp "has no data bus" — conflicts with vendors | C (variants, HU_MGU), F (rest) |
| G11/G30 etc. (NBT EVO) | 2015–19 | MOST, version not stated | – | yes (B&W amp is a MOST node) | – | – | C (MOST), F (MOST25) |
| G20/G05 (MGU, iDrive 7) | 2018+ | reportedly **none** (Ethernet) | – | – | – | – | F/I |
| MINI R5x / F5x | 2007–20 | unclear | – | unconfirmed | – | – | vendor lists only |
| Rolls-Royce Phantom VII / Ghost | 2003+ / 2009+ | MOST (E65 / F01 derived) | – | Lexicon Logic7: I | – | – | F/I |

### VW group

| Car | Years | Bus | Ring rate | Audio on MOST | Standard data seen | Model-specific data | Conf. / source |
|---|---|---|---|---|---|---|---|
| Audi A8 D3 (MMI 2G, J523) | 2003–09 | MOST25 | **44.1 kHz** | yes, every source straight to amp J525; nav prompts on own sync channel | not found | J523 sends volume/tone/mute to J525 — IDs not published | C, SSP 286 + SSP 293 |
| Audi A6/allroad C6 (MMI 2G) | 2005–08 | MOST25 | 44.1 | **Basic: no** (amp inside J523). Basic Plus and up: yes | not found | – | C, SSP 326 |
| Audi A6/Q7/A4/A5/Q5 (MMI 3G, J794) | 2008–12 | MOST25 | 44.1 | only with external J525 (Bose, B&O); base amp is inside radio R | not found | – | C, SSP 435 |
| Audi A8 D4, A6/A7 C7, Q7 4L… (MMI 3G+) | 2010–16 | MOST25, 22.5 Mbit/s | 44.1 | external amp; base cars need radio recoding (block 56) to put audio on fibre | not found | engineering menu "Central Registry" lists FBlocks — photo not obtained | C (SSP 970103), F (recode) |
| Audi MIB / MIB2 (A3 8V, C7 FL, B9, 4M) | 2013+ | **MOST150** | – | – | – | – | C, SSP 970143 |
| Audi A4/A5/Q5 B8 without MMI | 2008–16 | none (CAN amp) | – | no | – | – | F, conflicting |
| VW Phaeton, Bentley Continental Gen1 | 2002–11 | **no MOST ring** (CAN + analog) | – | no | – | – | C, SSP 274 |
| VW Touareg 7L / 7P | 2003–10 / 2011–18 | 7L: probably none; 7P: MOST (RNS 850, OS81050) | – | 7P: yes (Dynaudio J525) | – | – | F/I |
| Porsche PCM 2.0/2.1/3.0/3.1, CDR-23/24/30/31 (996, 997, 987, 955/957/958, 970, 991.1, 981) | 2003–16 | MOST25 | not stated | yes with Bose/Burmester; **2-channel stereo**, sub and fade derived in the amp | `AudioAmplifier` object in PCM 3.1 firmware | some years also a CAN plug to the amp; **DTCP** code present | F (vendors), C (firmware strings) |
| Porsche PCM 4/5 | 2016+ | MOST150 | – | – | – | – | vendor |
| Lamborghini Aventador | 2011+ | MOST25 | – | yes | – | – | vendor |

### Mercedes-Benz

| Car | Years | Bus | Ring rate | Audio on MOST | Standard data seen | Model-specific data | Conf. / source |
|---|---|---|---|---|---|---|---|
| W220/C215, W210, W163, R170, W203/W209 early, R230 early | 1998–2004 | **D2B**, not MOST | – | digital on D2B | – | – | C, MBUSA StarTuned "D2B and MOST" |
| W220 facelift (COMAND APS NTG1) | 09/2003– | MOST25 | not found | only with option 810 (sound amp); else AGW drives speakers | not found | – | C, WIS copy (w220.wiki) |
| W211/C219/R171 (Audio 20/50, NTG1/2) | 2002–08 | MOST25 (first Mercedes MOST car) | not found | with HK amp. **AGW = tuner + amp + ring master**: tuner audio may never reach the ring | not found | Dynavin drives AGW bass/mid/treble/balance/fader over MOST — IDs not published | C (vendor) |
| W211 FL, W164, X164, W251, R230 FL (NTG2.5) | 2006–12 | MOST25 | not found | HK Logic7 only | not found | – | F/C (vendor) |
| W169/W245 A/B | 2004–12 | MOST25 | not found | HK only; MF2830 Audio 20 has no fibre | – | – | vendor/F |
| W221/C216 (NTG3, 3.5) | 2005–13 | MOST25 | not found | yes; **tuner is inside the amp** | – | aftermarket inject by emulating the TV-tuner node | vendor, I |
| W204/W212/X204/C197/W218 (NTG4) | 2007–11 | MOST25 | not found | only if coded for external amp | – | engineering menu has "MOST FBLOCK Information" page — photo not obtained | C (Audison coding guide) |
| W176/W246/W166/R172/W212 FL (NTG4.5/4.7) | 2011–15 | MOST25 (I) | – | external amp | – | – | I (MOST25-only vendors list them) |
| W222/W205/W213 (NTG5.x) | 2013–19 | **MOST150** optical | – | – | – | – | vendor |
| MBUX (NTG6/7) | 2018+ | MOST150 coax | – | – | – | – | vendor |

The abundance of Mercedes MOST boxes on AliExpress is real, but most of them
convert **RCA → MOST** for an aftermarket head unit, i.e. they act as the head
unit towards the factory amp. They therefore implement the Mercedes amp
control protocol in firmware — it is known, just not published.

### Jaguar Land Rover

| Car | Years | Bus | Ring rate | Audio on MOST | Standard data seen | Model-specific data | Conf. / source |
|---|---|---|---|---|---|---|---|
| Jaguar S-type, X-type, XJ X350/X358 | 1999–2009 | **D2B** | – | – | – | – | F |
| Range Rover L322 | 2002–05 | **none** (BMW I-bus) | – | – | – | – | F |
| Range Rover L322 | MY06–12 | MOST25 | not found | HK Logic7 amp (I) | – | – | F |
| Discovery 3 / LR3 (L319) | 2005–09 | MOST25 | not found | yes, amp "connected via the MOST bus" (high-line only; low-line has no MOST) | – | – | **C**, LR3 workshop manual |
| Discovery 4, RR Sport L320, Evoque, L405/L494, F-type | 2005–~16 | MOST25 | not found | yes (I from shared amp families) | – | – | C/F/vendor |
| **Freelander 2 (L359)** | 2007–14 | MOST25 | **48 kHz** | yes; stereo 4 B, mono 2 B, surround 6 B per frame; base system has no fibre | 0x22: Connect 0x111, SpeakerLevel **0x46D used as volume**, MuteParameters 0x466 per sink | 0x22 FktIDs 0xE04/E05/E07/E08/E53; FBlock 0xF0, 0xF5 | C-code (usb2most firmware), F (drive2) |
| **Jaguar XF X250** | 2008–15 | MOST25 | **48 kHz** | yes, 16-bit stereo | 0x22 inst 0x05 at node 0x186: Balance/Bass/Treble/Fader 0x200–0x204 signed, Subwoofer 0x402, MixerLevel 0x467 | "shadow" amp 0x22 inst **0xA1** at gateway 0x161; 0x22 FktIDs 0xE09 Source, 0xE20–0xE22 CustAudio; **FBlock 0xF0 FktID 0x409 volume** (byte2 audio, byte8 nav/phone, byte10 parking); source switch 0x405→0x408→0x406→0x407; steering-wheel track keys gateway → screen (0x16E), FktID **0xCA1**: next Data0 03 + Data1 01, previous Data0 04 + Data2 01 | C-code (JLR-HU, SocketMost, pymost-client dump) |
| Jaguar XK X150, XJ X351 | 2006–19 | MOST25 | not found | yes (I) | – | – | F/vendor |
| JLR Touch Pro / Duo, I-Pace | ~2017+ | not MOST (Ethernet/coax) | – | – | – | – | vendor, I |

### Volvo, Aston Martin, others

| Car | Years | Bus | Ring rate | Audio on MOST | Standard data seen | Model-specific data | Conf. / source |
|---|---|---|---|---|---|---|---|
| Volvo P3: S80 II, V70 III/XC70, XC60, S60 II/V60 | 2007–18 | MOST (I: MOST25) | not found | yes (F); ICM master, IAM slave; anti-theft pairing of modules | – | – | C (master/slave only), F |
| Volvo XC90 I | 2003–14 | MOST | not found | not stated; HU sets amp EQ over MOST | – | – | F |
| Volvo P1: S40/V50/C30/C70 | 2004–13 | fibre HU→amp, MOST I | – | – | – | – | F |
| Aston Martin DB9/Vantage | 2004+ | MOST | – | yes (Linn amp) | – | – | F |
| Saab 9-3 | MY2003–06 | MOST25 ("O-bus") | not found | yes, "primarily used to send audio… to the amplifiers" | – | – | C, workshop manual text |
| Hyundai Genesis BH, Lexicon navi | ~2009–12 | MOST (I: MOST25) | – | yes: amp has only speaker outs + LWL Tx/Rx, no analog in, no CAN | – | – | C, service pinouts |
| Hyundai/Kia/Genesis 2013+ | – | **none** (S/PDIF + CAN); K900 MOST150 for telematics only | – | – | – | – | C |
| Maserati Quattroporte V | 2004–12 | MOST (I: MOST25) | – | probably, Bose | – | – | F, single vendor |
| Toyota/Lexus ~2012+, GM NGI 2014+ | – | **MOST50 electrical** — not reachable by an optical MOST25 tap | – | – | – | – | C |
| Cadillac 2004–11, Chrysler/Jeep, Nissan, Honda, Mazda, Ford, PSA, Renault | – | no MOST evidence found | – | – | – | – | C/I |

## 2a The best single source on platform differences: Trioma MOST-TosLink

Trioma (RU) MOST-TosLink 3.0 / MOST-RCA installation manual, rev. 28.03.2019,
trioma.ru/instructions/base/instruktsiya-audio-interfejsa-most-toslink-3-0/ —
**C** (vendor manual for a shipping product that talks to all of these rings).

- The adapter selects **1 of 22 algorithms** by jumper. The protocol an amp
  node has to speak differs per platform, not per brand:
  - Mercedes, 4 variants: NTG3/NTG3.5 and AGW (Becker); NTG2.5/NTG4/NTG4.5
    2008+; NTG1 without AGW and NTG2 (pre-2009); NTG1 **with** AGW
    (W211, C219, W220, R171).
  - BMW, 3 variants: E65/E66 (two modes); E/F-series (E60…E93, F01…F34, some
    G); a special E/F mode for chime levels.
  - Audi: MMI 2G/3G with external amp; MMI 3G+ / Lamborghini (amp and tuner
    in one box).
  - Porsche: PCM 2.0/2.1 (to 2009); PCM 3.0 (2009+).
  - Volvo/Land Rover: S80/XC70 to 2012 + Freelander 2; Freelander 2 HSE;
    XC70 2012+ / some S60/V60; S60/V60; XC60 Premium; XC90/S40/V50;
    Discovery 3/4 to 2013 + RRS to 2012; Evoque / RRS 2012+ / Discovery 4 2013+.
  - plus one mode to read a Volvo/LR amp serial number.
- It "extracts the main stereo signal **and** the phone, navigation, parking and
  service signals" and mixes them itself: confirms 3.4.
- It keeps volume, balance, treble, bass and a 5-band EQ from the head unit,
  and fader only on the RCA version: confirms 3.2.
- Output: "44,1(48) kHz 24 bit stereo PCM": both ring rates occur.
- Mercedes AGW (Japan-made) systems: the radio channel **cannot** be routed to
  an external amp. Tuner audio is not on the ring there.
- **Two cases where it coexists with the stock amp instead of replacing it:**
  Mercedes NTG1 with external AGW ("the stock amp stays active and can play
  normally") and Audi MMI 3G+ / VW Touareg NF. In the Audi case, two amps on
  the ring break channel allocation, and the adapter has to watch allocations
  and force re-initialisation. This is the closest any product comes to a
  second listener next to the real amp.
- Volvo/LR **component protection**: the amp serial number is checked. A wrong
  node "stops after 20–40 s or at the next source change". A passive tap is
  not a node, so this should not apply to the listener (I).
- Firmware versions of the cars' own units behave differently ("the problem
  has no universal solution").

SmartGauges (drive2, author of usb2most, Freelander 2):
- "Even within JLR, different models do it differently, so a universal
  solution is hard" (**F**).
- The facelift head unit works **only** with AUD3-xx amps. usb2most had to
  impersonate an AUD3-12 in front of a pre-facelift amp. The protocol changed
  within one model line, around MY2013.
- The pre-facelift amp has OS8104 + NEC V850E + Freescale DSP56371 + WM8770.
- Amps report their FktID list and expose standard SpeakerDelay (0x441) and a
  5-band parametric EQ per channel. The head unit uploads the EQ at power-up.
- Volvo XC90: the head unit edits the amp's PEQ gains (−6…+6 dB) over MOST.

## 3 What this means for a passive listener

1. **Ring rate is not always 48 kHz.** JLR (XF, Freelander 2): 48 kHz, C-code.
   Audi MMI 2G/3G/3G+ and BMW E65/F01: **44.1 kHz** (22.58 Mbit/s), C.
   A listener has to take both: 45.1584 or 49.152 MHz line rate. This one
   does - the receiver learns the UI from the line, and the regenerator's
   clock is centred on the measured rate.
2. **The ring PCM is pre-volume.** Every source agrees (SDMI25 "volume
   controlled signal", mObridge, usb2most proxying SpeakerLevel, Audi SSP 293
   "J523 sends volume to J525"): the head unit sends flat PCM and the amp
   applies volume/balance/fader/tone. A passive tap that only takes PCM plays
   at full scale. **Reading the control channel is mandatory, not optional.**
   Status: strong I from C sources; no car capture proves it.
3. **Volume is rarely standard 0x22/0x400.** Not once was 0x400 seen in a real
   car's data. BMW: AudioMaster 0x20/0x200. JLR: SpeakerLevel 0x46D and/or
   proprietary 0xF0/0x409. Mercedes, VAG, Volvo: unknown. Trioma needs 22
   algorithms for one amp-emulating product (2a), and JLR changed the amp
   protocol within Freelander 2 at the facelift. So the unit is the platform,
   sometimes the model year, not the brand. The volume path needs a
   per-platform decoder table and per-platform scales: configuration.
4. **There is more than one audio stream.** Nav prompts, phone, parking
   beeps, chimes travel on separate sinks/channels to the amp (Audi SSP 293,
   BMW, JLR, mObridge sinks 1–3). A passive tap must decode ConnectionMaster
   Allocate (0x101) results and Amp Connect (0x111) to learn which channel
   bytes are which, and must mix them itself.
5. **No external amp, no audio.** In base-amp cars (Audi MMI basic, BMW HiFi,
   Mercedes without HK, W221/AGW tuner-in-amp) the entertainment audio may
   never be on the ring. The target car's exact amp option decides whether
   a listener can work at all.
6. **DTCP.** Porsche PCM 3.1 carries DTCP code; some sources (probably DVD)
   may be encrypted on the ring. Not verified for any MOST25 car.

## 4 Open, in order of cheapest to close

1. Photos of the engineering-menu FBlock pages: Mercedes NTG4.x "MOST FBLOCK
   Information", Audi MMI 3G "Central Registry". Gives real FBlock/InstID lists
   without any hardware.
2. Firmware of a Chinese RCA→MOST Mercedes box (STM32 + OS8104 class):
   strings/tables give the Mercedes amp protocol, as usb2most did for JLR.
3. Blocked sources, to read through a real browser: drive2 (SmartGauges
   usb2most threads, Mercedes MOST threads), mbworld "COMAND 2.5 reverse
   engineering", rangerovers.net, disco3, jaguarforums, diymobileaudio.
4. L322 2007–10 workshop manual (fuddymuckers, 75.8 MB PDF) — ring master and
   node list for the Range Rover.
5. A capture on the target car: PCM amplitude vs. volume step (proves 3.2),
   and the actual volume telegram.

## 5 Sources worth keeping

- BMW training manuals: archive.org `BMWTechnicalTrainingDocuments`
  (ST042 E65, ST046 E60, ST402/ST502 E90/E70, ST811 F01, ST1501 G12).
- BMW diagnostic data as text: github.com/emdzej/ediabasx-docs-sgbd
  (MASK60, MASK2, CHAMP, CCC*, ASK_E65, AMP_60, AMPT70, ampt07/10, HU_MGU).
- Audi SSP 274, 286, 293, 326, 435, 970103, 970143.
- JLR: github.com/rhysmorgan134/{SocketMost, JLR-HU, pymost-client,
  most-explorer}; github.com/smartgauges/usb2most; LR3 workshop manual
  (workshop-manuals.com, sections 415-01 and 418-00).
- Mercedes: MBUSA StarTuned "Fiber Optics: D2B and MOST Bus" (09/2021);
  w220.wiki (WIS copy); Dynavin MOAGW sheet; Audison bit DMI NTG4.x guide.
- Aftermarket: HELIX SDMI25 manual, mObridge K2 / MOST25 DA manuals,
  Audison bit DMI compatibility list, Trioma MOST-TosLink 3.0 manual.
- drive2.ru, SmartGauges: /c/540082586538475793 (usb2most intro),
  /l/548968564636255384 (amp comparison, EQ/delay data),
  /l/559134374268764551 (facelift ring on a bench), /b/601446880240501339
  (usb2most firmware changelog). drive2 reads fine in a normal browser.
