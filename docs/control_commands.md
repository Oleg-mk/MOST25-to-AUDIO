# Audio control commands per brand: what we have, what is missing

Desk research. Nothing here has been measured on a car. Confidence labels as in
vehicle_survey.md: **C** primary source or working code, **F** forum or vendor,
**I** inference.

## 1 The short answer

- The listener does not depend on this table. It passes every control block raw
  (`ctrl_uart.v`), whatever its source or destination and whatever the brand.
  A missing entry here only means software cannot yet put a name or a dB value
  on a telegram it already has.
- The standard AudioAmplifier IDs (FBlock 0x22) are used on the wire, not only
  in the catalogue: JLR's amplifiers take Connect 0x111 and SpeakerLevel 0x46D
  (section 2).
- What is missing is per-brand: the value-to-dB scales, and OEM IDs for Audi,
  Porsche and Volvo. One recording of a real ring per brand (volume, tone, a
  phone call) fills it. The listener is the tool that makes that recording.

## 2 Per brand

| Brand | Known | Conf. | Source |
|---|---|---|---|
| Jaguar / Land Rover | AUD3 amp 0x22 inst 0x0A, volume via `46D` Set (byte0 param, byte1 sink, 7 signed-dB bytes), 61 steps −99…0 dB; LR2 amp inst 0x02, 35 steps −82…0 dB; 200/202/203/204 tone; mute via 466; amp sinks 1 main, 2 phone/navigation/voice, 3 parking sensors, 4 chimes; XF: the gateway's `F0.409` Status, byte 0 the record's kind (0 = the whole record), byte 2 the volume (0–35), bytes 7/9/10/11 phone/navigation/voice/parking sensors (level + 5, 0–25), the screen's Set [channel, 0, level + 5] (two layouts in one author's code, the later one used); tone, Subwoofer, MixerLevel and 0xE09/0xE20–0xE22 go to the gateway's shadow 0x22.A1, not to the amp | C | usb2most decompile; mObridge MOST25 DA Series Guide pp. 18-19 (the sinks); JLR-HU / SocketMost (`F0.409`) |
| BMW | AudioMaster `20.00.0200` VolumeActual, 0–63; 0220–0223 balance/fader/bass/treble; CIC sinks all on 0x22 | C | SGBD (CIC, NBT) |
| Audi | J523 order: connect channels → sound settings → unmute; no IDs | C order | SSP286 |

Standard FktID names are from the catalogue
`FBlock_AudioAmplifier_2V4-3` (0x201 Loudness, 0x469 RecallSoundSetting,
0x46B DynSoundControl, 0x46D SpeakerLevel, 0x400 Volume).

## 3 What is missing, and what closes it

| Gap | Closed by |
|---|---|
| value → dB scale for every brand except JLR's SpeakerLevel (dB on the wire); the Jaguar XF's 0xF0.0x409 bytes too | a ring recording while stepping volume, read against the head unit's display |
| Audi, Porsche, Volvo OEM IDs | a recording per brand: volume, tone, source change, call |
