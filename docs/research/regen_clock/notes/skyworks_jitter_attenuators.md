# Skyworks (ex-Silicon Labs) jitter-attenuating clock multipliers as the MOST25 regenerator clock (clk = 1024 x Fs from a 44.1/48 kHz LVCMOS Fs)

Research date: 2026-09-24. All manufacturer PDFs were downloaded from skyworksinc.com / statics.cirrus.com and read locally (pdftotext + PyMuPDF; tables and figures that extracted badly were rendered and read as images). Distributor numbers are labelled as such. "Inference" means my own arithmetic or reasoning from the cited facts, not a manufacturer statement.

Application yardsticks used below (from the task, not re-sourced): Fs = 44.1 or 48 kHz, clk = 45.1584 / 49.152 MHz, Fs tolerance +/-0.1 %, CKIN source = FPGA 3.3 V LVCMOS 50 % square wave with ~10 ns p-p quantization jitter, budget tUJ1 <= 0.0045 UI (about 92 ps p-p, about 8 ps rms at BER 1e-9), 3.3 V LVCMOS output needed, battery powered, in-car.

## Which of these parts meet the ~8 ps rms budget with a 44.1/48 kHz input, from a single 3.3 V supply, with an LVCMOS output?

### Takeaway
Only the 3rd-generation Si53xx parts (Si5319, Si5324, Si5326, Si5327 at 1.8/2.5/3.3 V; Si5328 at 2.5/3.3 V) meet all three hard constraints: they accept a kHz-range input, run from one 3.3 V rail and have a 3.3 V CMOS output. Their own jitter is sub-picosecond, and even at a 44–48 kHz phase-detector rate the FRM measures only about 1–2 ps rms wideband, so the chip itself fits the ~8 ps budget. The Si5342/44/45 Rev D and the Si5392/94/95 also accept an 8 kHz LVCMOS input and give LVCMOS outputs, but they need a 1.8 V core rail as well as 3.3 V. The Cirrus CS2000-CP is the same core as the CS2100-CP (70 ps rms period jitter, 175 ps rms wideband) and fails in the same way. What decides pass or fail is not the chip's own jitter but how much of the FPGA's 10 ns p-p input jitter gets through the loop. On that measure the low-bandwidth parts (Si5324/Si5327 at 4–525 Hz, Si5328 below 10 Hz, Si534x/Si539x down to 0.1 Hz) are much stronger than Si5319/Si5326, whose loop bandwidth cannot go below 60 Hz.

### Cited Findings

#### Source documents (all current Skyworks-hosted revisions found on 2026-09-24)
- Si5319 data sheet, Rev 1.0, dated August 27, 2021 (Skyworks-branded); its change list runs 0.1 → 0.2 → 0.3 → 0.4 → 0.41 → 0.42 → 0.43 → 1.0, and Rev 1.0 "replaced the specification tables ... with the specification tables from the Si53x Reference Manual, rev 0.42"; the word "Preliminary" does not appear in Rev 1.0 — [Si5319 DS Rev 1.0](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Si5324 data sheet Rev 1.1, August 23, 2021 — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- Si5326 data sheet Rev 1.0, October 29, 2021 — [Si5326 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5326.pdf)
- Si5327 data sheet Rev 1.0, August 27, 2021 — [Si5327 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5327.pdf)
- Si5328 data sheet Rev 1.0, August 27, 2021 — [Si5328 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5328.pdf)
- Si53xx Family Reference Manual (Si53xx-RM) Rev 1.3 (10/16), Skyworks-branded, 182 pages. The old silabs.com URL now returns 404; the current URL is this one — [Si53xx FRM](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Si5345/44/42 Rev D data sheet, Rev 1.2, November 30, 2021 — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf); Rev D Family Reference Manual (revision history tops out at Revision 1.3) — [Si5345/44/42 Rev D RM](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/Si5345-44-42-D-RM.pdf)
- Si5395/94/92 "FINAL DATA SHEET", revision B (March 2025), page date April 7, 2025 — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Cirrus CS2000-CP DS761F3 and CS2100-CP DS840F3 (copyright 2009–2015) — [CS2000-CP DS](https://statics.cirrus.com/pubs/proDatasheet/CS2000-CP_F3.pdf); [CS2100-CP DS](https://statics.cirrus.com/pubs/proDatasheet/CS2100-CP_F3.pdf)

#### Si5319 (1 input / 1 output, 3rd-gen DSPLL)
- Input 2 kHz–710 MHz (CKIN "0.002–710 MHz"); output 2 kHz–945 MHz, with select frequencies up to 1.4 GHz — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Loop bandwidth 60 Hz–8.4 kHz, set digitally; jitter peaking 0.05 dB typ / 0.1 dB max; jitter tolerance JTOL = 5000/BW ns pk-pk for jitter frequencies above the loop bandwidth — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Jitter generation (fIN = fOUT = 622.08 MHz, LVPECL in/out, BW 120 Hz, 114.285 MHz 3rd-OT crystal, VDD 2.5 V, TA 85 °C): 0.27 ps rms typ / 0.42 max (20 kHz–80 MHz); 0.14 / 0.31 ps rms (4–80 MHz); 0.26 / 0.41 ps rms (50 kHz–80 MHz); 4.2 / 6.2 ps pp (20 kHz–80 MHz). Typical plot at 3.3 V: 250 fs (12 kHz–20 MHz), 274 fs (brick wall 800 Hz–80 MHz) — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Output formats: LVPECL, LVDS, CML or CMOS. The CMOS output tops out at 212.5 MHz. CMOS rise/fall is at most 2 ns at VDD ≥ 2.97 V into 5 pF, and at most 8 ns at 1.71 V. CMOS drive (both pins shorted) at 3.3 V is 8, 16, 24 or 32 mA typ for ICMOS[1:0] = 00/01/10/11. LVPECL needs VDD ≥ 2.5 V nominal — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Supply: a single rail of 1.8 V ±5 %, 2.5 V ±10 % or 3.3 V ±10 % (on-chip regulator). IDD is 217 typ / 243 max mA (LVPECL, 622.08 MHz), 194 typ / 220 max mA (CMOS, 19.44 MHz) and 165 mA typ in disable mode, and "current draw is independent of supply voltage" — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- CKIN: input common mode 1.1–1.95 V at 3.3 V; single-ended input resistance 20/40/60 kΩ (min/typ/max); single-ended swing ≥ 0.2 Vpp below 212.5 MHz; rise/fall (20–80 %) ≤ 11 ns; duty cycle 40–60 % or a minimum pulse width of 2 ns, "whichever is smaller (the 40/60 % limitation applies only to high-frequency clocks)"; "no under- or overshoot is allowed"; absolute CKIN level limits 0 V to VDD — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Reference: "A low-cost 114.285 MHz 3rd overtone crystal or an external reference oscillator ... This external reference is required for the device to operate"; other crystal frequencies may be used — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- On input loss: VCO freeze. The DSPLL latches its VCO settings and uses the XO as its reference, so the output continues. Alarm pins are LOS and LOL, and a bypass mode is available for debug. Lock time from the start of ICAL to LOL low is 35 ms typ / 1200 ms max (622.08 MHz, BW 120 Hz). Time to clear LOL after LOS clears is 10 ms typ. The LOS trigger window is 4.5 x N3 x T_CKIN. Output phase drifts 300 typ / 500 max ps over −40 to +85 °C — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Control via I2C or SPI (selected by the CMODE pin). Reset pulse ≥ 1 µs; registers accessible ≤ 10 ms after reset — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- Package 36-lead 6x6 mm QFN; θJA 32 °C/W, θJC 14 °C/W; −40 to +85 °C. OPNs: Si5319A-C-GM (to 945 MHz plus 970–1134 MHz and 1.213–1.417 GHz), Si5319B-C-GM (2 kHz–808 MHz), Si5319C-C-GM (2 kHz–346 MHz); "R" suffix = tape and reel — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)

#### Si5324 (2 in / 2 out, "low-bandwidth" member)
- Input 2 kHz–710 MHz; output 2 kHz–945 MHz, select frequencies to 1.4 GHz. Loop bandwidth 4–525 Hz. Output jitter as low as 290 fs rms (12 kHz–20 MHz) and 320 fs rms (50 kHz–80 MHz). Hitless switching with phase build-out, free-run and digital hold; LOL/LOS/FOS alarms; I2C or SPI; on-chip regulator "with high PSNR"; LVPECL/LVDS/CML/CMOS per output — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- Supply 1.8 V ±5 %, 2.5 V ±10 % or 3.3 V ±10 %. IDD in CMOS mode at 19.44 MHz: 204 typ / 234 max mA with both CKOUTs on, 194 / 220 mA with one; 165 mA in disable mode — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- Reference: "An external, high quality 38.88 MHz clock or a low-cost 114.285 MHz 3rd overtone crystal". The data sheet warns: "Due to the low bandwidth capabilities of this part, any low-frequency wander or instability on the external reference will transfer to the output clocks ... a stable external reference, TXCO, OCXO, or thermally-isolated crystal is recommended", and Skyworks "does not recommend using MEMS based oscillators" as the reference — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- Lock time (622.08 MHz, BW 7 Hz, XAXB 114.285 MHz, LOCKT 3.3 ms): A/B/C/D grades 0.8 typ / 1.0 max s, settle 4.2 / 5.0 s; the legacy E grade 1 / 1.5 s, settle 1.2 / 1.5 s. Lock and settle time depend on the frequency plan, the XAXB frequency and LOCKT (see AN803). Input-to-output phase after an ICAL "is not controlled and can assume any value" — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- OPNs, all −40 to +85 °C, 36-QFN 6x6 mm: Si5324A (to 1.417 GHz), B (808 MHz), C (346 MHz), D (2 kHz–150 MHz), each "recommended for all new designs"; Si5324E-C-GM exists only for legacy designs that need the original lock-time behaviour (PB-1312191) — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)

