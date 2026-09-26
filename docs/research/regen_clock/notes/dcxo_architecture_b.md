# I2C/SPI DCXOs for an FPGA-run digital PLL ("architecture B") as the MOST25 regenerator clock

Retrieved 2026-09-24. Datasheet numbers were read from the manufacturer PDFs (text-extracted with pdftotext). Where the extracted table columns were misaligned, the finding says so and the number should be re-checked in the PDF before it is relied on. Distributor data is labelled as such. "Glitch-free" below always means the manufacturer's own wording; no datasheet found gives a numeric bound on phase error during a DCO step.

Requirement recap (from the assignment): clk = 45.1584 MHz (Fs 44.1 kHz) or 49.152 MHz (Fs 48 kHz); lock to a ring that may be off by up to ±0.1 % (±1000 ppm); tUJ1 ≤ 0.0045 UI ≈ 92 ps pk-pk ≈ 8 ps rms; 3.3 V LVCMOS; update over I2C at tens to hundreds of Hz or more; automotive temperature range desirable.

## Key question 1 — Which oscillators give ≥ ±1000 ppm glitch-free fine tuning over I2C at both 45.1584 and 49.152 MHz, with sub-picosecond jitter and an LVCMOS output?

### Takeaway
No part meets every requirement cleanly. By the datasheets, four meet the full set of ≥ ±1000 ppm glitch-free range, I2C, LVCMOS, sub-ps jitter and coverage of 45/49 MHz:
- **SiTime SiT5358** (±1200/±1600/±3200 ppm, 5–94 ppt steps, −40…105 °C, not AEC-Q100, frequency fixed at the factory);
- its **AEC-Q100 Grade 2 siblings SiT5186 and SiT5386**, which are still "Pre-Production Sampling";
- **Skyworks Si570** (±3500 ppm window, 0.09 ppb steps, an older design at 90 mA, −40…85 °C);
- **TI LMK61E0M** (±1000 ppm specified, the window depends on the configuration, 140 mA, jitter specified only at ≥ 50 MHz).

Several parts fall just short of ±1000 ppm around a fixed centre: Si549/Si548/Si544 (±950 ppm), Aeonsemi AS5003 (±970 ppm, preliminary) and Si514 (±1000 ppm, described as "sub-±1000"). They qualify if the FPGA re-programs the centre frequency once at start-up.

The other parts fail one requirement:
- **Differential outputs only:** SiT3521/SiT3522, TI LMK61E07 and LMK61E2 have no LVCMOS output. The LMK61E2's glitch-free fine margining is also only about ±100 ppm.
- **No I2C:** SiT3907 has LVCMOS and ±1600 ppm but uses a 1-wire tri-level interface.

### Cited Findings

#### Screening table (details and sources in the per-part sheets below)
| Part | 45.1584 / 49.152 MHz | Glitch-free tuning range | Step | Interface | Output | Jitter (typ) | Idd (typ) | Temp / AEC | Status (2026-09) |
|---|---|---|---|---|---|---|---|---|---|
| SiT5358 | factory-set, 1–60 MHz | ±6.25…±3200 ppm | 5–94 ppt | I2C 400 kHz / 1 MHz | LVCMOS / clipped sine | 0.31 ps (10 MHz, 12 k–5 M) | 44 mA | to −40…105 °C, no AEC | orderable, SiTime direct |
| SiT5186 / SiT5386 | factory-set, 1–60 MHz | ±6.25…±3200 ppm | 5–94 ppt | I2C | LVCMOS / clipped sine | 0.31 ps (10 MHz) | ~44 mA | AEC-Q100 Gr 2 −40…105 °C | Pre-Production Sampling |
| Si570 | I2C any-frequency, CMOS 10–160 MHz | ±3500 ppm | 0.09 ppb | I2C 400 kbps | CMOS/LVPECL/LVDS/CML | sub-ps (CMOS row unclear) | 90 mA | −40…85 °C | not verified |
| LMK61E0M | I2C any-frequency, LVCMOS ≤ 200 MHz | ±1000 ppm spec | 0.55 ppb | I2C 1 MHz, ≤ 8.7 kHz updates | 3.3 V LVCMOS ×2 | 0.5 ps (≥ 50 MHz) | 140 mA | −40…85 °C | Active, TI out of stock |
| Si549 / Si548 / Si544 | I2C any-frequency, CMOS ≤ 250 MHz | ±950 ppm | 0.1164 ppb | I2C 1 MHz | CMOS/diff | 0.2 ps CMOS | 74–87 mA | −40…85 °C | not verified |
| Si514 | I2C any-frequency, CMOS ≤ 212.5 MHz | ±1000 ppm ("sub") | 0.026 ppb | I2C | CMOS/diff | ~0.8 ps (12 k–20 M, LVPECL) | 21 mA | −40…85 °C | not verified |
| AS5003 (Aeonsemi) | I2C any-frequency, LVCMOS ≤ 212.5 MHz | ±970 ppm | 0.026 ppb | I2C 1 MHz | CMOS/diff | 0.35 ps | ~40–70 mA (unclear) | −40…85 °C | Rev 0.9, "under development" |
| SiT3521 | I2C any-frequency 1–340 MHz | ±6.25…±3200 ppm | 5–94 ppt | I2C / SPI | **LVPECL/LVDS/HCSL only** | 0.21 ps | ≤ 80–93 mA (max) | to −40…105 °C | Production |
| SiT3907 | factory-set 1–220 MHz | ±25…±1600 ppm | 1 ppb (mode 2) | **1-wire tri-level** | LVCMOS | 0.6 ps (20 MHz) | not extracted | −40…85 °C | Production |
| LMK61E07 | I2C any-frequency | ±1000 ppm | 0.55 ppb | I2C 1 MHz | **LVPECL/LVDS/HCSL only** | 0.1–0.15 ps | 162 mA | −40…85 °C | not verified |
| LMK61E2 | I2C any-frequency ≥ 10 MHz | ~±100 ppm (XO load cap) | — | I2C 400 kHz | **LVPECL/LVDS/HCSL only** | 0.09 ps | 152–162 mA | −40…85 °C | datasheet rev. May 2025 |

