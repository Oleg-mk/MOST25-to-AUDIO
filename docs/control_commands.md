# Audio control commands per brand: what we have, what is missing

Desk research and firmware analysis, 2026-09-23. Nothing here has been measured
on a car. Confidence labels as in vehicle_survey.md: **C** primary source or working code,
**F** forum or vendor, **I** inference.

## 1 The short answer

- The listener does not depend on this table. It passes every control block raw
  (`ctrl_uart.v`), whatever its source or destination and whatever the brand.
  A missing entry here only means software cannot yet put a name or a dB value
  on a telegram it already has.
- The standard AudioAmplifier IDs (FBlock 0x22) are used on the wire by a real
  product, not only in the catalogue (section 3).
- What is missing is per-brand: the value-to-dB scales, and OEM IDs for Audi,
  Porsche and Volvo. One recording of a real ring per brand (volume, tone, a
  phone call) fills it. The listener is the tool that makes that recording.

## 2 Firmware sources tried

| Firmware | Result |
|---|---|
| mObridge `.fif` | encrypted — not broken, by decision |
| GROM Volvo `grommost_vols*/volxc*_43.hex` | encrypted (entropy 7.98 throughout) |
| NAV-TV HUR-MB `.enc` | encrypted; the SD logs from a W209 hold only application events (SWC_VOL_UP, APP_MUTE), no telegrams |
| **Dension Gateway 500S `G51A_UPD.rom` v0065** | **plain ARM code, decoded (section 3)** |
| usb2most (JLR tool) | decompiled earlier; JLR tables in section 4 |

## 3 Dension Gateway 500S — what the code does (C)

Telechips ARM image, load base 0x20012824, Dension's own MOST stack
(`core\most\*.c`). The Gateway is a source (CD-changer emulator with a phone
kit), so most of its tables are source-side; the useful part is what it sends
to the amplifier.

**Sample rate per car profile** (profile records at file offset 0x1E4F20):

| 48 kHz | 44.1 kHz |
|---|---|
| Aston Martin, Volvo, Volvo2, Volvo3 | Mercedes, BMW, BMW MP3, BMW4, Audi, Audi2, Porsche PCM, Porsche CDR, Saab |

**FBlocks it implements** (table at 0x2410B4, records `{FBlockID, state, FktID table}`):
0x31 AudioDiskPlayer (OEM FktIDs 0xC00–0xC8B, 0xD02, 0xD21), 0x50 Phone,
0x51 Phonebook, 0x42, 0x24, 0x26, 0x54, 0x06, 0x07, 0x08, 0x0F, 0x15, 0xC2,
0xC7, 0xCC; plus shadows of 0x22 AudioAmplifier and 0x02 NetworkMaster, which
accept only Status (OPType 0x0C) — it listens to the amplifier.

**Phone-call sequence to the amplifier** (`fb_phone.c`, state machine at
0x2002EEF8), in order:

| Step | Telegram | Payload |
|---|---|---|
| find the amplifier | `02.A01` Get (Central Registry) | `22 00` |
| sink info | `22.110` SinkInfo Get | `01` |
| disconnect | `22.112` DisConnect StartResult | `01`, later `02` |
| connect own source | `22.111` Connect StartResult | `sink, 00, ch, ch+1, ch+2, ch+3` |
| mute | `22.113` Mute | `sink, 01` / `sink, 00` |
| save, clear, restore | `22.201` Loudness, `22.46B` DynSoundControl | Get; Set `00` during the call; Set the saved value after |
| OEM | `22.D11` StartResult | `01 30 02 00 14` |
| volume | `22.D10` Get `02` every 1 s; on its Status, send `22.400` Volume Set | `D10.data[1]` |

It also stores `22.469` RecallSoundSetting Status (16 bit).

**Brand of this path: I.** It is enabled when a configuration byte is 0 or 4,
which in the `CARCFG_MOST_*` list is MERCEDES and BMW4. Not proven. D10 and D11
are the only OEM AudioAmplifier FktIDs found anywhere so far.

## 4 Per brand

| Brand | Known | Conf. | Source |
|---|---|---|---|
| Jaguar / Land Rover | AUD3 amp 0x22 inst 0x0A, volume via `46D` Set (byte0 param, byte1 sink, 7 signed-dB bytes), 61 steps −99…0 dB; LR2 amp inst 0x02, 35 steps −82…0 dB; 200/202/203/204 tone; mute via 466; amp sinks 1 main, 2 phone/navigation/voice, 3 parking sensors, 4 chimes; XF: the gateway's `F0.409` Status, byte 2 the volume, byte 8 navigation/phone, byte 10 parking sensors | C | usb2most decompile; mObridge MOST25 DA Series Guide pp. 18-19 (the sinks); JLR-HU / SocketMost (`F0.409`) |
| BMW | AudioMaster `20.00.0200` VolumeActual, 0–63; 0220–0223 balance/fader/bass/treble; CIC sinks all on 0x22 | C | SGBD (CIC, NBT) |
| Mercedes (BMW4?) | 0x22: 110/111/112/113, 201, 46B, 469, 400; OEM D10 (phone volume), D11 | C code / I brand | Dension, section 3 |
| Audi | J523 order: connect channels → sound settings → unmute; no IDs | C order | SSP286 |
| Porsche PCM3.1 | FBlocks 0x22, 0x24, 0x31, 0x40, 0x42, 0x44, 0x50 | I | PCM-Forge material |
| Volvo | 48 kHz; no IDs (GROM encrypted) | C rate | Dension profiles |

Standard FktID names are from the local catalogue
`FBlock_AudioAmplifier_2V4-3` (0x201 Loudness, 0x469 RecallSoundSetting,
0x46B DynSoundControl, 0x46D SpeakerLevel, 0x400 Volume).

## 5 What is missing, and what closes it

| Gap | Closed by |
|---|---|
| value → dB scale for every brand except JLR | a ring recording while stepping volume, read against the head unit's display |
| D10/D11 brand, meaning of D11's bytes | a Mercedes recording with a phone call |
| Audi, Porsche, Volvo OEM IDs | a recording per brand: volume, tone, source change, call |

Leads left, not needed for the hardware: live `STEUERN_MOST_TELEGRAMM` on an
NBT; PCM3.1 binaries held by the PCM-Forge authors; CBF files (mhhauto);
rennlist/audiworld threads behind Cloudflare; the PiMOST forum.