#### Si5326 (2 in / 2 out; same PLL range as Si5319)
- Input 2 kHz–710 MHz; output 2 kHz–945 MHz, select frequencies to 1.4 GHz. Loop bandwidth 60 Hz–8.4 kHz; jitter as low as 0.3 ps rms (50 kHz–80 MHz). Supply 1.8/2.5/3.3 V. Hitless switching (manual or automatic), digitally controlled output phase adjustment, LOL/LOS/FOS alarms, I2C/SPI — [Si5326 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5326.pdf)
- Same IDD rows as Si5324 (CMOS 194–204 typ / 220–234 max mA); lock time 35 typ / 1200 max ms; reference is a 114.285 MHz 3rd-OT crystal or a high-quality external clock (TCXO/OCXO). OPNs Si5326A (to 1.4 GHz) and Si5326B (808 MHz), −40 to +85 °C, 36-QFN — [Si5326 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5326.pdf)

#### Si5327 (2 in / 2 out, low bandwidth, 40 MHz-crystal variant)
- Input 2 kHz–710 MHz; output 2 kHz–808 MHz. Loop bandwidth 4–525 Hz. Jitter generation 0.5 typ / 0.6 max ps rms (12 kHz–20 MHz, BW 111 Hz, 40 MHz fundamental crystal, fIN 19.44 MHz, fOUT 156.25 MHz, VDD 2.5 V, 85 °C). Manually controlled hitless switching; "Free run and VCO freeze modes"; LOL and LOS alarms (no FOS); single 1.8, 2.5 or 3.3 V supply; I2C/SPI; 36-QFN — [Si5327 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5327.pdf)
- Reference: "a low-cost 40 MHz crystal" or an external clock; the pin table says it "accepts 37–41 MHz crystal or reference clock". Lock time from start of ICAL to LOL low is 1.9 typ / 3 max s. IDD matches Si5324 (CMOS 194–204 / 220–234 mA). OPNs Si5327B (808 MHz), C (346 MHz), D (243 MHz), −40 to +85 °C — [Si5327 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5327.pdf)