#### SiTime SiT5358 (Elite Super-TCXO with DCTCXO/DCO mode) — datasheet Rev 1.03, 1 January 2023
- Any frequency from 1 MHz to 60 MHz in 1 Hz steps, factory programmable. The ordering code covers 1.000000–60.000000 MHz, so 45.158400 and 49.152000 MHz are orderable as two separate codes. Three configurations are ordered by code: TCXO, VCTCXO, or "DCTCXO enabling digital control of output frequency using an I2C interface, pullable to 5 ppt" — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- Pull range ±6.25, ±10, ±12.5, ±25, ±50, ±80, ±100, ±120/125, ±150, ±200, ±400, ±600, ±800, ±1200, ±1600, ±3200 ppm. Resolution is 5×10⁻¹² up to ±200 ppm, 1×10⁻¹¹ at ±400, 1.4×10⁻¹¹ at ±600, 2.1×10⁻¹¹ at ±800, 3.2×10⁻¹¹ at ±1200, 4.7×10⁻¹¹ at ±1600 and 9.4×10⁻¹¹ at ±3200 ppm (Table 18) — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- The control word is 26-bit two's complement: the LSW goes to 0x00[15:0], then the MSW to 0x01[9:0], and "the frequency change is initiated after the MSW value is written." "The maximum Digital Control update rate is 38 kHz regardless of I2C bus speed" — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- DCTCXO delay and settling (Table 20): Tfdelay (end of MSW write to start of pull) is 103 µs typ, 140 µs max. Tsettle (to 0.5 % of the frequency offset) is 16.5 µs typ, 20 µs max — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- The I2C bus runs at 400 kHz (−40…105 °C) or 1000 kHz (−40…85 °C) — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- Outputs are LVCMOS or clipped sinewave, on 2.5/2.8/3.0/3.3 V supplies. Stability is ±50 ppb over −40…105 °C with a ±1 ppb/°C typical slope. The package is 5.0 × 3.2 mm ceramic, 10 pins — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- Jitter (LVCMOS): RMS phase jitter is 0.31 ps typ at F_nom = 10 MHz, 12 kHz–5 MHz. The extracted table also lists 0.31/0.48 ps and a 50 MHz, 12 kHz–20 MHz condition, and RMS period jitter of about 0.8 ps typ. The column alignment is ambiguous in the extracted text. — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- Current is 44 mA typ / 53 mA max at F_nom 19.2 MHz, no load, in TCXO/DCTCXO modes. The row pairing was inferred from the extracted table. — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- The datasheet points to "Related products for automotive applications" (link to sitime.com/solutions/automotive). It is not AEC-Q100 itself — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- AN10064 on these Elite Super-TCXO DCO modes says "the output frequency can be continuously pulled within the specified pull range" and "The device output is not disabled during frequency change." It also says "Maximum digital control update rate is 38 kHz regardless of digital interface bus speed" — [SiTime AN10064 Rev 1.0](https://www.sitime.com/api/gated/AN10064-Improved-System-Performance-with-Digital-Frequency-Tuning.pdf)
- Price/stock (distributor aggregator data): SiTime direct lists 9,999 pcs at $35.59–$113.16 depending on variant. Avnet Silica/Americas/Asia list 0 stock and no price — [Findchips SiT5358](https://www.findchips.com/search/SiT5358)
- SiT5359 is the 60–220 MHz sibling ("60 MHz to 220 MHz, ±50 ppb"), so it cannot make 45/49 MHz — [SiT5359 datasheet](https://www.sitime.com/datasheet/SiT5359)

#### SiTime automotive (AEC-Q100) I2C-tunable parts: SiT5186 / SiT5386 (and SiT5187 / SiT5387)
- SiTime's DCXO family page (SiT3521, SiT3522, SiT3901, SiT3907, SiT3921, SiT3922) shows no AEC-Q100 part. The AEC-Q100 parts with I2C digital tuning are Super-TCXOs: AN10064 Table 1 lists SiT5186 (1–60 MHz, ±0.5/±1.0/±2.5 ppm), SiT5187 (60–220 MHz), SiT5386 (1–60 MHz, ±0.1/±0.2/±0.25 ppm) and SiT5387 (60–220 MHz), marked "* AEC-Q100 Compliant", with LVCMOS or clipped sine output. Table 1 also lists the non-automotive DCO-capable SiT5155/5156/5157 and SiT5356/5357 — [SiTime AN10064 Rev 1.0](https://www.sitime.com/api/gated/AN10064-Improved-System-Performance-with-Digital-Frequency-Tuning.pdf); [SiTime DCXO family page](https://www.sitime.com/products/digitally-controlled-oscillators)
- SiT5186 (advance datasheet rev 0.31, 1 January 2023):
  - "Automotive AEC-Q100 qualified", Grade 2 (−40…105 °C) with Grades 3/4 also available;
  - any frequency 1–60 MHz in 1 Hz steps, factory programmable;
  - DCTCXO via I2C up to ±3200 ppm pull range at 5 ppt resolution;
  - LVCMOS or clipped sinewave, 2.5–3.3 V;
  - I2C at 100/400 kHz (−40…105 °C) or 1000 kHz (−40…85 °C);
  - "update rate is 38 kHz regardless of I2C bus speed";
  - DCTCXO delay about 22 µs and settling about 30 µs typ to 1 % of final. Table 21's alignment in the extracted text is ambiguous.
  - RMS phase jitter 0.31 ps typ (10 MHz, 12 kHz–5 MHz); current table the same as the SiT5358 (44/53 mA typ/max).
  — [SiT5186 datasheet](https://www.sitime.com/datasheet/SiT5186)
- The SiT5186 product page lists the status as **"Pre-Production Sampling"**: 1–60 MHz, ±0.5/±1/±2.5 ppm, pull ±6.25 to ±3200 ppm, 5.0 × 3.2 mm 10-pin ceramic — [SiT5186 product page](https://www.sitime.com/products/automotive-tcxos/sit5186)
- The SiT5386 product page also says **"Pre-Production Sampling"**: 1–60 MHz, ±100 ppb over AEC-Q100 Grade 2 −40…105 °C, pull ±6.25 to ±3200 ppm, "LVCMOS or Clipped sinewave output", 5.0 × 3.2 mm 10-pin ceramic, 2.5–3.3 V — [SiT5386 product page](https://sitime.com/products/automotive-tcxos/sit5386)
- SiT5387 (advance Rev 0.31) is AEC-Q100 Grade 2 with "Output 60–189 MHz, and 200–220 MHz", so it does not cover 45/49 MHz — [SiT5387 datasheet](https://www.sitime.com/datasheet/SiT5387)
- Distributor data: SiT5186 variants at Avnet list 0 stock and no price — [Findchips SiT5186](https://www.findchips.com/search/SiT5186)

#### SiTime SiT3521 / SiT3522 (Elite I2C/SPI programmable oscillator with DCO) — SiT3521 datasheet Rev 1.02, 28 December 2023
- Two in-system modes after power-up at the factory start-up frequency: an any-frequency mode ("re-programmed to any frequency between 1 MHz and 340 MHz in 1 Hz steps") and a DCO mode ("steered or pulled by up to ±3200 ppm with 5 to 94 ppt resolution"). Programming is over I2C or SPI — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- **Outputs are LVPECL, LVDS or HCSL only**; the ordering code offers signaling type 1/2/4. There is no LVCMOS — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Any-frequency change: after the forward divider (0x05) is written, "the outputs will be disabled until the PLL locks to the new frequency and is stable." Output disable time is ≤ 2.3 µs and settling ≤ 421 µs. SPI needs ≥ 125 µs between transactions — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- The DCO is the same scheme as the SiT5358: a 26-bit word, LSW then MSW, pull range options from ±6.25 to ±3200 ppm, Tfdelay 103/140 µs, Tsettle 16.5/20 µs, and "maximum DCO Frequency Control update rate is 38 kHz regardless of I2C/SPI bus speed." Absolute pull range (APR) at the ±1600 ppm setting is ±1585 ppm (±10/±20 ppm stability grades) down to ±1545 ppm (±50 ppm grade). At ±3200 ppm it is ±3185…±3145 ppm — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Pitfall stated in the datasheet: "If the user desires that the output remains enabled while changing the frequency, a 1 must also be written to the OE control bit 0x01[10]" on software-OE parts. With software OE the output is disabled by default at start-up — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- I2C runs at 100 kHz, 400 kHz or 1 MHz, but "Fast mode plus is not supported in Extended Industrial temperature range". SPI SCLK goes up to 5 MHz. The −40…105 °C option is "available only for I2C operation" — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Jitter is 0.21–0.225 ps typ RMS phase jitter (156.25 MHz, 12 kHz–20 MHz). RMS period jitter is 1 ps typ / 1.6 ps max (LVPECL/LVDS). Idd max is 80–93 mA depending on output type, excluding termination — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Package is a 10-lead QFN, 5.0 × 3.2 mm. Temperature grades are −20…70, −40…85 and −40…105 °C. First-year aging is ±1 ppm — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Status is "Production" on the family page. SiT3522 covers 340–725 MHz (LVPECL/LVDS/HCSL), so it does not reach 45/49 MHz — [SiTime DCXO family page](https://www.sitime.com/products/digitally-controlled-oscillators)
- Price (aggregator, SiTime direct): $12.63–$42.74 across listed variants and quantity breaks — [Findchips SiT3521](https://www.findchips.com/search/SiT3521)

#### SiTime SiT3907 (DCXO) — datasheet Rev 1.2, revised July 24, 2014 (still the current download)
- Factory programmable from 1 MHz to 220 MHz. Pull range ±25, ±50, ±100, ±200, ±400, ±800 or ±1600 ppm. "LVCMOS/LVTTL compatible output", at 1.8, 2.5, 2.8 or 3.3 V. "Superior pull range linearity of <= 0.01%" — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- **Interface is a "1-pin tri-level serial interface" (the DP pin), not I2C.** Each frame is 40 bits (16-bit header, 8-bit register, 16-bit value). Mode 1 uses one frame (16-bit word) and mode 2 uses two frames (23-bit word) — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- Resolution and maximum update rate: in mode 1, ±1600 ppm gives 49 ppb at 25 k updates/s. In mode 2 every range gives 1 ppb at 12.5 k updates/s — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- "Writing into the DCXO registers does not cause any interruptions of output oscillations; the frequency will switch from one value to the new one smoothly." — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- Timing: frame length ≥ 40 µs, frame-to-frame delay ≥ 2 µs, frame-to-frequency delay ≤ 8 µs, frequency settling ≤ 30 µs. The label/value pairing comes from the extracted table and is confirmed for Tfdelay ≤ 8 µs and Tf2f = 2 µs in AN10041 — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907); [SiTime AN10041 Rev 1.1](https://www.sitime.com/sites/default/files/hiddenresources/AN10041-Designing-with-SiT39xx-DCXOs-SIT.pdf)
- Jitter at f = 20 MHz: RMS phase jitter (12 kHz–20 MHz) is 0.6 ps typ / 1 ps max with no DP activity, and 0.65 / 1 ps with full activity. RMS period jitter is 1.5 / 2 ps idle and 2 / 3 ps with activity — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- Stability ±10/±25/±50 ppm. Temperature −20…70 or −40…85 °C. Packages 3.2 × 2.5 (4-pin), 5.0 × 3.2 and 7.0 × 5.0 (6-pin). Status "Production" — [SiTime DCXO family page](https://www.sitime.com/products/digitally-controlled-oscillators)
- Siblings on the family page: SiT3921 (1–220 MHz) and SiT3922 (220–625 MHz) are LVPECL/LVDS DCXOs. SiT3901 is 1–26 MHz LVCMOS in a 1.5 × 0.8 mm package. The page also advertises "Wide pull range options, up to ±150,000 ppm" and "Tuning resolution of 1 ppb" over "a one-wire digital interface" — [SiTime DCXO family page](https://www.sitime.com/products/digitally-controlled-oscillators)

#### Skyworks Si549 / Si548 / Si544 (Ultra Series I2C XO with DCO/ADPLL mode) — Si549 doc 206617A, May 30 2023; Si548 206616A, May 30 2023; Si544 206612A, May 30 2023
- Si549: "I2C programmable to any frequency from 0.2 to 1500 MHz with < 1 ppb resolution". CMOS/Dual CMOS runs 0.2–250 MHz. Formats are LVPECL, LVDS, CML, HCSL, CMOS and Dual CMOS on 3.3/2.5/1.8 V "from the same part number". It supports "up to 4 pin-selectable startup frequencies" — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- DCO: "The Si549 can make small, fast frequency adjustments over a range of +/- 950 ppm". The ADPLL_DELTA_M[23:0] word (reg 231→232→233, LSByte first) sets 0.0001164 ppm/LSB, with a valid range of −8161513 to +8161512. The change takes effect when the MSByte (reg 233) is written. "This offset is added in a synchronous fashion to prevent frequency discontinuities and can be updated as fast as the max I2C bus speed of 1 MHz will allow." — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Spec table: "Frequency Range for Small Frequency Change (Continuous Glitchless Output)" is −950…+950 ppm from the centre. Settling time for a small change is ≤ 100 µs. A large change (> ±950 ppm) takes ≤ 40 ms "Output Squelched", including 30 ms of VCO calibration (FCAL). Frequency reprogramming resolution is 0.026 ppb. I2C runs at 100 kbps, 400 kbps or 1 Mbps (Fast Mode Plus) — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Pitfall notes in the datasheet: "For best performance, place the Si549 on a dedicated I2C bus, or isolate it via an I2C bus multiplexer to minimize noise." "For ADPLL applications and superior ADPLL performance, Skyworks recommends the Si548 … lower jitter than the Si549 while I2C lines are active." — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Si549 jitter (12 kHz–20 MHz): CMOS/Dual CMOS 200 fs typ (10 MHz ≤ F ≤ 250 MHz, no max given); differential 95 fs typ / 150 fs max (≥ 200 MHz). Idd for CMOS is 87 mA typ / 127 mA max. Total stability ±20/±25/±50 ppm by grade. Temperature −40…85 °C. Packages 5 × 7, 3.2 × 5 and 2.5 × 3.2 mm — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Si548 has the same ±950 ppm "Continuous Glitchless Output" window, the same ≤ 100 µs / ≤ 40 ms settling and CMOS to 250 MHz. It adds "Low additive jitter when I2C is active (15 fs Typ)". CMOS is 200 fs typ. Idd for CMOS is 87/127 mA. The package is a 6-pin DFN — [Si548 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si548-datasheet.pdf)
- Si544 has the same ±950 ppm glitchless window. Idd for CMOS is 74/108 mA. Jitter is 150 fs typ (LVPECL/HCSL/CML) and 200 fs typ (CMOS). Temperature −40…85 °C — [Si544 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si544-datasheet.pdf)

#### Skyworks Si570 / Si571 (I2C XO/VCXO, 3rd-generation DSPLL) — datasheet Rev 1.6, March 4 2022
- Programmable from 10 to 945 MHz (select frequencies to 1417.5 MHz). **CMOS output 10–160 MHz** — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- "the device allows reprogramming of the DCO frequency up to ±3500 ppm from the center frequency configuration without interruption to the output clock." The spec table's "Delta Frequency for Continuous Output" is −3500…+3500 ppm. Small-change settling is ≤ 100 µs. Larger changes recalibrate and force "the output clock to momentarily stop and start at any arbitrary point during a clock cycle", taking up to 10 ms, so "circuitry … sensitive to glitches or runt pulses may have to be reset" — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- RFREQ is 38-bit, giving "programmable frequency resolution of 0.09 ppb". Pitfall: "multi-register RFREQ writes can impact the output clock frequency on a register-by-register basis during updating." The cure is to freeze M (reg 135 bit 5 = 1), write RFREQ, then unfreeze — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- I2C: "Fast mode operation is supported for transfer rates up to 400 kbps." Idd for CMOS is 90 mA typ / 98 mA max. Temperature −40…85 °C. Total stability ±20/±31.5/±61.5 ppm for the ±7/±20/±50 ppm temperature options — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- Jitter:
  - differential (> 500 MHz): 0.26 ps typ / 0.40 ps max (12 kHz–20 MHz);
  - CMOS (10–160 MHz): its own row, with a maximum offset of 2 MHz for 10–50 MHz outputs. The extracted values are misaligned (about 0.6 ps).
  - period jitter (any output, N = 1000): 2 ps RMS and 14 ps pk-pk typ.
  — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- Skyworks AN575 names the Si514, Si570 and Si598 as I2C oscillators usable as DCOs in FPGA-based ADPLLs — [Skyworks AN575 Rev 0.1](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN575.pdf)

#### Skyworks Si514 (any-frequency I2C XO) — datasheet Rev 1.2, August 12 2021
- Covers 100 kHz to 250 MHz, with CMOS/Dual CMOS to 212.5 MHz. Resolution is 0.026 ppb. Outputs are LVPECL/LVDS/HCSL or CMOS on 3.3/2.5/1.8 V. Listed applications include "All-digital PLLs" and "DAC+ VCXO replacement" — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
- "Frequency Range for Small Frequency Change (Continuous Glitchless Output)" is ±1000 ppm from centre (the section is titled "sub ±1000 ppm"). "each update of M requires 100 µs to settle". "It is not possible to implement a frequency change ≥1000 ppm using multiple small frequency changes without changing the center frequency and recalibrating the VCO". A large change takes ≤ 10 ms with the output squelched — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
- Idd for CMOS at 100 MHz is **21 mA typ / 26 mA max**. Jitter (LVPECL, 156.25 MHz) is 0.8 ps typ / 1.0 ps max over 12 kHz–20 MHz, with period jitter ≤ 1.3 ps RMS and ≤ 11 ps pk-pk. CMOS phase jitter over 1.875–20 MHz is 0.25/0.35 ps. Additive jitter from 100 mVpp supply sine is 3.0–3.5 ps. Temperature −40…85 °C — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)

#### TI LMK61E0M (LVCMOS member of the LMK61E0x family) — SNAS692A, January 2017, revised May 2017
- "Supports 3.3-V LVCMOS Output up to 200 MHz" on two outputs (OUT0, OUT1). The package is a 7 × 5 mm 8-pin QFM. Temperature −40…85 °C. Total frequency tolerance ±25 ppm. Default frequency 70.656 MHz from EEPROM, "fully programmable in-system through I2C" — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- "Glitch-Less Frequency Margining: Up to ±1000 ppm From Nominal". Table 6.10 gives a margining range of −1000…+1000 ppm. "The PLL feedback divider can be updated to adjust the output frequency without spikes or glitches in steps of <1ppb using a PFD of 12.5 MHz … or in steps of <5.2 ppb using a PFD of 100 MHz" — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- DCXO mode (§8.4.2.1) addresses a PLL "implemented in another device like an FPGA". The numerator "must be written on every attempt MSB first and LSB last to ensure that the output frequency does not jump". "a total of 46 bits needs to be updated leading to a maximum update rate of 8.7 kHz with a maximum I2C rate of 1 Mbps". The minimum step is 0.55 ppb (VCO 5.6 GHz, doubler off, R = 4) or 4.96 ppb with the doubler on — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- Synthesis: VCO 4.6–5.6 GHz, FOUT = FVCO/(P·OUTDIV) with P = 4 or 5 and OUTDIV 6–256. STEPSIZE = FREF·D/(R·P·OUTDIV·DEN). DEN is up to 4,194,303 — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- Jitter is 500 fs typ / 1000 fs max RMS (12 kHz–20 MHz) **for fOUT ≥ 50 MHz**, fractional-N, LVCMOS. Idd is **140 mA typ / 180 mA max**, or 120 mA with the output disabled — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- Status: TI.com shows "ACTIVE" but both LMK61E0M-SIAR and -SIAT are out of stock. TI lists the LMK6C, a fixed-frequency BAW LVCMOS oscillator, as having the "same functionality with different pin-out" — [TI LMK61E0M product page](https://www.ti.com/product/LMK61E0M); [TI LMK61E0M-SIAR part details](https://www.ti.com/product/LMK61E0M/part-details/LMK61E0M-SIAR)
- Broker listings show LMK61E0M-SIAR at 4,101 pcs and -SIAT at 889 pcs, with no price (aggregator data) — [Findchips LMK61E0M](https://www.findchips.com/search/LMK61E0M)

#### TI LMK61E07 — SNAS722B, December 2017, revised August 2023
- "The output on LMK61E07 can be configured as LVPECL, LVDS, or HCSL", so **there is no LVCMOS**. It has the same "Glitch-Less Frequency Margining: Up to ±1000 ppm" and the same DCXO mode (8.7 kHz maximum update, 0.55 ppb minimum step). Idd (LVPECL) is 162 mA typ / 208 mA max. Temperature −40…85 °C. Package 7 × 5 mm, 6 pins — [LMK61E07 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e07.pdf)
- Pitfall: "Glitch-less frequency margining in DCXO mode is achieved by adjusting the numerator of the feedback divider without changing the integer value of the divider, which could cause a frequency glitch". A fractional part near ½ should be chosen. The datasheet example at 70.656 MHz yields limits of "+955 ppm and … −1365 ppm from nominal" at a 0.58 ppb step — [LMK61E07 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e07.pdf)

#### TI LMK61E2 — SNAS674C, September 2015, revised May 2025
- Outputs are LVPECL (≤ 1 GHz), LVDS (≤ 900 MHz) and HCSL (≤ 400 MHz) from 10 MHz; there is no LVCMOS. Jitter is 90 fs typ. Total tolerance ±50 ppm. Idd is 152–162 mA typ / 196–208 mA max. Temperature −40…85 °C. I2C is 100/400 kHz — [LMK61E2 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e2.pdf)
- Fine margining works by changing the integrated crystal's load capacitance (R16/R17), "implemented in a manner such that the output … undergoes a smooth monotonic change in frequency." Coarse margining works through the output divider — [LMK61E2 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e2.pdf)
- SNAA283 (October 2015): the LMK61E2 margining target is "+/- 100ppm" for Ethernet testing. On the fractional-numerator approach it says "It is highly recommended to re-calibrate the PLL after the fractional portion of the feedback divider has been updated via I2C". Output-divider changes "could result in glitches" — [TI SNAA283](https://www.ti.com/lit/an/snaa283/snaa283.pdf)

#### Aeonsemi AS5003 "Arcadium" (quartz-free, MEMS-free) — datasheet Rev 0.9, footer "This information applies to a product under development"
- Any frequency via I2C: 10 kHz–350 MHz differential, 10 kHz–212.5 MHz LVCMOS, at up to 0.026 ppb resolution. I2C runs at 100/400 kbps or 1 Mbps. Outputs are LVPECL, LVDS, CML, HCSL, CMOS and Dual CMOS on 1.8–3.3 V. Packages 3.2 × 5 and 2.5 × 3.2 mm, 6 pins — [AS5003 datasheet](https://media.digikey.com/pdf/Data%20Sheets/Aeonsemi/AS5003.pdf)
- "Frequency Range for Small Frequency Change (Continuous Glitchless Output)" is ±970 ppm from centre, with DCXO-feature settling of 8 µs. Jitter is 350 fs typ (12 kHz–20 MHz, CMOS and differential; differential max 750 fs). Total stability ±50 ppm. Temperature −40…85 °C, or −40…105 °C "only with VDD = 1.8V". Idd roughly 40–70 mA; the table is misaligned — [AS5003 datasheet](https://media.digikey.com/pdf/Data%20Sheets/Aeonsemi/AS5003.pdf)

#### VCXO + DAC alternative (analog control) — SiTime SiT3808, datasheet Rev 1.02, 25 February 2022
- 1–80 MHz LVCMOS VCXO. Pull range ±25, ±50, ±100, ±150, ±200, ±400, ±800 or ±1600 ppm. Linearity 0.1 % typ / 1 % max. Control-voltage bandwidth 8 kHz (16 kHz option). Idd 31/33 mA. RMS phase jitter 0.5/1 ps and period jitter 1.5/2 ps (20 MHz). Temperature −20…70 or −40…85 °C — [SiT3808 datasheet](https://www.sitime.com/datasheet/SiT3808)
- AN10041: "Typically, VCXOs exhibit a maximum PR of ±150 ppm". Its quartz example DSV753SV has ±150 ppm against the SiT3907 DCXO's ±1600 ppm. "Phase noise of VCXOs is largely dependent on PR", while "DCXO phase noise is not influenced by PR and noise on its controlling input". VCXO linearity is "typically in the 2 to 5% range" against DCXO "better than 0.1%" — [SiTime AN10041 Rev 1.1](https://www.sitime.com/sites/default/files/hiddenresources/AN10041-Designing-with-SiT39xx-DCXOs-SIT.pdf)
- AN575: a DAC + VCO "functional equivalent of a DCO" (Xilinx XAPP854) avoids serial-bus limits on loop bandwidth. It must be weighed against "the cost, complexity, and likely higher noise contribution of another component in the signal path" — [Skyworks AN575 Rev 0.1](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN575.pdf)

#### Other vendors screened (search-level only)
- Microchip DSC2133/DSC2233 is a "Low-Jitter I2C/SPI Programmable Dual LVDS Oscillator" (LVDS). No DCO claim was seen and it was not evaluated — [Microchip DSC2133/DSC2233 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/DSC2133-DSC2233-Low-Jitter-I2C-SPI-Programmable-Dual-LVDS-Oscillator-DS20006231A.pdf)
- Renesas 8N3Q001 is a quad-frequency I2C-programmable XO (15.476–866.67 MHz). No DCO/fine-tune claim was seen — [Renesas 8N3Q001](https://www.renesas.com/en/products/8n3q001)

### Inferences
- **Jitter is not the discriminator.** Every candidate's intrinsic RMS phase jitter is 0.2–1 ps (period jitter 1–2 ps RMS) against a budget of about 8 ps RMS. That is roughly a 10× margin, and 35–70× better than the CS2100-CP's 70 ps RMS period jitter. This is inferred by comparing datasheet numbers with the requirement; the integration bands differ and are not all at 45/49 MHz.
- **Ranking for this application (LVCMOS + I2C + ≥ ±1000 ppm):**
  1. SiT5358-class DCTCXO with a ±1200 or ±1600 ppm range. It is linear, has ppt steps, a 38 kHz update rate, ~44 mA, and goes to 105 °C. It needs two order codes and is costly as a ±50 ppb Super-TCXO. The same DCO also sits in the ±0.5–2.5 ppm families: SiT5156 (industrial) and SiT5186 (AEC-Q100, not yet in production). These are presumably cheaper, but no price was found.
  2. Si570: ±3500 ppm, one part for both rates, 90 mA, older design, 400 kbps I2C.
  3. LMK61E0M: one part for both rates, but 140 mA, jitter unspecified below 50 MHz, and out of stock at TI.
  4. Si549/Si548, AS5003 and Si514, using the start-up re-centering strategy from KQ2.
- **LMK61E0M's glitch-less window at the MOST rates**, computed from the datasheet equations at PFD 12.5 MHz with the fraction kept off the integer boundaries (inference; the datasheet only guarantees ±1000 ppm):
  - 45.1584 MHz: P = 4, OUTDIV = 30, FVCO = 5419.008 MHz, N = 433.52064, window −1201/+1106 ppm, step 0.55 ppb.
  - 49.152 MHz: P = 4, OUTDIV = 24, FVCO = 4718.592 MHz, N = 377.48736, window −1291/+1358 ppm, step 0.63 ppb.
  - With PFD 100 MHz the numerator window is arithmetically ±7,500 ppm or more, but the VCO band may not follow without recalibration. Nothing above ±1000 ppm should be assumed.
- For battery/standby power, the Si514 (21 mA) and SiT5358/SiT5186 (~44 mA) are far better than the Si549 (87 mA), Si570 (90 mA) or LMK61E0M (140 mA).
- The SiT3907 is technically attractive: LVCMOS, ±1600 ppm, 1 ppb, smooth updates, 12.5 k updates/s, and the oldest well-documented DCXO. The 1-wire tri-level DP interface is easy from an FPGA with one tri-state pin and resistor divider, per the datasheet's circuit. It is excluded only by the "I2C" requirement; its datasheet dates from 2014.

### Gaps
- Most parts publish no jitter at exactly 45.1584/49.152 MHz. LMK61E0M jitter is specified only for fOUT ≥ 50 MHz, the SiT5358 at 10/50 MHz, and the Si570 CMOS row could not be read reliably.
- No manufacturer specifies a maximum phase or time error during a DCO step. "Glitch-free", "smooth" and "continuous" are qualitative, backed only by settling-time specs (SiTime 16.5–20 µs to 0.5 %, Skyworks ≤ 100 µs, AS5003 8 µs).
- Lifecycle status of the Skyworks parts (Si549/548/544/570/514) could not be read; the Skyworks product and lifecycle pages render client-side. Their datasheets were re-issued under Skyworks numbering in 2021–2023. Skyworks is in the middle of its Qorvo combination per its FY2026 Q3 release, and no timing-product divestiture was found in search — [Skyworks Q3 FY2026 release](https://investors.skyworksinc.com/news-releases/news-release-details/skyworks-delivers-solid-third-quarter-fiscal-year-2026-results)
- No price or stock was found for the Si549/Si548/Si544/Si570/Si514, SiT3907, SiT5156 or SiT5386. Findchips returned nothing for Si549, SiT3907 and SiT5156.
- The SiTime family-page claim of "up to ±150,000 ppm" pull over a one-wire interface is not tied to a specific part in the documents read.
- SiT3907 supply current, and SiT5358/SiT5186 period jitter, could not be read unambiguously from the extracted tables.
- The TI LMK61E07 and LMK61E2 lifecycle pages were not fetched. The AS5003's production status in 2026 is unknown.

## Key question 2 — Can one part cover both frequencies at runtime, or are two parts (or a two-order-code BOM) needed?

### Takeaway
It depends on the family.
- **Two order codes are needed** for SiTime's Super-TCXO/DCTCXO parts (SiT5358, SiT5186, SiT5386), for the SiT3907 DCXO and for the SiT3808 VCXO. Their output frequency is factory-programmed and their pull range (≤ ±3200 ppm) is far smaller than the 8.84 % gap between 45.1584 and 49.152 MHz.
- **One part is enough** with the fully I2C-programmable families: Si549/Si548/Si544, Si570, Si514, LMK61E0M, AS5003, and the (differential-only) SiT3521. Each needs one "large" frequency change at start-up, which squelches or interrupts the output for between 0.4 and 40 ms. That is harmless if it happens before the repeater starts regenerating.

### Cited Findings
- SiT5358: "Any frequency from 1 MHz to 60 MHz in 1 Hz steps" / "Factory programmable options"; the frequency is set in the ordering code. In DCTCXO mode "The maximum output frequency change is constrained by the pull range limits" (±6.25…±3200 ppm) — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- SiT5186/SiT5386 "can be factory programmed for any combination of frequency, stability, voltage, and pull range" — [SiT5186 datasheet](https://www.sitime.com/datasheet/SiT5186); [SiT5386 product page](https://sitime.com/products/automotive-tcxos/sit5386)
- SiT3907 is "Factory programmable between 1 MHz and 220 MHz"; DCXO registers only pull around that nominal — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- SiT3521 any-frequency mode re-programs 1–340 MHz in 1 Hz steps over I2C/SPI. The output is disabled (≤ 2.3 µs) until the PLL relocks, with settling ≤ 421 µs. Outputs are differential only — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521)
- Si549 is "I2C programmable to any frequency from 0.2 to 1500 MHz" and supports "one, two, or four user-defined startup frequencies" selected by FS pins, with FS-change settling ≤ 10 ms. A large change beyond ±950 ppm settles in ≤ 40 ms with "Output Squelched during Frequency Transition" — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Si570 is programmable 10–945 MHz (CMOS 10–160 MHz). A change beyond the ±3500 ppm window makes the output "momentarily stop and start at any arbitrary point during a clock cycle", takes up to 10 ms, and downstream logic "may have to be reset" — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- Si514: "To change the frequency by ≥1000 ppm, the user must change the center frequency", which requires VCO recalibration with the output squelched (≤ 10 ms) — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
- LMK61E0M: "the device registers and EEPROM settings are fully programmable in-system through I2C", with a factory-programmed EEPROM start-up default — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf). On the sibling LMK61E2, "Setting R72.1 to 1 causes a VCO recalibration and is necessary after device reconfiguration" — [LMK61E2 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e2.pdf)
- AS5003 "is fully programmable to any frequency from 10 kHz to 350 MHz"; "Configurations are changeable by users via I2C interface upon startup" — [AS5003 datasheet](https://media.digikey.com/pdf/Data%20Sheets/Aeonsemi/AS5003.pdf)
- AN575: "ADPLLs can control a DCO as if it has virtually infinite Absolute Pull Range (APR)" — [Skyworks AN575 Rev 0.1](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN575.pdf)

### Inferences
- 49.152 / 45.1584 = 1.08844, i.e. +8.84 % (+88,435 ppm). That is about 28× the largest DCO pull half-range (±3200 ppm), so no factory-set SiTime part can serve both rates.
- For a fixed-frequency SiTime design there are three BOM options: (a) two SKUs/order codes, one per car family; (b) two footprints, one populated; (c) both populated with OE selecting one, which doubles the oscillator cost (~$36–113 each for the SiT5358 on distributor data).
- Deriving one rate from the other inside the FPGA would need an FPGA PLL/MMCM, which reintroduces the tens-of-ps jitter problem. That is inferred from general FPGA PLL behaviour and was not researched here.
- **Re-centering removes the ±950 ppm shortfall of the Si549-class parts.** At start-up the FPGA measures Fs with its frame-period counter, programs the any-frequency part to 1024 × Fs_measured with one squelched "large change", and then tracks with DCO steps inside ±950 ppm. The DCO then only has to absorb the measurement error, the 99 MHz reference's own ppm error, oscillator drift (±20–50 ppm total stability) and ring wander.
- Because the Si570 large-change output can produce runt pulses, the FPGA clock domain fed by the oscillator should be held in reset during the start-up re-programming.
- An Si549 ordered with two FS-selectable start-up frequencies (45.1584 and 49.152 MHz) gives a one-part, one-order-code BOM with no I2C needed for the rate choice.

### Gaps
- Whether a SiTime SiT5358/SiT5186 can have its pull-range register switched in-system glitch-free (the datasheets say pull range "can be controlled via I2C" but give no transition behaviour) was not established.
- LMK61E0M EEPROM write endurance (relevant if the detected rate is stored as the power-up default) was not extracted.
- Whether a MOST timing master can change Fs by more than ~±900 ppm during operation, forcing an in-service re-centre on Si549-class parts, is outside this research. It depends on ring behaviour.

## Key question 3 — Real limits of an FPGA-run loop through I2C (latency, step size, update rate) for tracking a ring that may be off by up to ±0.1 % and wanders slowly; practical feasibility of architecture B

### Takeaway
The I2C path is not the limit. Device update caps are 38 kHz (SiTime Elite DCO), 25/12.5 kHz (SiT3907), 8.7 kHz (LMK61E0x), and bus-limited for the Si549. End-to-end write-to-new-frequency latency is about 0.1–0.3 ms. Steps are 5 ppt–0.6 ppb. All of these exceed what a few-Hz loop needs by two to three orders of magnitude; the SiTime rule of thumb is update rate and 1/latency ≥ 10× loop bandwidth.

The real constraints are:
- **pull range** against the ±1000 ppm ring offset plus the oscillator's own tolerance: choose a SiTime ±1200/±1600 ppm range, or re-centre an any-frequency part;
- **acquisition**: at 1000 ppm the elastic FIFO slips about 49 k clocks/s, so a counter-based frequency-locked loop (FLL) must pre-steer before the FIFO loop closes;
- **write-sequencing rules**: LSW→MSW, register order, Freeze-M, never touching the integer divider;
- **bus-activity-induced jitter**: use a dedicated I2C bus.

Architecture B is feasible with off-the-shelf parts. The unresearched risk is the FPGA's own output-path jitter, not the oscillator.

### Cited Findings

#### Device-side update/latency/step limits (from datasheets)
- SiTime Elite DCO (SiT3521, SiT5358): "maximum … update rate is 38 kHz regardless of I2C/SPI bus speed". Tfdelay is 103 µs typ / 140 µs max and Tsettle 16.5/20 µs (to 0.5 %). Steps are 5 ppt (≤ ±200 ppm range) to 47 ppt (±1600) and 94 ppt (±3200) — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521); [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- SiT5186 (advance): 38 kHz maximum update rate. Delay about 22 µs, settling about 30 µs to 1 % (alignment ambiguous) — [SiT5186 datasheet](https://www.sitime.com/datasheet/SiT5186)
- SiT3907: 25 k updates/s (mode 1) or 12.5 k updates/s (mode 2). Frame-to-frequency delay ≤ 8 µs and settling ≤ 30 µs. Steps are 1 ppb (mode 2) or 49 ppb (mode 1 at ±1600 ppm) — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- Si549/Si548/Si544: updates "as fast as the max I2C bus speed of 1 MHz will allow". Small-change settling is ≤ 100 µs. The step is 0.0001164 ppm (116 ppt) — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- Si570: I2C ≤ 400 kbps. Small-change settling ≤ 100 µs. Resolution 0.09 ppb — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- Si514: "each update of M requires 100 µs to settle". Resolution 0.026 ppb — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
- LMK61E0M/LMK61E07: 46 bits per update give a "maximum update rate of 8.7 kHz with a maximum I2C rate of 1 Mbps". The minimum step is 0.55 ppb — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
- AS5003: small-change settling 8 µs. I2C runs at 100 k/400 k/1 Mbps — [AS5003 datasheet](https://media.digikey.com/pdf/Data%20Sheets/Aeonsemi/AS5003.pdf)

#### Application notes and papers on DCXO-based software/FPGA PLLs
- **SiTime, "Analysis of High-stability Controlled Oscillators for Low-bandwidth PLLs"** (S. Tabatabaei; no date in the text)
  - "For a guaranteed stable operation, typically the update rate and inverse of the update delay should be at least 10 times higher that the target loop bandwidth". The paper's example is 1 kHz bandwidth needing more than 10 kHz update and less than 100 µs delay.
  - Quantization: at 25,000 updates/s, 100 ppb resolution raises phase noise at offsets below 10 kHz, 10 ppb has "little impact", and "1 ppb or better resolution … effectively eliminate[s] any quantization impact". "even update rate in the range of 2500 update/s is sufficient" for 1 ppb.
  - Locked-loop frequency error from quantization "1ppb/sqrt(25000)=0.006ppb" over 1 s.
  - Phase-detector options: a high-speed PD at the output rate, or divided paths with a slow PD. For the latter, "the digitizer rate has to be at least 10 times higher than the loop filter bandwidth".
  — [SiTime paper PDF](https://www.sitime.com/sites/default/files/hiddenresources/Analysis-of-High-stability-SIT.pdf)
- **SiTime AN10041 Rev 1.1 "Designing with the SiT39xx Family of DCXOs"**
  - Low-bandwidth PLLs "typically have very low bandwidth, e.g. less than 1 kHz"; "High stability DCXOs, which exhibit ±1% or better linearity, are ideal for all digital low-bandwidth PLLs (ADPLL)".
  - APR = PR − F_stability − F_aging must be budgeted.
  - DCXO linearity is better than 0.1 %, against 2–5 % for VCXOs.
  - For the fastest updates "the next frame must be sent after 2 µs (Tf2f)".
  - The frequency update "does not lead to any interruptions of output oscillations. The frequency will switch from one value to the new value smoothly".
  — [SiTime AN10041 Rev 1.1](https://www.sitime.com/sites/default/files/hiddenresources/AN10041-Designing-with-SiT39xx-DCXOs-SIT.pdf); [AN10041 page](https://www.sitime.com/support/resource-library/application-notes/an10041-designing-sit39xx-family-dcxos-digitally)
- **SiTime AN10064 Rev 1.0 "Improved System Performance with Digital Frequency Tuning in Precision Super-TCXOs"**
  - Lists the DCO benefits: 5×10⁻¹² resolution "minimizes accumulated time error in synchronization applications"; no DAC; digital noise immunity; "No frequency pull non-linearity" because pulling is via the fractional feedback divider; 16 ranges from ±6.25 to ±3200 ppm.
  - The pull value is written LSW then MSW. "control logic changes the feedback divider value during Tdelay … then the output frequency starts to change and settles to 1% of the final frequency value within the Tsettle".
  - "The device output is not disabled during frequency change". "Read Reg1 value from the device as it may include control bits for other settings" before writing the MSW. The 38 kHz maximum update rate applies.
  — [SiTime AN10064 Rev 1.0](https://www.sitime.com/api/gated/AN10064-Improved-System-Performance-with-Digital-Frequency-Tuning.pdf)
- **Skyworks AN575 Rev 0.1 (September 23, 2021) "Introduction to FPGA-based ADPLLs"**
  - Architecture: reference divider → digital PD → digital loop filter → command conversion → I2C master → external Si514/Si570/Si598 DCO → feedback divider. The example runs on an Altera Cyclone III starter kit, with a flip-flop/counter phase detector clocked by a sampling clock fs.
  - Benefits listed: no drifting analog Vc node, flexible loop filters, freeze/hold modes, and "virtually infinite" APR.
  - It gives no quantitative loop design; "Additional details and performance measurements … will be included in future versions".
  — [Skyworks AN575](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN575.pdf)
- **TI** documents DCXO use directly in the LMK61E0x datasheets rather than a separate note: "In applications that require the LMK61E0 as part of a PLL that is implemented in another device like an FPGA, it can be used as a digitally controlled oscillator (DCXO)" — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf). TI's older SNAA283 targets ±100 ppm margining for Ethernet elastic-buffer testing, not closed-loop DCO use — [TI SNAA283](https://www.ti.com/lit/an/snaa283/snaa283.pdf)

#### Manufacturer-documented pitfalls
- **Atomic multi-byte updates:**
  - SiTime applies the change on the MSW write only, and the OE bit in the MSW register must be kept at 1 on software-OE parts or the output turns off — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521); [SiTime AN10064](https://www.sitime.com/api/gated/AN10064-Improved-System-Performance-with-Digital-Frequency-Tuning.pdf)
  - Si549 applies it on reg 233 (MSByte) — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
  - LMK61E0x: "MSB first and LSB last to ensure that the output frequency does not jump" — [LMK61E0M datasheet](https://www.ti.com/lit/ds/symlink/lmk61e0m.pdf)
  - Si570 needs Freeze-M around RFREQ writes — [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)
- **Do not cross the integer divider or the calibrated band:**
  - LMK61E0x "without changing the integer value of the divider, which could cause a frequency glitch" — [LMK61E07 datasheet](https://www.ti.com/lit/ds/symlink/lmk61e07.pdf)
  - Si514 cannot chain small changes past ±1000 ppm — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
  - Si54x beyond ±950 ppm needs FCAL with the output squelched — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf)
- **Bus activity couples into jitter:**
  - Si549: dedicated I2C bus or mux recommended; Si548 specifies 15 fs typ additive jitter with I2C active — [Si549 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si549-datasheet.pdf); [Si548 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si548-datasheet.pdf)
  - SiT3907 phase jitter rises from 0.6 to 0.65 ps typ and period jitter from 1.5 to 2 ps typ "With full activity on DP pin" — [SiT3907 datasheet](https://www.sitime.com/datasheet/SiT3907)
- **Temperature limits on bus speed:** SiT3521 has no Fast-mode Plus at −40…105 °C; the SiT5358 supports 1 MHz only to 85 °C — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521); [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358)
- **Supply noise:** Si514 additive jitter is 3.0–3.5 ps for 100 mVpp supply sine (10–500 kHz) — [Si514 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/Si514.pdf)
- **Aging and temperature are absorbed only if the range is budgeted:** "APR = PR − Fstability − Faging" — [SiT3521 datasheet](https://www.sitime.com/datasheet/SiT3521); [SiTime AN10041](https://www.sitime.com/sites/default/files/hiddenresources/AN10041-Designing-with-SiT39xx-DCXOs-SIT.pdf). The SiT5358 drifts ±50 ppb over −40…105 °C; XO-class parts (Si549/Si570/Si514) have ±20…±61.5 ppm total stability including aging — [SiT5358 datasheet](https://www.sitime.com/datasheet/SiT5358); [Si570/Si571 datasheet](https://www.skyworksinc.com/-/media/Skyworks/SL/documents/public/data-sheets/si570-71.pdf)

### Inferences (computed from the cited datasheet numbers; assumptions stated)
- **Bus time per update**, counting 9 SCL clocks per byte plus START/STOP:
  - SiTime DCO write (address, register, 4 data bytes): about 56 SCL cycles, i.e. about 140 µs at 400 kHz and 56 µs at 1 MHz.
  - Si549 ADPLL write (address, register, 3 bytes): about 47 cycles, i.e. about 118 µs at 400 kHz and 47 µs at 1 MHz.
  - End-to-end write→new frequency: SiTime about 0.26–0.30 ms at 400 kHz (bus + Tfdelay ≤ 140 µs + Tsettle ≤ 20 µs); Si549 up to about 0.22 ms (bus + ≤ 100 µs settling; only a maximum is specified).
- **Loop stability margin.** For a few-Hz loop the SiTime rule needs only about ≥ 30–50 Hz update rate and ≤ 10–30 ms delay. A 0.3 ms latency at a 5 Hz crossover costs about 360° × 5 Hz × 0.3 ms ≈ 0.5° of phase margin, which is negligible. Updating at 100 Hz–1 kHz uses under 2–15 % of a 400 kHz bus.
- **Step size and wander.** A residual limit cycle of ±1 LSB held for one update interval Tu moves the clock by about LSB × Tu:
  - At Tu = 10 ms (100 Hz): 0.05 ps (5 ppt), 0.47 ps (47 ppt, ±1600 ppm range), 1.2 ps (Si549 116 ppt), 5.5 ps (LMK61E0M 0.55 ppb), 490 ps (SiT3907 mode 1 at 49 ppb, so use mode 2 at 1 ppb).
  - These are low-frequency (≤ update-rate) phase-wander components, not broadband jitter, and are much smaller than the 20.3 ns symbol period at 49.152 MHz. Raising the update rate or using the finer-step parts shrinks them further.
- **Acquisition.** An initial ±1000 ppm error slips the elastic FIFO by about 49,152 clocks/s at 49.152 MHz (45,158 at 45.1584 MHz). The FIFO cannot be the acquisition detector unless it is impractically deep.
  - A counter FLL resolves frequency against the 99 MHz reference with a 1-count granularity of 485 ppm per frame, 10.1 ppm over 48 frames (1 ms), 1.01 ppm over 10 ms, 0.10 ppm over 0.1 s and 0.01 ppm over 1 s. A 10–100 ms FLL measurement therefore puts the DCO within about 1–0.1 ppm of the ring, relative to the 99 MHz crystal's own error, before the FIFO-based type-II loop closes.
  - The residual 0.1–1 ppm then slips only about 5–50 clocks/s, which a few-Hz PI loop removes within about a second. That is a design estimate; the MOST lock-time requirement was not checked.
- **Tracking slow wander.** For a type-II loop, a frequency ramp R (fractional/s) gives a steady phase offset of about R·f0/(4π²·fn²) clock cycles. Example assumption: R = 1 ppm/s, f0 = 49.152 MHz, fn = 3 Hz gives about 0.14 cycles, easily held by a FIFO a few symbols deep. The ring's actual wander rate is not known here.
- **Range budget.**
  - Fixed-centre SiTime: pick PR ≥ ±1200 ppm; at ±1600 ppm the APR is ±1545…±1585 ppm (SiT3521) and about ±1599 ppm (SiT5358), comfortably above ±1000 ppm plus drift.
  - Si549-class (±950 ppm): re-centre once at start-up, after which ±950 ppm easily covers ±50 ppm drift and wander.
  - LMK61E0M: stay inside the datasheet ±1000 ppm, which is borderline for a ±1000 ppm ring plus its own ±25 ppm tolerance unless re-centred too. Re-centring is possible because it is fully programmable.
- **Jitter budget.** Oscillator intrinsic jitter (≤ 1 ps RMS) uses about 1/8 of the ≈ 8 ps RMS allowance. DCO step activity adds only low-frequency wander, and a dedicated I2C bus limits coupling. The remaining budget belongs to the FPGA path from clock input through global buffer to output register and IO, plus board supply noise; those were not researched here.
- **Overall feasibility.** Architecture B is practical. It trades the CS2100-CP's 70 ps RMS period jitter for about 1–2 ps RMS period jitter from any listed DCO, moves loop control into FPGA logic the project already has, and needs no DAC.
  - Recommended BOM shape for a car: an I2C LVCMOS DCTCXO with ±1600 ppm range, factory-set to 45.1584 and 49.152 MHz as two order codes. SiT5358 is industrial and orderable now; SiT5186/SiT5386 are AEC-Q100 but pre-production.
  - One-part alternatives: Si549/Si548 with re-centring, or Si570 (±3500 ppm).

### Gaps
- The MOST SP1 tUJ1 measurement bandwidth (which part of the DCO-induced wander counts as "uncorrelated jitter") was not checked. It is needed to set the loop's update rate and LSB with certainty and is in the local MOST PHY spec, not researched here.
- Jitter added by the FPGA clock input, routing and output path, and by the board, was not researched. It is the likely dominant term once the CS2100 is removed.
- No manufacturer publishes a closed-loop measurement of an FPGA+DCXO PLL with these specific parts. AN575 promises measurements in "future versions" but Rev 0.1 has none.
- No IEEE 1588/SyncE/audio-clock-recovery application note giving numeric loop coefficients for these DCXOs was found beyond the SiTime paper, AN10041 and AN10064. The SiTime IEEE 1588 page was surfaced in search but not read — [SiTime precision oscillators for IEEE 1588](https://www.sitime.com/precision-oscillators-ieee-1588)
- The ring's real wander rate (ppm/s) and any in-service Fs changes by the timing master are not characterised here. The type-II tracking estimate uses an assumed 1 ppm/s.
