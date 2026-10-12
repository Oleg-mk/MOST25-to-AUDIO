# Sources

This page lists where the project's knowledge of MOST25, of the cars' messages on the ring and of the
parts comes from. No code or design files were copied from any of these sources. Projects without a
licence were only read.

The MOST specifications are the MOST Cooperation's copyrighted documents and are not in this
repository. The code cites them by section, so a reader with access can check every number.

## The cars' messages on the ring

Each car's row in [docs/vehicle_survey.md](docs/vehicle_survey.md) names its own sources and how
sure each fact is; [docs/control_commands.md](docs/control_commands.md) does the same for the
control commands per brand.

| Source | What was taken from it |
|---|---|
| Rhys Morgan, **JLR-HU** ([github.com/rhysmorgan134/JLR-HU](https://github.com/rhysmorgan134/JLR-HU)), **SocketMost**, `usb` branch ([github.com/rhysmorgan134/SocketMost](https://github.com/rhysmorgan134/SocketMost)), **pymost-client** ([github.com/rhysmorgan134/pymost-client](https://github.com/rhysmorgan134/pymost-client)); no licence, read only | Jaguar's and Land Rover's node addresses (0x161 gateway, 0x180 audio unit, 0x186 amplifier, 0x16E screen); the amplifier as FBlock 0x22, instance 0x05, sink 1, switched by DisConnect 0x112 and Connect 0x111; the gateway's 0xF0.0x409 Status with the audio level in byte 2, navigation and phone in byte 8 and the parking sensors in byte 10; source switching through 0xF0.0x405 to 0x408 with AUX as FBlock 0x24; the steering wheel's track keys, 0xCA1 to the screen; that an OS8104 filters control messages by address, which is why the listener decodes them in the FPGA. The byte positions come from one parser and still need a recording to confirm them. |
| mObridge, *MOST25 DA Series Guide*, pp. 18-19 | Which of the amplifier's sinks carries what: phone, navigation and voice on sink 2, the parking sensors on sink 3, the chimes on sink 4, by maker. |
| smartgauges, **usb2most** ([github.com/smartgauges/usb2most](https://github.com/smartgauges/usb2most)), GPL-3.0, and its author's posts on drive2.ru | A USB-to-MOST adapter with an OS8104A that has been used in cars. Its v3 schematic is the precedent for the optical front end: the TE FOT header, series resistors, Rext. Its firmware, published as binaries, was read for its Jaguar and Land Rover tables: 0x22.0x46D SpeakerLevel as the volume on Freelander 2 and the AUD3 amplifiers. |
| BMW technical training manuals (archive.org, *BMWTechnicalTrainingDocuments*: ST042, ST046, ST402, ST502, ST811, ST1501); BMW diagnostic data as text ([github.com/emdzej/ediabasx-docs-sgbd](https://github.com/emdzej/ediabasx-docs-sgbd)) | BMW's rings at 44.1 kHz; the volume sent as AudioMaster 0x20, FktID 0x200. |
| Audi self-study programmes SSP 274, 286, 293, 326, 435, 970103, 970143 | Audi's MMI rings at 44.1 kHz. |
| Mercedes-Benz USA, StarTuned, *Fiber Optics: D2B and MOST Bus* (09/2021); w220.wiki; Dynavin MOAGW sheet; Audison bit DMI NTG4.x guide | Mercedes' rings and where audio runs on them. |
| Aftermarket manuals: HELIX SDMI25, mObridge K2, the Audison bit DMI compatibility list, Trioma MOST-TosLink 3.0 | Which cars carry audio on the ring; that the protocol unit is the platform and model year, not the brand (Trioma documents 22 amplifier-emulation algorithms). |
| Land Rover LR3 workshop manual (sections 415-01 and 418-00) | The LR3's audio system on MOST. |

## MOST25

| Source | Used for |
|---|---|
| MOST Cooperation, *MOST Specification* Rev. 2.5 (10/2006), with section 2.3.2 for the standard layer | the control frame, the application message service, OPTypes |
| MOST Cooperation, *MOST Specification of Physical Layer* Rev. 1.1 (09/2003), 2.1 and the SP tables | the frame, biphase-mark coding, the SP limits the end-to-end simulation distorts the line to |
| MOST Cooperation, function catalogues *FBlock AudioAmplifier* 2V4-3 and *GeneralFBlock* (oPhy25 2V5-1) | the amplifier's functions the host decodes (Connect, DisConnect, SinkInfo, Volume, Balance, Bass, Treble, Fader, Loudness, SpeakerLevel), their data types, and Mute 0x113 with its sink number |
| A. Grzemba (ed.), *MOST: The Automotive Multimedia Network*: Table 5.1, Fig. 5.11 and 5.12 | the frame's byte map, the control message over 16 frames |
| Oasis SiliconSystems patents by D. Knapp: US 2005/0053179 A1, US 2004/0057542 A1 | the preamble opens with a 3-UI coding violation (the specifications never draw it) |
| Oasis SiliconSystems: EP 1333580 B1, US 6763060 B1 | lock after three valid preambles, unlock after two invalid ones, as the receiver does here |
| IEC 60958-3 | the S/PDIF consumer channel status |
| The clock-recovery parts' makers (Skyworks/Silicon Labs, Renesas, TI, Analog Devices, Microchip, Cirrus Logic), as listed in [docs/research/regen_clock](docs/research/regen_clock) | the choice of the regenerator's clock: an Si514 the FPGA steers, locked to the ring |

## The car's supply

| Source | Used for |
|---|---|
| ISO 16750-2, test B (suppressed load dump); ISO 7637-2, pulses 1, 2a, 3a and 3b | the battery input: the buck's voltage rating, the TVS in front of the reverse-polarity diode, the fuse |

## Parts

| Part | Documents |
|---|---|
| TE 1-1394640-1, MOST pigtail FOT header | TE drawing C-2-2141577-1 rev B; application specification 114-18997 |
| The FOT inside it | Broadcom (Avago) AFBR-1013 data sheet, application note 5344: Rext and the supply filters |
| Sipeed Tang Nano 20K | Sipeed data sheet v1.3 and schematic |
| Gowin GW2AR-18 | data sheet DS226 |
| Espressif ESP32-DevKitC-VIE, ESP32-WROVER-IE | Espressif data sheets and the DevKitC's drawing |
| Skyworks (Silicon Labs) Si514 | data sheet: the I2C registers, the frequency steps |
| TI DIR9001, SRC4192, PCM5102A, OPA1678, TPS60403, LMR38020 | TI data sheets (LMR38020: SNVSC40E) |
| 74LVC1G34, 74LVC1G79, 74LVC1G123, 74LVC1G125, 74LVC1G157 | Nexperia data sheets |
| Cliff FCR684208R and FCR684208T (ORJ-8, OTJ-8), TOSLINK | Cliff's drawings, rev 2 (29/06/23) |
| BKL Electronic 0101153, RCA jack | BKL's drawing |
| Molex Micro-Fit 3.0 43650-0200 | Molex's drawing |

## Related projects

**JLR-MOST-Reader** ([github.com/Oleg-mk/JLR-MOST-Reader](https://github.com/Oleg-mk/JLR-MOST-Reader)) was cut
down from this project for Jaguar and Land Rover: the same receiver, DSP engine, S/PDIF coder and optical
front end with its bypass, re-checked there. Two of its checks compare its decoder and gain tables against
this project's C code.