#### Si5328 (2 in / 2 out, SyncE / ITU-T G.8262, ultra-low bandwidth)
- Input 8 kHz–710 MHz; output 8 kHz–808 MHz. Jitter as low as 0.3 ps rms (12 kHz–20 MHz); measured 331 fs rms (12 kHz–20 MHz) at 125 MHz out with a 25 MHz input, a Rakon 40 MHz TCXO (RTX7050A) as reference, VDD 3.3 V, BW 0.085 Hz. Supply 2.5 V ±10 % or 3.3 V ±10 % only — [Si5328 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5328.pdf)
- Loop bandwidth "(0.1 Hz; 1 to 10 Hz)" per the data sheet front page — [Si5328 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5328.pdf); the FRM instead says "the loop BW of the Si5328 can be programmed from 0.05 to 6 Hz" — [Si53xx FRM §6.1.4.2](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf) (the two sources conflict)
- Reference: "Because of the wander requirements of SynE and G.8262, the Si5328 must be used with a suitable TCXO as its XAXB reference" — [Si53xx FRM §6.1.3](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Lock time (346 MHz, BW 0.088 Hz): 2 s typ with LOCKT = 4 and FASTLOCK, 12.5 s with LOCKT = 1; settle 1 s. OPNs Si5328B (8 kHz–808 MHz) and Si5328C (8 kHz–346 MHz), −40 to +85 °C, 36-QFN. IDD in CMOS mode at 25 MHz: 194–204 typ / 220–234 max mA — [Si5328 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5328.pdf). (The FRM Table 26 note says "Fmax = 346 MHz for the Si5328", which conflicts with the 808 MHz B grade; irrelevant at 49 MHz — [Si53xx FRM](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf).)

#### Si5342 / Si5344 / Si5345 Rev D (4th-gen DSPLL + MultiSynth)
- Input: differential 8 kHz–750 MHz, LVCMOS 8 kHz–250 MHz. "Differential signals must be ac-coupled, while single-ended LVCMOS signals can be ac- or dc-coupled"; the termination figure covers 3.3, 2.5 and 1.8 V LVCMOS — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- Output: differential 100 Hz–1028 MHz, LVCMOS 100 Hz–250 MHz. LVCMOS outputs are dc-coupled with series resistors, VDDO 3.3, 2.5 or 1.8 V per output supply; LVCMOS impedance, swing and polarity are programmable (§3.9.6–3.9.8) — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- Jitter: 90 typ / 145 max fs rms in integer mode and 120 / 170 fs rms in fractional mode (12 kHz–20 MHz; fIN 19.44 MHz, fOUT 156.25 MHz LVPECL, BW 100 Hz, 48 MHz crystal). Loop bandwidth 0.1 Hz–4 kHz, with a fastlock feature for low bandwidths — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- The RM recommends keeping the normal PLL bandwidth "less than Fpfd/160 although ratios of Fpfd/100 will typically work fine". It adds that the device "supports a minimum input frequency of 8 kHz, but if a fractional P input divider is used, the input frequency must be 300 MHz or higher" — [Si5345/44/42 Rev D RM](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/Si5345-44-42-D-RM.pdf)
- Supplies: VDD 1.8 V ±5 %, VDDA 3.3 V ±5 %, plus separate VDDO pins (3.3/2.5/1.8 V). IDD 135 typ / 260 max mA and IDDA 120 typ / 130 max mA, plus 22–26 mA per LVPECL output at 156.25 MHz. TA −40 to +85 °C, TJ max 125 °C — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- External crystal 25–54 MHz. Modes are free-run (accuracy follows the crystal), lock acquisition, locked and holdover. "The holdover circuit ... stores up to 120 seconds of historical frequency data", and holdover uses an averaged frequency from a programmable window. Monitors: LOS, OOF, LOL and the INTRb pin. PLL lock time with fastlock is 280 typ / 300 max ms at fIN = 19.44 MHz — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- I2C or SPI, with in-circuit programmable NVM ("they always power up with a known frequency configuration"); factory-preprogrammed OPNs exist. At power-up the device loads its configuration from NVM, and "no clocks will be generated until the initialization is complete" — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)
- Packages and OPNs: Si5345 (4 in / 10 out) 64-QFN 9x9 mm; Si5344 (4/4) and Si5342 (4/2) 44-QFN 7x7 mm. Grade letters: A = 0.001–1028 MHz integer + fractional, B = to 350 MHz, C = to 1028 MHz integer only, D = to 350 MHz integer only (e.g. Si5342D-D-GM). All −40 to +85 °C — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf)

#### Si5392 / Si5394 / Si5395 (4th-gen, 2019+, drop-in compatible with Si5342/44/45)
- Input: differential 8 kHz–750 MHz, LVCMOS 8 kHz–250 MHz. Output: differential 100 Hz–1028 MHz, LVCMOS 100 Hz–250 MHz. "Drop-in compatible with Si5345/44/42" — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Jitter: 69 fs rms (grade P), 71 fs (grade E), 85 fs (integer mode), 100 fs (fractional mode). Loop bandwidth 0.1 Hz–4 kHz for grades A/B/C/D; "For grade P and E devices, the DSPLL bandwidth is fixed at 100 Hz" — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Reference: grades A/B/C/D/P take an external crystal or XO in a QFN package. Grades J/K/L/M/E have an integrated reference (no crystal) in LGA packages: Si5395 64-LGA 9x9 mm; Si5394 and Si5392 44-LGA 7x7 mm. The integrated-reference options were added in Rev 1.1 (June 2019). OPN pattern is e.g. Si5392J-A-GM (J = to 1028 MHz integer + fractional, K = 350 MHz, L = 1028 MHz integer only, M = 350 MHz integer only) — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Supplies: VDD 1.8 V ±5 %, VDDA 3.3 V ±5 %, VDDO 1.8/2.5/3.3 V. IDD is 150 typ / 300 max mA (Si5395) or 125 / 250 mA (Si5394/92); IDDA (Si5395) 125 / 140 mA. TA −40 to +85 °C. Lock time with fastlock 280 / 300 ms at 19.44 MHz (grades P/E: 460 / 625 ms). Free-run, synchronous and holdover modes; NVM; I2C/SPI — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)

#### Cirrus CS2000-CP / CS2100-CP (reference only)
- Both use the same hybrid analog/digital PLL (delta-sigma fractional-N synthesizer plus digital PLL). CLK_IN 50 Hz–30 MHz; output 6–75 MHz; single 3.1–3.5 V supply; 12 mA typ / 18 mA max unloaded (40 mW typ); 10-pin MSOP; Commercial (−10 to +70 °C), Automotive-D (−40 to +85 °C) and Automotive-E (−40 to +105 °C) grades. The CS2000 adds stand-alone synthesis from an 8–75 MHz reference, which the CS2100 lacks — [CS2000-CP DS761F3](https://statics.cirrus.com/pubs/proDatasheet/CS2000-CP_F3.pdf); [CS2100-CP DS840F3](https://statics.cirrus.com/pubs/proDatasheet/CS2100-CP_F3.pdf)
- Identical jitter rows in both data sheets, measured at a 24.576 MHz output: period jitter 70 ps rms typ; base-band jitter (100 Hz–40 kHz) 50 ps rms; wide-band jitter (100 Hz corner, TIE per AES-12id) 175 ps rms. CLK_IN lock time is 100 typ / 200 max UI of CLK_IN for fCLK_IN < 200 kHz. Clock skipping keeps PLL_OUT running for a CLK_IN outage of ≥ 20 ms (tCS) — [CS2000-CP DS761F3](https://statics.cirrus.com/pubs/proDatasheet/CS2000-CP_F3.pdf); [CS2100-CP DS840F3](https://statics.cirrus.com/pubs/proDatasheet/CS2100-CP_F3.pdf)
- ClkIn_BW[2:0] "sets the minimum loop bandwidth when locked to CLK_IN"; the application figures show the 1 Hz and 128 Hz settings — [CS2000-CP DS761F3](https://statics.cirrus.com/pubs/proDatasheet/CS2000-CP_F3.pdf)

#### Evidence on jitter at a low phase-detector rate and on input-jitter transfer (the parts of the budget that matter here)
- FRM Table 51 (Si53xx narrowband, Fin = Fout = 200 MHz, BW 60 Hz, brick-wall integration), rms jitter against f3. At f3 = 62.5 kHz: 246 fs (12 kHz–20 MHz) and 997 fs (100 Hz–40 MHz). At 31.25 kHz: 248 fs and 1,844 fs. At 15.625 kHz: 252 fs and 3,521 fs. At 2 kHz: 307 fs and 56,113 fs. "Once f3 is above roughly 50 kHz, there is very little benefit from further increasing f3" — [Si53xx FRM App. B](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- FRM Table 73 (622.08 MHz in/out; FM-modulated input; Si5326 at BW 120 Hz, Si5324 at BW 7 Hz; jitter integrated to 50 MHz):
  - 50 Hz modulation: input 181 ps → Si5326 169 ps, Si5324 10.6 ps
  - 100 Hz: 177 ps → 136 ps and 2.04 ps
  - 500 Hz: 175 ps → 18.6 ps and 295 fs
  - 1 kHz: 184 ps → 4.28 ps and 292 fs
  - 5 kHz: 138 ps → 297 fs and 302 fs
  — [Si53xx FRM App. H](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- XA/XB reference: "Any reference phase noise over the band from 100 Hz to about 30 kHz will pass through to the Si53xx clock outputs with little attenuation", and "The higher the reference frequency, the lower the Si53xx output jitter" (114.285 MHz 3rd-OT recommended over 37–41 MHz fundamental) — [Si53xx FRM App. A](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- The FRM discusses FPGA-generated inputs directly: "Even though FPGAs are notorious for having jittered outputs, the jitter attenuating feature of the Narrowband Any-Frequency Clocks allow an FPGA's output to be used to produce a very clean clock" (its example is a 194.4 MHz FPGA DCM output) — [Si53xx FRM App. B](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### Automotive grade
- None of the Si5319/24/26/27/28, Si5342/44/45 Rev D or Si5392/94/95 data sheets mentions AEC-Q100; every OPN is −40 to +85 °C (text search of all seven data sheets) — [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf); [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf); [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Skyworks' automotive-grade timing line is the Si5332-AM clock generator family (search-result summary of Skyworks pages: AEC-Q100, automotive grade 2), not a jitter attenuator — [Si5332-AM DS (search result, not opened)](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/si5332-automotive-grade-datasheet.pdf)
- The Cirrus data sheets name "Automotive-D/E" temperature grades but, in the text I searched, never state AEC-Q100 — [CS2100-CP DS840F3](https://statics.cirrus.com/pubs/proDatasheet/CS2100-CP_F3.pdf)

### Inferences
- **Budget arithmetic.** At 48 kHz MOST25 runs 64 bytes x 8 bits x 48 kHz = 24.576 Mbit/s, which is 49.152 Mbaud after biphase coding. That makes 1 UI = 20.345 ns, and 0.0045 UI = 91.6 ps pp, or about 7.6 ps rms at Q = 12 (BER 1e-9). This matches the task's "≈92 ps pp / ≈8 ps rms".
- **Intrinsic jitter is not the issue for any Skyworks part.** Datasheet jitter generation runs from 0.07 to 0.6 ps rms. At the application's f3 of 44.1–48 kHz, FRM Table 51 interpolates to about 1.1–1.5 ps rms wideband (100 Hz–40 MHz) for the Si53xx family, so the chip alone uses at most about 20 % of the 7.6 ps rms. The Cirrus parts' 175 ps rms wideband TIE is over 20x the budget.
- **The input path is the issue.** The Si53xx JTOL spec of 5000/BW ns pk-pk means a 10 ns pk-pk input needs BW ≤ 500 Hz to stay inside specified tolerance (at BW = 525 Hz the tolerance is 9.5 ns; at 8.4 kHz it is 0.6 ns). So Si5319/Si5326 must be run near the bottom of their 60 Hz–8.4 kHz range.
- **How much gets through depends on the jitter spectrum.** Scaling FRM Table 73 linearly: a jitter component at 50 Hz passes through a 120 Hz-BW Si5326/Si5319 almost unattenuated (0.6 dB), and through a 7 Hz-BW Si5324 with about 24.6 dB of attenuation. At 100 Hz the Si5324 gives about 38.8 dB. Applied to 10 ns pp, the Si5324 leaves about 586 ps pp at 50 Hz and about 115 ps pp at 100 Hz, both over 92 ps; above about 500 Hz it reaches its own ~0.3 ps floor. So whether any part meets tUJ1 depends on two things not in these documents:
  - where the FPGA's quantization-jitter energy sits in frequency (a sampled Fs edge produces deterministic beat tones set by the ratio of the FPGA clock to Fs);
  - the high-pass corner of the MOST SP1 tUJ1 measurement.

  The lowest usable bandwidth is the strongest lever: Si5324/Si5327 at about 4 Hz, Si5328 at 0.05–0.1 Hz, Si534x/Si539x at 0.1 Hz. Keeping f3 at the full Fs (N31 = 1) also avoids the low-f3 penalty shown in Table 51.
- **Supply and output constraint.** Only Si5319/24/26/27 (and Si5328 at 3.3 V) give a 3.3 V CMOS output from one 3.3 V rail. The Si534x/Si539x parts need an added 1.8 V ±5 % rail.
- **Power.** The Si53xx draws about 0.64 W typ (194 mA x 3.3 V) and up to about 0.80 W (220 mA x 3.63 V), since the current does not scale with VDD. The Si5345 is similar (about 0.64 W typ, 0.94 W max). The CS2x00 draws 0.04 W. For a battery-powered in-car unit, the jitter attenuator's supply should be switched off when the ring is asleep.
- **Temperature.** Every Skyworks candidate is rated −40 to +85 °C with no AEC-Q100 grade. That is a qualification risk for an in-car install if the mounting location can exceed 85 °C ambient.

### Gaps
- The MOST SP1 tUJ1 measurement filter (high-pass corner) and the spectrum of the FPGA's 10 ns quantization jitter were not researched here; the pass/fail verdict on input-jitter transfer depends on both.
- No Skyworks document gives jitter generation or jitter transfer measured with a 44.1/48 kHz input and a 45/49 MHz CMOS output. Table 51 (200 MHz, varied f3) and Table 73 (622 MHz) are the closest primary data.
- The exact BWSEL loop-bandwidth values available for this plan (f3 = 44.1/48 kHz, N2 = 112,640) come only from DSPLLsim, which was not downloaded or run.
- Equivalent low-f3 jitter data for the 4th-gen Si534x/Si539x at an 8–48 kHz input was not found.
- The Si5328 loop-bandwidth range conflicts between the data sheet (0.1 Hz; 1–10 Hz) and the FRM (0.05–6 Hz), and was not resolved.
- The loop-bandwidth range of the integrated-reference Si539x grades J/K/L/M is not stated explicitly in the text found (A/B/C/D: 0.1 Hz–4 kHz; P/E: fixed 100 Hz).
- The Si5345 data sheet's 3.3 V LVCMOS input-swing limit (whether a divider is needed) was not extracted.
- The Si5319 product page says the Si5319-EVB accepts inputs from 10 MHz; whether the EVB's input network can be used at 44.1 kHz for bench evaluation was not checked in the EVB user guide.

## Is Si5319 (or its siblings) still active, and which sibling is the best fit if not?

### Takeaway
Yes. As of 2026-09-24, Skyworks still sells Si5319A/B/C and Si5324/26/27/28 as current catalogue products. None of Skyworks' 317 published EOL/LTB notices covers any Si531x/Si532x jitter attenuator or the Si539x. The only related notice (LTB10225, Oct 2021) discontinues Si534x Revision B and names Rev D as the replacement. I did not obtain an explicit "Active" flag from Skyworks' own lifecycle lookup. Among the siblings, the best fit for a 10 ns-jittered 44.1/48 kHz input on one 3.3 V rail is the Si5324 (my inference; C or D grade). Si5327 is the low-bandwidth alternative with a 40 MHz fundamental crystal. Si5328 has the lowest bandwidth but needs a TCXO and locks in 2–12.5 s. Si5319 remains usable only at a loop bandwidth near its 60 Hz floor.

### Cited Findings
- Skyworks still lists Si5319A (OPN Si5319A-C-GM) under Timing › General Purpose Jitter Attenuators. The page carries the current data sheet, "Buy Now", specifications (input 2–710 MHz, I2C/SPI, QFN36 6x6, −40 to 85 °C) and the Si5319-EVB at MSRP $350.00. No lifecycle or NRND marking is shown on the page — [Skyworks Si5319A page](https://www.skyworksinc.com/en/Products/Timing/General-Purpose-Jitter-Attenuators/Si5319A)
- Product pages for Si5319C, Si5324A, Si5324C, Si5326A, Si5327B and Si5328B also resolve (HTTP 200) under the same category, with their OPNs (e.g. "SI5324A-C-GM", "SI5328B-C-GM") in the page metadata — [Si5324A page](https://www.skyworksinc.com/en/Products/Timing/General-Purpose-Jitter-Attenuators/Si5324A); [Si5328B page](https://www.skyworksinc.com/en/Products/Timing/General-Purpose-Jitter-Attenuators/Si5328B); [Si5319C page](https://www.skyworksinc.com/en/Products/Timing/General-Purpose-Jitter-Attenuators/Si5319C)
- Skyworks' EOL/LTB document list held 317 documents on 2026-09-24, all loaded and searched. Si53xx-numbered hits:
  - LTB10593 (Si53102 PCIe buffer)
  - LTB10397 (Si53254A/Si53258A)
  - LTB10567 (Si5335x…-AM)
  - LTB10225 (Si534x Rev B)

  There were no hits for "Si539". The list includes 2025 notices, so it is maintained — [Skyworks EOL/LTB list](https://www.skyworksinc.com/search?doc=Last%20Time%20Buy#documents)
- LTB10225 "Product Discontinuation Customer Notification", 1-October-2021: "discontinuing the production of the Si5340/1/2/4/5/6/7/8 Revision B". It maps each part to a Rev D replacement (e.g. Si5345A-B → Si5345A-D; Si5342D-B → Si5342D-D) and an "Upgrade Si539x" part (e.g. Si5345A-B → Si5395A; Si5342A-B → Si5392A). All Rev B custom OPNs are affected — [LTB10225](https://www.skyworksinc.com/-/media/SkyWorks/Documents/Products/LTB/LTB10225_Si534x_RevB.pdf)
- The Si5324 A/B/C/D-C-GM OPNs are "recommended for all new designs", and E-C-GM is kept for legacy lock-time behaviour — [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- The Si5395/94/92 data sheet was revised in February and March 2025 (package drawings, pin names), which shows current maintenance — [Si5395/94/92 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5395-94-92-a-datasheet.pdf)
- Distributor data, as reported in search-engine summaries of the distributor pages (not verified on-page, because DigiKey served a bot check and Mouser returned a blank page to automated access):
  - Mouser SI5319C-C-GM: in stock, $26.98, lifecycle "Production" / manufacturer status "FULL PRODUCTION" (the summary says that record was last updated about 4 years ago) — [Mouser SI5319C-C-GM](https://www.mouser.com/ProductDetail/Skyworks-Solutions-Inc/SI5319C-C-GM?qs=JiL6vA75y8P52C/BcPFmLQ%3D%3D)
  - SI5324D-C-GMR: DigiKey US $31.4776 at the 2,500-piece reel MOQ; DigiKey Canada 1,888 units in stock, CAD 39.26 per reel unit; Mouser non-stocked, 52-week lead time, $26.23, MOQ 2,500 — [DigiKey SI5324D-C-GM](https://www.digikey.com/en/products/detail/silicon-labs/SI5324D-C-GM/2278229); [DigiKey.ca SI5324D-C-GM](https://www.digikey.ca/en/products/detail/silicon-labs/SI5324D-C-GM/2278229); [Mouser SI5324D-C-GM](https://www.mouser.com/ProductDetail/Skyworks-Solutions-Inc/SI5324D-C-GM?qs=sGAEpiMZZMvShe%252BZiYheirJWhSBimlWFAomQfP3qZ3I%3D)
  - SI5324C-C-GM: DigiKey "can be ordered today and ships today" — [DigiKey SI5324C-C-GM](https://www.digikey.com/en/products/detail/silicon-labs/SI5324C-C-GM/SI5324C-C-GM-ND/2278226)
- Feature differences between the siblings that matter here:
  - Si5319: 1 in / 1 out, BW 60 Hz–8.4 kHz, VCO freeze.
  - Si5326: 2 in / 2 out, same BW as Si5319, digital hold.
  - Si5324: 2 in / 2 out, BW 4–525 Hz, digital hold, 114.285 MHz crystal or 38.88 MHz reference.
  - Si5327: 2 in / 2 out, BW 4–525 Hz, 37–41 MHz fundamental crystal only, 0.5 ps rms, LOL/LOS only.
  - Si5328: 8 kHz minimum input, BW below 10 Hz, TCXO mandatory, 2.5/3.3 V only.

  Sources: [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf); [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf); [Si5326 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5326.pdf); [Si5327 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5327.pdf); [Si5328 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5328.pdf); [Si53xx FRM §6.1.4, App. A](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Low-bandwidth caveats from the FRM:
  - "the Si5324/27/69/74 loop bandwidth ranges from about 4 to 525 Hz".
  - Lock time of the low-BW parts "can be longer"; with FASTLOCK it is typically 1–5 s.
  - Longer HIST_DEL/HIST_AVG settings are recommended for the low-BW parts.

  Source: [Si53xx FRM §6.1.4.1, §6.2.1.1, §6.6.2](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

### Inferences
- **Status call.** Catalogue listing, "Buy Now", current distributor stock, and no LTB/EOL notice together are strong evidence that Si5319/24/26/27/28 are in production in 2026. They are 3rd-generation (2008-era) parts, however, and Skyworks' newer attenuators are the Si539x (LTB10225 names Si539x as the upgrade path for the Si534x family). A long-life product should keep a pin-out-independent fallback in mind.
- **Best sibling for this job: Si5324C or Si5324D** (a 150 MHz output grade is enough for 49 MHz). It keeps Si5319's register model, divider limits, single 3.3 V supply, CMOS output and 36-QFN footprint class. It adds a 4–525 Hz bandwidth, about 16x lower than Si5319/Si5326 (FRM §6.1.4.1), with a JTOL of hundreds of ns at a few Hz of bandwidth, and it adds digital hold with history. Costs: about 1 s lock and up to 5 s settle, and a need for a thermally quiet reference.
- **Si5327** is the lower-cost variant: a 37–41 MHz fundamental crystal instead of the 114.285 MHz 3rd overtone, the same 4–525 Hz bandwidth and 0.5 ps rms jitter.
- **Si5328** only makes sense if sub-Hz bandwidth proves necessary; it needs a TCXO and has 2–12.5 s lock.
- **Si5342D-D-GM / Si5392J-A-GM** (Rev D / Si539x, the latter needing no crystal) are the modern choices if a second 1.8 V rail is acceptable. Whether one frequency plan can serve both 44.1 and 48 kHz on these parts is unverified (see next question).

### Gaps
- Skyworks' official Product Lifecycle Status Lookup was not queried; it is a form, and I did not submit forms. A per-OPN "Active/NRND" statement from Skyworks is therefore still missing — [Lookup page](https://www.skyworksinc.com/Product-Lifecycle-Status-Lookup)
- Distributor price and stock could not be verified on-page (DigiKey bot check, Mouser blank page, Octopart 403, Findchips client-side rendering). The figures above are search-snippet data. A snippet reporting "SI5392A-A-GM $33.69, 266 in stock at DigiKey" could not be tied to a specific page, so it is excluded from the findings.
- No PCN on the 3rd-generation parts (fab, assembly or crystal-list changes) was searched beyond the EOL/LTB list.

## What does the FRM procedure (ICAL, CKIN network, crystal) demand of the board and the FPGA init sequence — and can one register set serve both 44.1 and 48 kHz?

### Takeaway
One Si5319/Si5324 register set does give CKOUT = 1024 x CKIN for both rates within every FRM limit. With N31 = 1, N2 = 112,640 (N2_HS 11 x N2_LS 10,240) and N1 = 110 (N1_HS 11 x NC1_LS 10), f3 is 44.1 or 48 kHz and fOSC is 4.967 or 5.407 GHz, with at least 2.3 % margin to the 4.85–5.67 GHz VCO limits even at ±0.1 % Fs. The catch is calibration: ICAL runs only with a valid, frequency-stable CKIN present and the crystal running, and it must be repeated after the frequency plan is written or the rate changes. So the FPGA must first recover a stable Fs from the ring, then reset and calibrate the chip, then hold the regenerator off until LOL goes low. That takes 35 ms to 1.2 s for Si5319 and about 1 s (plus up to 5 s settle) for Si5324, during which the output can be off or up to 20 % off frequency.

On the board, the FRM calls for:
- a 114.285 MHz 3rd-overtone crystal with no load capacitors (or a 37–41 MHz fundamental, or an AC-coupled reference);
- a resistive attenuate-and-bias network plus 100 nF AC coupling from the FPGA's 3.3 V LVCMOS pin into CKIN+, with CKIN− AC-grounded;
- CKOUT+ and CKOUT− in CMOS mode, which are identical in-phase copies.

### Cited Findings

#### Divider and frequency limits (FRM §6.1.3, Tables 26/27; register widths from the data sheets)
- fOUT = fIN x N2 / (N1 x N3), with N1 = N1_HS x NC1_LS, N2 = N2_HS x N2_LS and N3 = N31 — [Si53xx FRM §6.1.3](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Limits for Si5319/24/26/27/28 (Table 26): CKIN 2 kHz–710 MHz; f3 2 kHz–2 MHz; fOSC 4.85–5.67 GHz; fOUT 2 kHz–1.475 GHz; "Each entry has 500 ppm margins at both ends" — [Si53xx FRM Table 26](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Divider ranges (Table 27): N1_HS = 4…11; NCn_LS = 1 or even up to 2^20; N2_HS = 4…11; N2_LS = even 2…2^20; N3 = 1…2^19 — [Si53xx FRM Table 27](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf). The register fields confirm the exponents: N31[18:0], N2_LS[19:0], NC1_LS[19:0], N2_HS[2:0], N1_HS[2:0] — [Si5319 DS register map](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf)
- "Selecting the largest possible high-speed divider value will produce lower power consumption"; loop bandwidth "is a function of the phase detector input frequency and the PLL feedback divider", with BWSEL values listed by DSPLLsim — [Si53xx FRM §6.1.3–6.1.4](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Reference-to-output rule: "output frequencies that are an integer multiple (or close to an integer multiple) of the XA/XB reference frequency ... should be avoided" — [Si53xx FRM App. B](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### ICAL (self-calibration) (FRM §6.2)
- ICAL is triggered by internal DCO registers going out of range or by setting ICAL = 1. It starts only "if a valid input clock exists (no input alarm) and is selected as the active clock at that time. The external crystal or reference clock must also be present for the self-calibration to begin (LOSX_INT = 0)" — [Si53xx FRM §6.2.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- "After power-up and writing of dividers or PLL registers, the user must set ICAL = 1 ... LOL will go low when self calibration is complete. Depending on the selected value of the loop bandwidth, it may take a few seconds more for the output frequency and phase to completely settle." A software reset via RST_REG (register 136.7) is recommended before every ICAL and its register writes — [Si53xx FRM §6.2.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- With SQ_ICAL = 0 the output runs during ICAL and "the frequency of the output clocks will change by as much as ±20% during the ICAL process". With SQ_ICAL = 1 the outputs stay off until calibration completes. Table 28 (CKOUT_ALWAYS_ON x SQ_ICAL) selects off-until-first-ICAL, off-during-any-ICAL, or always-on — [Si53xx FRM §6.2.1, §6.2.5](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- The active CKIN must be "stable in frequency" during ICAL; the other CKINs must be within 100 ppm or squelched. "If the selected CKINn varies by 500 ppm or more in frequency since the last calibration, the device may initiate a self-calibration" — [Si53xx FRM §6.2.2–6.2.3](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- After one successful ICAL, a later input loss does not require another: the device enters digital hold (Si5319: VCO freeze) and "relocks to the input clock without performing a self-calibration" when the input returns — [Si53xx FRM §6.2.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- For the low-BW parts (Si5324/27/28): FASTLOCK (the LSB of register 137) "must be written before ICAL"; typical lock with FASTLOCK is 1–5 s; LOCKT = 001 (the three LSBs of register 19) is recommended — [Si53xx FRM §6.2.1.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Register locations in the maps:
  - Reg 0: FREE_RUN, CKOUT_ALWAYS_ON, BYPASS_REG.
  - Reg 2: BWSEL_REG[3:0].
  - Reg 3: SQ_ICAL, plus VCO_FREEZE (Si5319) or CKSEL_REG and DHOLD (Si5324).
  - Reg 5: ICMOS[1:0].
  - Reg 6: SFOUT1_REG[2:0].
  - Reg 19: VALTIME[1:0], LOCKT[2:0].
  - Reg 25: N1_HS.
  - Regs 31–33: NC1_LS.
  - Regs 40–42: N2_HS / N2_LS.
  - Regs 43–45: N31.
  - Regs 129–132: LOS/LOSX/LOL status and flags.
  - Reg 136: RST_REG and ICAL.
  - Reg 137: FASTLOCK (Si5324).

  Sources: [Si5319 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5319.pdf); [Si5324 DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si5324.pdf)
- Lock detect: LOL is held active during calibration; it is a retriggerable one-shot on potential cycle slips, with polarity set by LOL_POL (default active high) and minimum active time set by LOCKT — [Si53xx FRM §6.11.8](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- LOS: the input is divided down to 2 kHz–2 MHz and oversampled by a 40 MHz clock; the alarm fires after twice the normal sample count passes with no edge. Validation time VALTIME is 2 ms, 100 ms, 200 ms or 13 s. LOS can be switched to the slower LOS_A or disabled; with LOS disabled, digital hold can be forced with DHOLD (register 3, bit 5). FOS monitoring works only for 10–710 MHz inputs — [Si53xx FRM §6.11.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Holdover behaviour:
  - Digital hold (Si5324/26/28) averages history (HIST_DEL / HIST_AVG).
  - VCO freeze (Si5319) holds the value from "roughly one second prior to" the alarm.
  - In either mode the output continues and "the VCO tracks any changes in the external reference clock".

  Source: [Si53xx FRM §6.6, §7.4](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Free-run mode (FREE_RUN bit): the XA/XB oscillator can serve as the clock source. For the Si5319, "Clock selection is manual using an input pin. Clock switching is not hitless" — [Si53xx FRM §6.5](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### CKIN from a single-ended 3.3 V LVCMOS source (FRM §7.1, Figure 41)
- CKIN inputs "are internally biased to a common mode voltage and can be driven by either a single-ended or differential source ... AC coupling the input clocks is recommended ... However, either ac or dc coupling is acceptable". "Jitter generation improves for higher levels on CKINn (within the limits described in the data sheet)" — [Si53xx FRM §7.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Figure 41, "CMOS Termination (1.8, 2.5, 3.3 V)" (read from the rendered figure), component by component:
  - At the CMOS driver: R1 33 Ω in series, placed near the driver.
  - Then a 50 Ω line.
  - At the receiver: R2 in series (100 Ω at 3.3 V; 49.9 Ω at 2.5 V; 14.7 Ω at 1.8 V).
  - Then a node with R3 150 Ω to VDD and R4 150 Ω to GND.
  - C1 100 nF from that node to CKIN+.
  - CKIN− to GND through C2 100 nF.
  - Inside the chip, R5/R6 40 kΩ bias both inputs to VICM.

  Notes on the figure: "Attenuation circuit limits overshoot and undershoot", "Use only with ~50% duty cycle clock signals", "Assumes the CMOS output can drive 8 mA" — [Si53xx FRM Fig. 41](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- Unused inputs should have an AC ground; unused input buffers can be powered down with the PD_CKn bits — [Si53xx FRM §7.1](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### Crystal / reference (FRM §7.4, Appendix A)
- RATE[1:0] selects the reference (Table 50):
  - MM: 114.285 MHz 3rd-overtone crystal (recommended for best jitter).
  - LL: 37–41 MHz fundamental crystal (40 MHz recommended).
  - MH: external clock at 114.285 MHz (109–125.5 MHz).
  - ML: external clock at 57.1425 MHz (55–61 MHz).
  - LM: external clock at 38.88 MHz (37–41 MHz).

  For a current list of qualified crystals, see "Si531x/2x/6x Jitter Attenuating Clock Recommended Crystal List" — [Si53xx FRM App. A](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- "Loading capacitors should not be used for either fundamental mode or 3rd overtone crystals" (no footprints). An external reference "must be ac coupled" (Figure 51 shows a 3.3 V CMOS reference network). The crystal's absolute accuracy "does not impact the accuracy or jitter performance of the device output clocks when operating in jitter attenuation mode" and matters only in digital hold or VCO freeze. Rapid crystal temperature changes "can temporarily disturb the Si53xx output phase and frequency", so thermal isolation is recommended — [Si53xx FRM §7.4, App. A](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- The Si5327 takes only 37–41 MHz fundamental crystals. The Si5328 needs a TCXO. "The Si5374, Si5375, and Si5376 must be used with an external crystal oscillator" (not a candidate here) — [Si53xx FRM §6.1.3, App. A](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### CMOS output mode (FRM §6.9, §7.2)
- "For the CMOS setting, both output pins drive single-ended in-phase signals and should be externally shorted together to obtain the maximum drive strength." Figure 44 reads "Optionally Tie CKOUTn Outputs Together for Greater Strength". SFOUT = 010 selects CMOS — [Si53xx FRM §6.9, Fig. 44, Table 38](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)
- In CMOS mode "bypass mode is not supported". "Changes to SFOUT or HLOG will change the output phase. An ICAL is required to re-establish the output phase." Hold-Logic-1 drives both CMOS pins high. Disabling an output tri-states it at common mode and powers down the output buffer and its NC divider — [Si53xx FRM §6.9](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/si53xx-reference-manual.pdf)

#### 4th-generation parts, for comparison
- Si5345/44/42: at power-up the configuration loads from NVM and the DSPLL enters free-run automatically. LVCMOS inputs may be ac- or dc-coupled. There is no Si53xx-style ICAL step; lock acquisition runs automatically with an optional fastlock bandwidth — [Si5345/44/42 Rev D DS](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si5345-44-42-d-datasheet.pdf); [Si5345/44/42 Rev D RM](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/reference-manuals/Si5345-44-42-D-RM.pdf)

### Inferences

#### One register set for both rates: checked against the limits (my arithmetic)
- **N31 = 1** gives f3 = Fs: 44,055.9–44,144.1 Hz or 47,952–48,048 Hz at ±0.1 %, inside 2 kHz–2 MHz and near the ~50 kHz point where FRM Table 51 shows the low-f3 penalty ending.
- **N2 = 112,640 = 2^11 x 5 x 11.** Legal splits are (N2_HS, N2_LS) = (11, 10,240), (10, 11,264), (8, 14,080), (5, 22,528) and (4, 28,160); all N2_LS values are even and ≤ 2^20. Use 11 x 10,240 for lowest power.
- **fOSC:**
  - 44.1 kHz: 4.962457–4.972391 GHz, which is 2.32–2.52 % above the 4.85 GHz minimum.
  - 48 kHz: 5.401313–5.412127 GHz, which is 4.55–4.74 % below the 5.67 GHz maximum.

  Both are inside the limits for the whole ±0.1 % range, and far beyond the 500 ppm limit margin.
- **N1 = 110.** Legal splits are (N1_HS, NC1_LS) = (11, 10) or (5, 22); (10, 11) is illegal because NC1_LS must be 1 or even. fOUT is exactly 45.158400 MHz or 49.152000 MHz (ratio 1024.0), below the 212.5 MHz CMOS limit and inside every grade's range, including Si5324D (≤ 150 MHz).
- **The plan is therefore within all published limits for Si5319/24/26/27/28.** The Si5328 also needs CKIN ≥ 8 kHz, which is met.
- **What differs between the two rates:**
  - The real loop bandwidth: BWSEL maps to Hz through f3 and N2, so the same code gives a bandwidth about 8.8 % different.
  - Calibration: a 44.1 → 48 kHz change is 88,000 ppm, far beyond the 500 ppm auto-recal threshold. The init code should always run RST_REG then ICAL once the actual Fs is present, rather than rely on the auto-recal "may".
- **Crystal spur rule is met.** 45.1584 and 49.152 MHz are not near integer multiples or sub-multiples of 114.285 MHz (ratios 2.53 and 2.33), nor of 40 MHz (1.13 and 1.23) or 38.88 MHz (1.16 and 1.26).

#### What Figure 41 means at 44.1 kHz with a 3.3 V FPGA driver (my arithmetic)
- The R3/R4 pair forms a 75 Ω Thevenin source at 1.65 V. The driver therefore sees about 7.9 mA DC in each logic state (consistent with the figure's 8 mA note), and the node swing is about 1.19 Vpp, above the 0.2 Vpp minimum.
- The R3/R4 divider alone burns about 11 mA / 36 mW continuously.
- C1 into the 20–60 kΩ internal bias gives τ = 2–6 ms (a high-pass corner at 27–79 Hz), so a 44.1 kHz square wave droops only 0.2–0.6 % per half-period. The network works at audio rates.
- For a short on-board trace, the 50 Ω matching is not needed. A plain resistive attenuator (series R into a divider) plus 100 nF coupling that meets the data sheet limits would be an equivalent, lower-power choice; that is a design choice, not an FRM statement.
- The 50 % duty requirement is met by the FPGA's square wave.

#### FPGA and host init sequence implied by the FRM
1. Power up, hold RST for ≥ 1 µs, then wait ≤ 10 ms before the first register access.
2. Set RST_REG (136.7) for a software reset.
3. Write the frequency plan to registers 25, 31–33, 40–45: N31 = 1, N2_HS/N2_LS, N1_HS/NC1_LS.
4. Write the remaining configuration:
   - BWSEL (reg 2), chosen with DSPLLsim at ≤ 500 Hz for JTOL;
   - SFOUT1 = 010 CMOS (reg 6) and ICMOS (reg 5);
   - CKOUT_ALWAYS_ON (reg 0) / SQ_ICAL (reg 3);
   - LOCKT / VALTIME (reg 19);
   - LOS mode;
   - Si5324/27/28 only: FASTLOCK = 1 (reg 137) and LOCKT = 001.
5. Wait until the FPGA has recovered a stable Fs from the ring (LOS_INT = 0) and the crystal runs (LOSX_INT = 0).
6. Write ICAL = 1 (reg 136).
7. Poll LOL, or watch the LOL pin, until it goes low: 35 ms typ / 1.2 s max for Si5319/26 (datasheet conditions), about 1 s for Si5324, 1.9–3 s for Si5327, 2–12.5 s for Si5328. Then allow extra settle time: up to 5 s for Si5324.
8. Enable the regenerator's transmit path only after LOL is low, because CKOUT can be absent or up to ±20 % off frequency during ICAL.
9. On an Fs rate change (44.1 ↔ 48 kHz), repeat steps 2–8.
10. On a short ring dropout, rely on digital hold / VCO freeze: no re-ICAL is needed.

#### Other board notes
- CKOUT+ and CKOUT− are identical in-phase CMOS copies. They could feed the FPGA clock pin and the retiming flip-flop separately, but the FRM's recommendation is to short them for maximum drive. Driving two loads from separate pins is my inference and was not evaluated by the FRM.
- The crystal should sit away from heat sources, because the FRM warns about thermal transients.
- The low-BW parts pass reference wander to the output, so a thermally isolated crystal (or TCXO) matters more on Si5324/27/28 than on Si5319.

### Gaps
- DSPLLsim was not run, so the exact BWSEL codes and resulting loop bandwidths for f3 = 44.1/48 kHz with N2 = 112,640 remain unknown. Whether DSPLLsim itself would pick N31 = 1 / N2 = 112,640 for this ratio was also not confirmed.
- The FRM gives no formula for lock time against loop bandwidth. Data-sheet lock times are specified at 622 MHz (Si5319/24/26) or 346 MHz (Si5328), not at a 44 kHz f3, and AN803 (Si5324/27 lock and settling) was not fetched.
- The exact ICAL bit position in register 136 was read only from the register-map column order (RST_REG is bit 7 per the FRM; ICAL is listed next to it). Confirm against the full register description before coding.
- The 4th-generation VCO tuning range is not stated in the Si5345 Rev D data sheet or RM text I searched; only "fVCO = 14 GHz" appears as a test condition in the Si539x data sheet. It is therefore unverified whether one Si534x/Si539x plan can cover a 44.1/48 kHz input change of 8.8 % (with a fixed 1024 ratio the VCO would have to move by 8.8 %). Two plans, one per rate, selected by the host, may be required; check in ClockBuilder Pro.
- The "Si531x/2x/6x Jitter Attenuating Clock Recommended Crystal List" (qualified 114.285 MHz and 40 MHz part numbers) was not fetched.
