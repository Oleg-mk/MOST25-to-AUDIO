# kHz-input jitter attenuators from ADI, Microchip, Cirrus Logic and other vendors as the MOST25 regenerator clock (alternatives to Si5319)

Scope: Analog Devices, Microchip, Cirrus Logic and "other" vendors (SiTime, Diodes, onsemi). Skyworks, TI and Renesas were left out because other researchers in this session are covering them. All web pages and prices were retrieved on 2026-09-24. Unless a line says "distributor" or "inferred", the number comes from a manufacturer document.

How the budget is read here (restating the brief, not new data): tUJ1 ≤ 0.0045 UI. At 48 kHz, UI = 1/49.152 MBd = 20.35 ns, so the limit is 91.6 ps p-p. At 44.1 kHz, UI = 22.14 ns, so the limit is 99.6 ps p-p. For Gaussian jitter at BER 1e-9, p-p ≈ 12 × rms, which gives about 7.6 ps rms (48 kHz) or 8.3 ps rms (44.1 kHz). Datasheet jitter is quoted over different integration bands (12 kHz–20 MHz, 10 Hz–30 MHz, AES-12 bands, period jitter), and each figure below keeps its band.

## Which of these meet the ~8 ps rms budget with a 44.1/48 kHz input, from a 3.3 V supply, with an LVCMOS output, at reasonable power and complexity?

### Takeaway
The only parts found that meet the jitter budget from a kHz reference and have a native 3.3 V LVCMOS output are these:
- **ADI AD9557, and its 6-output sibling AD9558.** Input from 2 kHz, 3.3 V CMOS input thresholds, a 3.3 V CMOS output, and datasheet jitter from a 2 kHz reference into the 3.3 V CMOS driver of 3.22 ps rms (10 Hz–30 MHz) and 0.32 ps rms (12 kHz–20 MHz). Typical power is about 0.55 W, and the price is $24.37 per 1k. It needs 1.8 V and 3.3 V rails plus a 10–50 MHz crystal.
- **Microchip ZL30253, or ZL30252 with an external EEPROM.** Input from 1 kHz, CMOS outputs at 1.5–3.3 V, 0.16–0.45 ps rms, four configurations selectable by pin, about 0.67 W. It needs 1.8 V and 3.3 V rails and a 25–60 MHz crystal (doubled) or a 93–130 MHz XO.

Other parts either miss a requirement or carry a weakness:
- **ADI AD9545, AD9546 and AD9542** easily meet the jitter budget. However, they run from a single 1.8 V supply, their outputs are HCSL/CML only, and their CMOS reference inputs are 1.2/1.8 V. They would need level translation on both sides.
- **ADI AD9553** is 3.3 V-only, accepts inputs from 8 kHz, has CMOS outputs and costs $8.29 per 1k. It can make both frequencies exactly as an integer-N PLL, but it is a plain analog PLL (about 170 Hz loop, external loop filter, no NVM). Its jitter below 12 kHz is not given in the datasheet text.
- **SiTime SiT95145** meets every electrical requirement and needs no crystal (integrated MEMS reference). It is a 64-pin, roughly 1.1 W device (full configuration), and no price was found.
- **Excluded for input frequency:** none of the Microchip ZL30250/1 or ZL30260–ZL30267 parts accept a kHz input; their minimum is 9.72 MHz.

### Cited Findings

#### ADI AD9557 (Dual-Input Multiservice Line Card Adaptive Clock Translator): strongest ADI fit
- **Documents.** Datasheet Rev. C (revision history "9/2016—Rev. B to Rev. C"; initial 10/2011). The product page says Rev. C is the most up-to-date revision. — [AD9557 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf) (the text was read from the identical Rev. C copy at [marutsu mirror](https://www.marutsu.co.jp/contents/shop/marutsu/ds/AD9557.pdf)); [AD9557 product page](https://www.analog.com/en/products/ad9557.html)
- **Status and price.** Lifecycle "RECOMMENDED FOR NEW DESIGNS". 1ku list price "Starting From $24.37". — [AD9557 product page](https://www.analog.com/en/products/ad9557.html). Distributor: DigiKey shows AD9557BCPZ at $50.21 unit price, stock not shown — [DigiKey search](https://www.digikey.com/en/products/result?keywords=AD9557BCPZ)
- **Input.**
  - Input references 2 kHz to 1250 MHz. The single-ended CMOS frequency range is 0.002–300 MHz.
  - The single-ended input has a "3.0 V to 3.3 V Threshold Setting" with VIH ≥ 2.0 V and VIL ≤ 1.0 V.
  - Minimum input slew rate is 40 V/µs, and minimum pulse width high/low is 1.5 ns.
  - A 3.3 V LVCMOS 44.1/48 kHz square wave is therefore directly acceptable.
  - Source: [AD9557 datasheet, Table 7](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **DPLL.** PFD input 2–100 kHz. Loop bandwidth 0.1–2000 Hz in Table 12. The features list says "0.1 Hz to 5 kHz (2 kHz maximum for <0.1 dB of peaking)". R divider 1 to 2^20. Integer feedback N1 180–131,072 plus a 23-bit fractional part with programmable modulus. — [AD9557 datasheet, Table 12 and p.1](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Frequency plan limits.**
  - The DPLL's 30-bit DCO outputs 175–200 MHz.
  - The APLL has an integer N2 feedback divider, a VCO range of 3.35–4.05 GHz, a nominal bandwidth of 250 kHz, and one external 6.8 nF capacitor.
  - The distribution path is RF dividers ÷3 to ÷11, followed by 10-bit channel dividers of 1–1023 (the overview text says 1–1024).
  - Output range is 360 kHz–1250 MHz.
  - Source: [AD9557 datasheet, pp. 30, 36](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Can it make 45.1584 and 49.152 MHz? (inferred from the limits above)** Yes, both.
  - 45.1584 MHz: RF÷5 × channel÷15 gives VCO = 3386.88 MHz. N2 = 17 gives a DCO of 199.23 MHz (in range). With R = 1, fPFD = 44.1 kHz and N1 = 4517 + 11/17, which the programmable modulus can represent exactly.
  - 49.152 MHz: RF÷8 × channel÷9 gives VCO = 3538.944 MHz. N2 = 18 gives a DCO of 196.608 MHz. N1 = 4096 exactly at fPFD = 48 kHz.
- **Outputs.**
  - Two output pairs, each either one LVDS/HSTL differential output or two single-ended CMOS outputs.
  - OUT0 supports 1.8 V or 3.3 V CMOS. OUT1 supports 1.8 V CMOS only.
  - 3.3 V CMOS (OUT0), strong drive: 0.36–250 MHz, rise/fall 0.4 ns into 10 pF.
  - Source: [AD9557 datasheet, pp. 10, 30](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Jitter (Table 17).**
  - Conditions: 49.152 MHz crystal system clock, "fREF = 2 kHz; fOUT = 70.656 MHz; fLOOP = 100 Hz; HSTL and/or 3.3 V CMOS Driver".
  - 10 Hz–30 MHz: 3.22 ps rms. 5 kHz–20 MHz: 338 fs rms. 12 kHz–20 MHz: 324 fs rms. 10 kHz–400 kHz: 278 fs rms. 100 kHz–10 MHz: 210 fs rms.
  - Other configurations give 285–343 fs rms (12 kHz–20 MHz).
  - Source: [AD9557 datasheet, Table 17](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Supplies and power.**
  - DVDD3 and AVDD3 at 3.135–3.465 V. DVDD and AVDD at 1.71–1.89 V.
  - Typical-configuration currents: IAVDD (1.8 V) 162 mA typ / 215 max; IDVDD (1.8 V) 20 / 28 mA; IAVDD3 (3.3 V) 49 / 63 mA; IDVDD3 (3.3 V) 18 / 26 mA.
  - Power dissipation: typical configuration 0.36 min / 0.55 typ / 0.76 max W; all blocks running 0.61 typ / 0.85 max W.
  - Incremental power: a 3.3 V CMOS output at 250 MHz with 80 pF adds 27 mW typ; a single-ended reference input adds 7 mW.
  - Source: [AD9557 datasheet, Tables 1–3](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **System clock.** A 10–50 MHz fundamental AT-cut crystal (motional resistance ≤ 100 Ω), or a 10–600 MHz reference clock. The jitter tables use a 49.152 MHz crystal or a 19.2 MHz TCXO. — [AD9557 datasheet, Table 6 and Tables 17–18](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Holdover and lock.**
  - Automatic or manual holdover ("GR-1244 Stratum 3 stability in holdover"). Initial holdover frequency accuracy is < 0.01 ppm, excluding the system-clock drift.
  - Phase lock detector threshold range 0.001–65.5 ns; frequency lock detector 0.001–16,700 ns.
  - Status appears on M3–M0 and IRQ.
  - Source: [AD9557 datasheet, Tables 13–14](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Control and configuration.**
  - SPI or I²C interface.
  - The on-chip EEPROM is downloaded at power-on reset. Its "conditional processing" is selected by the three-level M3/M2 pins (up to 8 conditions), so a strap or the FPGA can select a 44.1 kHz-family or 48 kHz-family profile at power-up.
  - The APLL must be calibrated at startup and whenever its input frequency changes by more than ±100 ppm. A 44.1↔48 family change therefore needs recalibration.
  - ADI's evaluation software includes a frequency-planning wizard.
  - Source: [AD9557 datasheet, pp. 36, 43](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9557.pdf)
- **Package and temperature.** 40-lead 6 mm × 6 mm LFCSP, −40 to +85 °C. No automotive grade is mentioned in the datasheet or on the product page. — [AD9557 product page](https://www.analog.com/en/products/ad9557.html)

#### ADI AD9558 (Quad Input Multiservice Line Card Adaptive Clock Translator with Frame Sync): same core as AD9557, six outputs
- **Documents, status, price.** Datasheet Rev. D, 12/2024 (the only Rev. D change was terminology: "Changed Master to Main and Slave to Subordinate"). "RECOMMENDED FOR NEW DESIGNS". 1ku from $26.40. — [AD9558 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9558.pdf); [AD9558 product page](https://www.analog.com/en/products/ad9558.html)
- **Features.** Four reference inputs at 2 kHz–1250 MHz. Six output pairs, each LVDS/HSTL or two single-ended CMOS. Outputs 352 Hz–1250 MHz. Loop bandwidth 0.1 Hz–5 kHz (2 kHz maximum for < 0.1 dB peaking). On-chip EEPROM with multiple power-up profiles and a pin-program function. 64-lead 9 × 9 mm LFCSP. — [AD9558 product page](https://www.analog.com/en/products/ad9558.html)
- **3.3 V CMOS.** Available on OUT0 and OUT5 only: strong drive to 250 MHz, rise/fall 0.4–0.6 ns. — [AD9558 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9558.pdf)
- **Jitter.** Same rows as AD9557: "f = 2 kHz; f = 70.656 MHz; f = 100 Hz; HSTL and/or 3.3 V CMOS Driver" gives 3.22 ps rms (10 Hz–30 MHz) and 324 fs rms (12 kHz–20 MHz). With a 19.2 MHz TCXO system clock and a 0.1 Hz loop, the same translation gives 970 fs rms (10 Hz–30 MHz) and 404 fs rms (12 kHz–20 MHz). — [AD9558 datasheet, Table 17](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9558.pdf)
- **Supplies and power.**
  - 3.3 V (DVDD3, AVDD3) and 1.8 V (DVDD, AVDD).
  - Typical currents: IDVDD3 19 mA, IDVDD 20 mA, IAVDD3 70 mA, IAVDD 230 mA.
  - Power: typical configuration 0.47 min / 0.74 typ / 1.02 max W; all blocks 1.0 typ / 1.32 max W.
  - Source: [AD9558 datasheet, Tables 1–3](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9558.pdf)

#### ADI AD9545 (Quad Input, 10-Output, Dual DPLL/IEEE 1588 1 pps Synchronizer and Jitter Cleaner)
- **Documents, status, price.** Datasheet Rev. C (11/2021; ©2020–2021). "RECOMMENDED FOR NEW DESIGNS". 1ku from $24.30. — [AD9545 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf); [AD9545 product page](https://www.analog.com/en/products/ad9545.html). Rev. 0 (2017) was also read: [marutsu mirror](https://www.marutsu.co.jp/contents/shop/marutsu/ds/AD9545.pdf)
- **Input.**
  - "Dual DPLL synchronizes 1 Hz to 750 MHz". Rev. 0 said 1 Hz–500 MHz.
  - The single-ended reference receivers are "1.2 V and 1.8 V CMOS" (DC-coupled) or 1.2 V AC-coupled with a 360–1200 mV p-p swing. A 3.3 V LVCMOS source therefore needs a divider or AC coupling.
  - The digital phase detector input range is 1 Hz–200 kHz.
  - Source: [AD9545 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf); [product page](https://www.analog.com/en/products/ad9545.html)
- **Loop bandwidth.** 10⁻⁴ Hz to 1850 Hz, with the constraint (fPFD/bandwidth) ≥ 20. — [AD9545 datasheet, Table 10](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf)
- **Frequency plan limits.**
  - The DPLL's 48-bit DCO outputs 162–350 MHz.
  - APLL0 VCO 2424–3232 MHz; APLL1 VCO 3232–4040 MHz. APLL PFD 162–350 MHz.
  - The output is VCO ÷ 2, then a 32-bit Q divider (half-divide available).
  - Source: [AD9545 datasheet Rev. 0, pp. 30 and Table 13](https://www.marutsu.co.jp/contents/shop/marutsu/ds/AD9545.pdf)
  - Inferred: 45.1584 MHz with Q = 27 gives VCO = 2438.55 MHz; 49.152 MHz with Q = 25 gives VCO = 2457.6 MHz. Both fall within APLL0's range.
- **Outputs.**
  - Five pairs, each "differential LVDS/HCSL/CML or 2 single-ended outputs (1 Hz to 500 MHz)". These are current-mode drivers from the 1.8 V VDD.
  - Single-ended swing is about 0.51–0.63 V p-p into 50 Ω.
  - There is no 3.3 V LVCMOS output specification.
  - Source: [AD9545 datasheet Rev. C, Table 10](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf)
- **Jitter.** 213–323 fs rms (12 kHz–20 MHz) across the six listed configurations with a 52 MHz crystal. One of these used a 1 Hz reference with a 50 mHz DPLL bandwidth and gave 235 fs rms. — [AD9545 datasheet, Table 22](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf)
- **Supplies and power.**
  - VDD 1.71–1.89 V (single 1.8 V with internal regulation). VDDIOA/B 1.71–3.465 V, for the serial port and M pins only.
  - IVDD 260 / 310 / 355 mA (typical configuration). Power 445 / 560 / 671 mW; all blocks 548 / 700 / 813 mW.
  - Source: [AD9545 datasheet, Tables 1–3](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf)
- **Other details.**
  - System clock: 25–52 MHz crystal, or 20–300 MHz reference. The reference design uses a 49.152 MHz crystal.
  - Holdover: automatic or manual.
  - Control: external EEPROM for autonomous initialization, SPI or I²C.
  - Package: 48-lead 7 × 7 mm LFCSP, −40 to +85 °C.
  - Source: [AD9545 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf); [product page](https://www.analog.com/en/products/ad9545.html)

#### ADI AD9546 (Dual DPLL Digitized Clock Synchronizer)
- **Documents, status, price.** Datasheet Rev. 0 (10/2020, 205 pages), the latest per the product page. "RECOMMENDED FOR NEW DESIGNS". 1ku from $24.36. — [AD9546 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9546.pdf); [AD9546 product page](https://www.analog.com/en/products/ad9546.html)
- **Features.** 1 Hz–750 MHz references (two differential or eight single-ended). Loop bandwidth 0.0001–1850 Hz. Five output pairs of LVDS/HCSL/CML, or two single-ended each (1 Hz–500 MHz). External EEPROM. Single 1.8 V supply. — [AD9546 product page](https://www.analog.com/en/products/ad9546.html)
- **Power.** VDD 1.71–1.89 V. IVDD 325 typ / 330 max mA. Power 585 typ / 760 max mW (typical configuration); all blocks 745 / 795 mW. Single-ended reference inputs are 1.8 V CMOS. — [AD9546 datasheet, Tables 2–4](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9546.pdf)
- **Jitter.** About 213–323 fs rms (12 kHz–20 MHz) in the phase-noise figures. — [AD9546 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9546.pdf)
- **Distributor.** DigiKey AD9546BCPZ: Active, 67 in stock, $49.72 (1), $36.07 (100), $34.89 (250), 10-week lead time. Output types listed as "Clock, CML, HCSL". Supply 1.71–1.89 V and 1.71–3.465 V. — [DigiKey](https://www.digikey.com/en/products/detail/analog-devices-inc/AD9546BCPZ/14637506)

#### ADI AD9542 (Quad Input, Five-Output, Dual DPLL Synchronizer and Adaptive Clock Translator)
- **Documents, status, price.** Datasheet Rev. 0 (9/2017). "RECOMMENDED FOR NEW DESIGNS". 1ku from $12.16, the cheapest of the ADI DPLL parts. — [AD9542 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9542.pdf); [AD9542 product page](https://www.analog.com/en/products/ad9542.html)
- **Input and loop.** Input from 2 kHz (1.2/1.8 V CMOS single-ended range 2 kHz–500 MHz); DPLL range 2 kHz–750 MHz. Digital phase detector 1 Hz–200 kHz. Loop bandwidth 0.0001–1850 Hz. — [AD9542 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9542.pdf)
- **Same platform as AD9545.** Same outputs (LVDS/HCSL/CML or two single-ended, 1 Hz–500 MHz), single 1.8 V supply, IVDD 260 / 310 / 355 mA, power 445 / 560 / 671 mW, jitter 213–323 fs rms (12 kHz–20 MHz), 48-lead 7 × 7 mm LFCSP, external EEPROM. — [AD9542 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9542.pdf); [product page](https://www.analog.com/en/products/ad9542.html)

#### ADI AD9553 (Flexible Clock Translator): the small, cheap, 3.3 V-only ADI option
- **Documents, status, price.** Datasheet Rev. A (10/2010; Rev. 0 was 4/2010). "RECOMMENDED FOR NEW DESIGNS" (shown in the product-family list on analog.com). 1ku "Starting From $8.29". — [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf); [AD9553 product page](https://www.analog.com/en/products/ad9553.html)
- **Architecture.** An integer-N analog PLL with an on-chip VCO (3350–4050 MHz), a 20-bit N divider (minimum 32), and a PFD range of 13.3 kHz–100 MHz. Inputs between 8 kHz and 13.3 kHz must use the ×2 multiplier. A VCO prescaler P0 (÷5 to ÷11) is followed by 10-bit P1/P2 output dividers. — [AD9553 datasheet, pp. 22–23 and Table 6](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Input.** The CMOS single-ended input covers 0.008–200 MHz. The datasheet says "the single-ended CMOS input is 3.3 V compatible", with VIH ≥ 1.62 V and VIL ≤ 0.52 V. — [AD9553 datasheet, Table 5](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Can it make 45.1584 and 49.152 MHz? (inferred from the limits above)** Yes, both, and exactly 1024 × Fs, through SPI programming (the pin-programmed tables do not include these ratios).
  - 44.1 kHz: fPFD = 44.1 kHz, N = 81,920, VCO = 3612.672 MHz, then P0 = 8 and P1 = 10.
  - 48 kHz: fPFD = 48 kHz, N = 73,728, VCO = 3538.944 MHz, then P0 = 8 and P1 = 9.
  - Both N values are ≥ 16,384, which puts the internal filter in its "low loop bandwidth (~170 Hz)" configuration.
- **Loop filter.** "The components primarily responsible for the bandwidth of the loop filter are external and connect between Pin 16 and Pin 17". The pin-programmed bandwidths are 170 Hz, 20 kHz and 75 kHz. — [AD9553 datasheet, p. 23 and Table 9](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Jitter.**
  - Figure 8, "fREF = 8 kHz, fOUT1 = 155.52 MHz": 1.27 ps rms (12 kHz–20 MHz) and 0.54 ps rms (50 kHz–80 MHz).
  - Table 9, CMOS output: 1.32 ps rms (12 kHz–20 MHz) and 0.45 ps rms (50 kHz–80 MHz) at 122.88 → 155.52 MHz.
  - Source: [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Outputs.** Two outputs, each LVPECL, LVDS or CMOS. CMOS runs up to 200 MHz. — [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Supply and power.** Single 3.3 V supply (3.135–3.465 V). Total current 162 mA typ / 185 max, measured with both channels at maximum frequency. The feature list says "<450 mW (under most conditions)". — [AD9553 datasheet, Table 1](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Other details.** A crystal is optional (10–52 MHz; 25 MHz in pin mode) and is needed only for holdover. A LOCKED pin shows lock status. Control is 3-wire SPI or pin strapping, with no EEPROM. Package 5 × 5 mm, −40 to +85 °C. — [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)

#### ADI parts checked and set aside (product-page data only)
- **AD9554.** Input 2 kHz–1000 MHz. Outputs are "8 differential clock outputs … HCSL, LVDS-compatible, or LVPECL-compatible", with no CMOS mode. Loop bandwidth 0.1 Hz–4 kHz. Off-chip EEPROM. 72-lead 10 × 10 mm. $34.65 per 1k, Rev. E. — [AD9554 product page](https://www.analog.com/en/products/ad9554.html)
- **AD9559.** Dual PLL. Input 2 kHz–1250 MHz. Four pairs of LVDS/HSTL or two single-ended CMOS each. Loop bandwidth 0.1 Hz–2 kHz. On-chip EEPROM. 72-lead 10 × 10 mm. $29.98 per 1k, Rev. D (01/2025). "RECOMMENDED FOR NEW DESIGNS". — [AD9559 product page](https://www.analog.com/en/products/ad9559.html)
- **AD9547.** Input 1 kHz–750 MHz. Two pairs of LVDS/LVPECL or two single-ended CMOS each, up to 450 MHz. Loop bandwidth 0.001 Hz–100 kHz. On-chip EEPROM. 64-lead LFCSP. $21.28 per 1k, Rev. H (11/2024). Listed under "Direct Digital Synthesis" on analog.com. — [AD9547 product page](https://www.analog.com/en/products/ad9547.html)
- **AD9548.** Input 1 Hz–750 MHz. $36.22 per 1k, Rev. H (02/2025). Also listed under "Direct Digital Synthesis". — [AD9548 product page](https://www.analog.com/en/products/ad9548.html)

#### Microchip ZL30252 / ZL30253 (3-Input, 3-Output Any-to-Any Clock Multiplier and Jitter Attenuator)
- **Documents.** The datasheet is dated "January 2018" (Microsemi-branded, marked "Microsemi Confidential"). — [ZL30252/ZL30253 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Input.**
  - "Any input frequency from 1kHz to 1250MHz (1kHz to 300MHz for CMOS)".
  - Single-ended signals go on ICxP. Signals with more than 2.5 V amplitude must be DC-coupled. Pin voltage tolerance is up to VDD33.
  - A 3.3 V LVCMOS 44.1/48 kHz input is therefore allowed.
  - Source: [datasheet, p.1 and Table 10](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **DPLL.** "Programmable bandwidth, 14Hz to 500Hz" on p.1. Table 14 says "Jitter Transfer Bandwidth, DPLL+APLL Programmable: 1 to 500 Hz". "Freerun or digital hold on loss of all inputs". Activity and frequency monitors, plus fast detection of input loss. — [datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Frequency plan limits.** APLL VCO 3715–4180 MHz. High-speed dividers are integers 4–15 or half-steps 4.5–7.5. There is a 7-bit medium-speed divider (maximum input 850 MHz), then a 25-bit low-speed divider. Output range < 1 Hz to 1035 MHz; CMOS/HSTL up to 250 MHz. — [datasheet, Table 13 and §2.3](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
  - Inferred: 45.1584 MHz with HSDIV 6 × MSDIV 14 gives VCO = 3793.31 MHz; 49.152 MHz with HSDIV 5 × MSDIV 16 gives VCO = 3932.16 MHz. Both are in range with integer dividers.
- **Outputs.** CML, or two CMOS per pair. A per-output VDDOx pin sets the CMOS level anywhere from 1.5 V to 3.3 V, so 3.3 V LVCMOS is native. At VDDOx = 3.3 V, VOH ≥ VDDOx − 0.4 V at 4 mA. — [datasheet, Table 12](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Jitter.**
  - DPLL+APLL at 622.08 MHz: 0.25 typ / 0.3 max ps rms (12 kHz–20 MHz).
  - Table 16, DPLL+APLL with a 25 MHz CMOS output: 0.345 ps rms with a 114.285 MHz XO master clock, 0.45 ps rms with a 57.1425 MHz crystal doubled (12 kHz–5 MHz).
  - Period jitter 8 ps pk-pk and cycle-to-cycle 7.5 ps pk (N = 10,000). Half-divide paths can be worse.
  - Source: [datasheet, Tables 14 and 16](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Master clock for the DPLL.**
  - An XO on XA at 93–130 MHz (doubler disabled), or a 25–60 MHz crystal. The doubler is recommended with a crystal and not recommended with an XO in jitter-attenuation mode.
  - "Higher frequencies give lower output jitter". The XO should have < 0.1 ps rms jitter (12 kHz–5 MHz).
  - Source: [datasheet, §5.4 and Tables 2 and 9](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Supplies and power.**
  - AVDD18 and DVDD18 at 1.8 V ±5%. AVDD33, DVDD33 and VDDXO33 at 3.3 V ±5%. VDDOx 1.5–3.3 V.
  - Table 7: "Total power, DPLL+APLL configuration, one input and one normal-swing CML output enabled: 0.67 W" (typ).
  - Per-rail currents in raw-text order: IDD18 242 typ / 297 max mA and IDD33 184 / 225 mA (DPLL+APLL), footnoted as measured with all blocks enabled. The table layout is ambiguous; see Gaps.
  - Source: [datasheet, Table 7 and pin list](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Configuration.** SPI or I²C. "Automatic self-configuration at power-up from external (ZL30252) or internal (ZL30253) EEPROM; up to four configs pin-selectable". Evaluation software is available. — [datasheet p.1](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Package and temperature.** 32-pin QFN, 5 × 5 mm, −40 to +85 °C. Order codes ZL30252LDG1/LDF1 and ZL30253LDG1/LDF1. — [datasheet p.1](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf)
- **Distributor.** DigiKey Canada, ZL30253LDG1: "Part Status: Active", 547 in stock, CAD 23.42 (1), 19.53 (25), 18.87 (100), 6-week lead time. — [DigiKey.ca](https://www.digikey.ca/en/products/detail/microchip-technology/ZL30253LDG1/5325699)

#### Microchip ZL30255 (Dual-Channel Any-to-Any Clock Multiplier and Jitter Attenuator)
- Two independent channels, each built like the ZL30252/3: 1 kHz–1250 MHz inputs (1 kHz–300 MHz CMOS), DPLL bandwidth 14–500 Hz, and CMOS outputs at 1.5–3.3 V.
- Internal EEPROM with four pin-selectable configurations.
- 64-pin LGA, 5 × 10 mm, −40 to +85 °C. Datasheet dated January 2018.
- Source: [ZL30255 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30255_data_sheet_012318.pdf)

#### Microchip parts that do NOT accept a 44.1/48 kHz reference
- **ZL30250 / ZL30251** (DS20006780B, ©2023–2025): "Any Input Frequency from 9.72 MHz to 1250 MHz (9.72 MHz to 300 MHz for CMOS)". These are APLL-only synthesizers. — [ZL30250/1 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/TCG/ProductDocuments/DataSheets/ZL30250-1-4-Input-3-Output-Any-to-Any-Clock-Multiplier-and-Frequency-Synthesizer-IC-DS20006780.pdf)
- **ZL30260–ZL30263** (1-APLL, 6/10 outputs; datasheet September 2020): "Any input frequency from 9.72MHz to 1.25GHz". — [ZL30260-63 datasheet](http://ww1.microchip.com/downloads/en/DeviceDoc/ZL30260-ZL30263-data-sheet-092920.pdf)
- **ZL30264–ZL30267** (2-APLL, 6/10 outputs; DS20006555C): "Any input frequency from 9.72 MHz to 1.25 GHz". — [ZL30264-67 datasheet](https://ww1.microchip.com/downloads/aemDocuments/documents/TCG/ProductDocuments/DataSheets/ZL30264-5-6-7-2-APLL-6-or-10-Output-Any-to-Any-Clock-Multiplier-and-Frequency-Synthesizer-DS20006555.pdf)
- **ZL30244 / ZL30245** (dual-channel): the search-engine summary of the datasheet says 9.72 MHz minimum input. The datasheet itself returned HTTP 403, so this is unverified. — [ZL30244/5 datasheet link](https://www.microchip.com/content/dam/mchp/documents/TCG/ProductDocuments/DataSheets/ZL30244-ZL30245-Data-Sheet.pdf)

#### SiTime SiT95145 (Cascade ClkSoC 10-output MEMS jitter cleaner): "other vendor" candidate
- **Documents and status.** Datasheet Rev 2.39, 23 May 2025. Product page shows "Production". — [SiT95145 datasheet](https://www.sitime.com/datasheet/SiT95145); [SiT95145 product page](https://www.sitime.com/products/jitter-cleaners/sit95145)
- **Inputs and outputs.** Inputs 8 kHz–750 MHz differential and 8 kHz–250 MHz LVCMOS. Outputs are LVPECL, CML, HCSL, LVDS or LVCMOS, each at 1.8, 2.5 or 3.3 V. LVCMOS outputs run 8 kHz–250 MHz. — [datasheet p.1](https://www.sitime.com/datasheet/SiT95145). The product page disagrees on the differential input maximum ("8 kHz to 2.1 GHz (differential), 8 kHz to 250 MHz (LVCMOS"). The 8 kHz minimum is the same in both sources. — [SiT95145 product page](https://www.sitime.com/products/jitter-cleaners/sit95145)
- **Architecture.** "Quad fractional-N PLLs with integrated VCO and loop filter". An integrated ApexMEMS resonator removes the need for an external crystal. — [datasheet p.1](https://www.sitime.com/datasheet/SiT95145)
- **Loop and modes.** "Programmable jitter attenuation bandwidth for each PLL: 1 mHz to 4 kHz". Synchronized, holdover or free-run modes. Indicators for lock loss, clock loss and frequency drift. — [datasheet p.1](https://www.sitime.com/datasheet/SiT95145)
- **Jitter.** 120 fs rms (12 kHz–20 MHz at 622.08 MHz). 93 fs typical in the SerDes band. — [datasheet](https://www.sitime.com/datasheet/SiT95145); [product page](https://www.sitime.com/products/jitter-cleaners/sit95145)
- **Power.** "Total Power Dissipation (2.5V LVDS Outputs @ 156.25M)" is 1130 mW typ. The supply-current rows, in extraction order, are 320–345 mA typ for the full configuration and 170 mA typ with "Two PLLs and 4 Outputs enabled". Row alignment is uncertain. — [datasheet Table 4](https://www.sitime.com/datasheet/SiT95145)
- **Control, package, temperature.** I²C or SPI, plus two-time-programmable NVM, or factory pre-programmed. 9 × 9 mm 64-pin QFN, −40 to +85 °C. — [product page](https://www.sitime.com/products/jitter-cleaners/sit95145)
- **Price.** DigiKey returned no results for "SiT95145". — [DigiKey search](https://www.digikey.com/en/products/result?keywords=SiT95145)
- **Newer SiTime family.** SiTime also lists the SiT95312, SiT95314 and SiT95315 jitter cleaners: 85 fs typ, 2/4/4 PLLs, 44-pin 7 × 7 mm or 64-pin 9 × 9 mm. Their input ranges were not checked. — [SiTime jitter cleaners](https://www.sitime.com/products/jitter-cleaners-network-synchronizers/jitter-cleaners)

#### Diodes and onsemi
- **Diodes PI6CX201A** "LVCMOS VCXO Jitter Attenuator": "Obsolete". PCN-2642 is a device end-of-life notice (2023-09-05 / 2024-03-05). It is "Optimized for 25MHz input/output frequency" with a maximum output of 25 MHz, a 3.3 V supply and a 20-pin TSSOP. It is not usable here. — [Diodes PI6CX201A](https://www.diodes.com/part/view/PI6CX201A)
- **onsemi.** The search found only fanout buffers (for example NB3V8312C). No onsemi kHz-input jitter attenuator turned up. — [onsemi NB3V8312C datasheet](https://www.onsemi.com/pdf/datasheet/nb3v8312c-d.pdf)

### Inferences
- **Summary matrix.** Compiled from the fact sheets above. "Jitter" is the manufacturer figure with its band; prices are manufacturer 1k budgetary prices unless marked.

| Part | Min ref | 3.3 V LVCMOS in / out | Supplies | Jitter (band) | Power typ | 1k price | Status |
|---|---|---|---|---|---|---|---|
| Si5319 (baseline, from brief) | 2 kHz | yes / yes | 3.3 V | 0.3 ps rms | ~0.64 W | — | — |
| AD9557 | 2 kHz | yes / yes (OUT0) | 3.3 + 1.8 V | 3.22 ps (10 Hz–30 MHz), 0.32 ps (12 kHz–20 MHz), from 2 kHz ref, 3.3 V CMOS | 0.55 W | $24.37 | RFND |
| AD9558 | 2 kHz | yes / yes (OUT0, OUT5) | 3.3 + 1.8 V | same rows as AD9557 | 0.74 W | $26.40 | RFND |
| ZL30253 / ZL30252 | 1 kHz | yes / yes (VDDO 1.5–3.3 V) | 3.3 + 1.8 V | 0.25–0.45 ps rms | 0.67 W | CAD 18.87 @100 (DigiKey.ca) | Active (DigiKey) |
| AD9545 / AD9546 / AD9542 | 1 Hz / 1 Hz / 2 kHz | no (1.2/1.8 V CMOS in) / no (HCSL/CML) | 1.8 V | 0.21–0.32 ps (12 kHz–20 MHz) | 0.56 / 0.585 / 0.56 W | $24.30 / $24.36 / $12.16 | RFND |
| AD9553 | 8 kHz | yes / yes (≤ 200 MHz) | 3.3 V only | 1.27 ps (12 kHz–20 MHz) from 8 kHz ref | < 0.45–0.53 W | $8.29 | RFND |
| SiT95145 | 8 kHz | yes (likely) / yes | 1.8 / 2.5 / 3.3 V | 0.12 ps (12 kHz–20 MHz) | up to 1.13 W | not found | Production |
| CS2600 / CS2500 / CS2501 | 150 / 150 / 50 Hz | yes / yes | 3.3 or 1.8 V | 18 ps rms period; 90 ps rms TIE > 100 Hz | ~13 mW | $5.58 / $4.89 / $4.51 | Active |

- **Jitter margin.** All DPLL + APLL parts (AD9557/8, ZL3025x, AD954x, SiT95145) meet the ~8 ps rms budget with more than 10× margin, in any band above a few kHz. Even the widest band quoted (AD9557/AD9558, 10 Hz–30 MHz, 3.22 ps rms from a 2 kHz reference into the 3.3 V CMOS driver) is under budget. With a TCXO system clock and a 0.1 Hz loop it falls to 0.97 ps.
- **No datasheet shows 45.1584 or 49.152 MHz output directly.** The closest cases are AD9557/AD9558 at 70.656 MHz from 2 kHz, ZL3025x at 25 MHz CMOS, and AD9553 at 155.52 MHz from 8 kHz. In these architectures the time jitter is set by the XO/crystal, the DPLL and the APLL VCO, and should scale little with output frequency. This is an inference.
- **AD9557 versus Si5319 (the closest like-for-like replacement).**
  - AD9557 advantages:
    - It uses a common 10–50 MHz fundamental crystal (49.152 MHz in ADI's tables) instead of a 114.285 MHz third-overtone crystal.
    - It has on-chip EEPROM with pin-selected power-up profiles, so no host write is needed at boot.
    - Its loop bandwidth goes down to 0.1 Hz, against Si5319's 60 Hz minimum. That filters the FPGA's quantization jitter much harder.
    - Typical power is similar (0.55 W against ~0.64 W).
  - AD9557 cost: it needs a 1.8 V rail as well as 3.3 V. Only OUT0 can drive 3.3 V CMOS.
- **ZL30253.** Its main draws are the internal EEPROM with four pin-selectable configurations (a natural 44.1/48 selector) and 3.3 V CMOS on every output. Its drawbacks are two rails, a 93–130 MHz XO or 25–60 MHz crystal for the DPLL master clock, and a datasheet from 2018 (Microsemi era).
- **AD9545/AD9546/AD9542.** These are over-specified telecom/1588 parts. Choosing one adds a 1.8 V-only supply, a translator from HCSL/CML to 3.3 V LVCMOS, and an attenuator on the 3.3 V Fs input. The AD9542 ($12.16) is the cheapest way into this jitter class at ADI, but the translator cancels much of that saving.
- **AD9553.** It is attractive on cost ($8.29) and supply (3.3 V only), and needs no crystal if holdover is not needed. Its uncertainty sits between the ~170 Hz loop corner and 12 kHz. That region is dominated by free-running VCO noise and is not quantified in the datasheet text; only a plot is given.
  - Rough estimate, not a datasheet figure: an LC VCO at about −98 dBc/Hz at 1 kHz offset (scaled to 45 MHz) integrates from 170 Hz to 12 kHz to roughly 5 ps rms. That is near the budget if that band counts toward tUJ1.
  - It would need bench measurement, or a read of Figure 8 in the datasheet, before it is chosen.
- **SiT95145.** It removes the crystal entirely, which helps vibration robustness in a car. It costs power (1.13 W full; single-PLL use should be much lower but was not verified), board area (64-pin), and price visibility.
- **Why DPLL + XO parts beat plain analog PLLs here (inference).** A plain PLL at 44.1 kHz has N ≈ 80,000, so the in-band reference and PFD noise is multiplied by 20·log(N) ≈ 98 dB, and the loop must be kept narrow. A DPLL filters the reference digitally, and a crystal-referenced APLL sets the high-offset jitter. VCXO-based cleaners (dual-loop) would need a rate-specific VCXO, meaning two VCXOs to cover both 45.1584 and 49.152 MHz. DCO-based DPLL parts (AD955x, AD954x, ZL3025x, SiT9514x) cover both families from one fixed crystal.
- **Input quantization jitter (inference; the real error is often tonal, not white).** Uniform ±5 ns quantization is about 2.9 ns rms. If it spread flat to 22 kHz, a 60 Hz loop (Si5319 minimum) would pass about 150 ps rms of wander, and a 1 Hz loop about 20 ps rms. The low-bandwidth floors (AD9557 0.1 Hz, AD954x 10⁻⁴ Hz, SiT95145 1 mHz, ZL3025x 1–14 Hz) give far more room than Si5319.

### Gaps
- **Which band tUJ1 uses.** The measurement band and filter that MOST oPHY SP1 applies to tUJ1 were not checked in this assignment. Datasheet figures above (12 kHz–20 MHz, 10 Hz–30 MHz) are proxies.
- **Jitter at the target frequencies.** No manufacturer measurement at 45.1584 or 49.152 MHz, or from a 44.1/48 kHz reference, was found for any part. The nearest are a 2 kHz reference (AD9557/AD9558) and an 8 kHz reference (AD9553).
- **ZL30252/3 open points.**
  - The per-rail current table is scrambled in text extraction. The 0.67 W typ total is the reliable figure.
  - Whether a newer Microchip-branded revision of the 2018 datasheet exists was not verified.
  - ZL30252 lifecycle and USD pricing were not checked; only ZL30253LDG1 at DigiKey.ca.
  - The allowed DPLL master-clock values (MCR2.MCLK field) were not read, so it is unconfirmed whether a common 49.152 or 50 MHz crystal (doubled) works in jitter-attenuation mode.
- **AD9553.** Its phase-noise plot for the 8 kHz reference (Figure 8) could not be rendered, so jitter from 170 Hz to 12 kHz is unquantified. Its external loop-filter values for a 44.1 kHz PFD were not designed.
- **Other ADI parts.** Jitter, power and 3.3 V CMOS capability of AD9547, AD9548 and AD9559 were not verified from datasheets (product-page data only). AD9547/AD9548 are DDS-based per their catalogue placement and were not examined further.
- **SiT95145.** Price and stock, single-PLL power, and 3.3 V LVCMOS input thresholds were not verified. The SiT9531x family's minimum input frequency was not checked.
- **Distributor data.** Mouser pages timed out and microchip.com product pages returned 403. Distributor data is limited to DigiKey for AD9546BCPZ, AD9557BCPZ (price only) and ZL30253LDG1.
- **Out of scope.** Skyworks, TI and Renesas parts were not covered here (assigned to other researchers). Microchip's large network synchronizers (ZL3073x "Azurite", ZL30256 3-channel) were not evaluated.

## Which offer automotive (AEC-Q100) grades?

### Takeaway
Only the Cirrus Logic parts have AEC-Q100 grades: CS2600-DN, CS2500-DZ and CS2501-DZ, all Grade 2 at −40 to +105 °C. None of them meets the jitter budget. None of the jitter-capable parts found here offers an automotive grade: ADI AD9557/AD9558/AD9545/AD9546/AD9542/AD9553, Microchip ZL30252/3/ZL30255, and SiTime SiT95145 are all −40 to +85 °C industrial.

### Cited Findings
- **CS2600.** "Available in commercial-grade 16-pin QFN … –40°C to +85°C … also available in the AEC-Q100-qualified grade-2 package for operation from –40°C to +105°C". Ordering codes CS2600-CN (Commercial, $5.58 per 1k) and CS2600-DN (Automotive, –40 to +105 °C, $6.13 per 1k). — [CS2600 datasheet DS1346F1, APR 2025](https://statics.cirrus.com/pubs/proDatasheet/CS2600_DS1346F1.pdf); [CS2600 product page](https://www.cirrus.com/products/cs2600/)
- **CS2500.** CS2500-CZ (Commercial, $4.89 per 1k) and CS2500-DZ (Automotive, –40 to +105 °C, $5.37 per 1k), in a 10-pin TSSOP. — [CS2500 product page](https://www.cirrus.com/products/cs2500/)
- **CS2501.** CS2501-CZ ($4.51 per 1k) and CS2501-DZ (Automotive, $4.96 per 1k), in a 10-pin TSSOP. — [CS2501 product page](https://www.cirrus.com/products/cs2501/)
- **ADI.** AD9557, AD9558, AD9545, AD9546, AD9542 and AD9553 datasheets and product pages list only −40 to +85 °C. A text search of the AD9557, AD9558, AD9545 and AD9553 datasheets found no "AEC" or "automotive" mention. — [AD9557 product page](https://www.analog.com/en/products/ad9557.html); [AD9545 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/ad9545.pdf); [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf)
- **Microchip.** ZL30252/ZL30253 and ZL30255 are −40 to +85 °C only. — [ZL30252/3 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30252,_ZL30253_data_sheet_012318.pdf); [ZL30255 datasheet](https://ww1.microchip.com/downloads/en/DeviceDoc/ZL30255_data_sheet_012318.pdf)
- **SiTime.** SiT95145 operating range is −40 to +85 °C. — [SiT95145 product page](https://www.sitime.com/products/jitter-cleaners/sit95145)

### Inferences
- A jitter-capable part from this vendor set in a car would be used as an industrial-grade (−40 to +85 °C) part. The automotive-grade route here is limited to Cirrus, whose parts fail on jitter (see the next question).
- The Si5319 baseline is also −40..85 °C (per the brief), so switching to AD9557 or ZL30253 does not lose a qualification the baseline had.

### Gaps
- ADI and Microchip automotive catalogues were not searched exhaustively for "-EP", "W"-suffix or AEC-Q100 variants of these parts. Only the product pages and datasheets were checked.
- Whether any AEC-Q100 DPLL-class part with a kHz input exists at Skyworks, TI or Renesas was out of scope here.

## Does any low-cost part (for example a newer Cirrus clock multiplier) reach the jitter budget?

### Takeaway
No. The newest Cirrus generation are CS2600 (DS1346F1, APR 2025), CS2500 (DS1343F2, JAN 2026) and CS2501 (DS1345F2, JAN 2026). They cost $4.51–$6.13 per 1k and have AEC-Q100 options. All three specify 18 ps rms typical (25 max) period jitter, 21 ps rms baseband TIE and 90 ps rms wideband TIE. Period jitter alone puts high-frequency TIE at ≥ 9 ps rms typ (12.5 max), which is over budget whatever tracking bandwidth the receiver has.

The current CS2100-CP and the CS2000 are now "Discontinued". Cirrus names CS2501 as the drop-in for CS2100 and CS2600 as the recommended replacement, but these do not fix the jitter problem.

The cheapest parts found that might pass:
- ADI AD9553 ($8.29 per 1k, 3.3 V only). It is unproven below 12 kHz offset.
- ADI AD9542 ($12.16 per 1k). It passes jitter easily, but it is 1.8 V only and has HCSL/CML outputs.

### Cited Findings
- **CS2600 jitter.** DS1346F1, APR 2025, Table 3-4. Conditions: 12 MHz reference, 24.576 MHz output, 15 pF load.
  - "CLK_OUT period jitter": 18 typ / 25 max psRMS, with either the external timing reference or the internal oscillator (sample size 10,000).
  - "CLK_OUT baseband TIE jitter" (3rd-order 100 Hz–40 kHz bandpass, AES-12id-2020 §3.4.2): 21 / 70 psRMS with an external reference; 170 / 350 psRMS with the internal oscillator.
  - "CLK_OUT wideband TIE jitter" (3rd-order 100 Hz high-pass, AES-12id-2020 §3.4.1): 90 / 160 psRMS with an external reference; 200 / 380 psRMS with the internal oscillator.
  - Source: [CS2600 datasheet](https://statics.cirrus.com/pubs/proDatasheet/CS2600_DS1346F1.pdf)
- **CS2600 other specs.**
  - CLK_IN 150 Hz–30 MHz. CLK_OUT 6–75 MHz. REF_CLK_IN 8–75 MHz, or a crystal at 8–50 MHz, or the internal oscillator.
  - FLL bandwidth: FLL_BW 1–128 Hz times 1 or 16, limited to fCLK_IN/23.4.
  - Holdover mode: frequency deviation 0.1% max with CLK_IN stopped. Unlock indicators F_UNLOCK and P_UNLOCK.
  - IVDD 4 mA typ unloaded. VDD 3.1–3.5 V or 1.71–1.89 V. Outputs VOH ≥ 0.9·VDD, so LVCMOS at VDD.
  - I²C/SPI, OTP, or hardware (resistor) mode. 16-pin QFN.
  - Source: [CS2600 datasheet](https://statics.cirrus.com/pubs/proDatasheet/CS2600_DS1346F1.pdf)
- **CS2500 and CS2501.** Same jitter rows as CS2600: period 18 / 25 psRMS; baseband TIE 21 / 70; wideband TIE 90 / 160 (external reference); IVDD 4 mA typ. CS2500 CLK_IN is 150 Hz–30 MHz; CS2501 CLK_IN is 50 Hz–30 MHz. — [CS2500 datasheet DS1343F2, JAN 2026](https://statics.cirrus.com/pubs/proDatasheet/CS2500_DS1343F2.pdf); [CS2501 datasheet DS1345F2, JAN 2026](https://statics.cirrus.com/pubs/proDatasheet/CS2501_DS1345F2.pdf)
- **Compatibility.** CS2501 is "Pin-to-pin, register map, and control compatible with CS2100 and CS2300". CS2500 is "…compatible with CS2000 and CS2200". — [CS2501 product page](https://www.cirrus.com/products/cs2501/); [CS2500 product page](https://www.cirrus.com/products/cs2500/)
- **Lifecycle.** CS2100 page: "Discontinued Product. … Recommended Replacements: CS2600. Drop-in Replacements: CS2500, CS2501" (datasheet DS840F3). CS2000 page: same wording (CS2000-CP datasheet DS761F3). — [CS2100 product page](https://www.cirrus.com/products/cs2100/); [CS2000 product page](https://www.cirrus.com/products/cs2000/)
- **Older generation (AN0632R1, MAY 2024).**
  - CS2000/CS2100 "CLK_OUT period jitter, external timing reference": 70 ps.
  - Baseband TIE (100 Hz–40 kHz): 50 ps. Wideband TIE (100 Hz corner): 175 ps.
  - CS2300 period jitter with the internal oscillator: 35 ps.
  - Unloaded power is listed as 40 mW, 59 mW and 13.2 mW (3.3 V). The mapping of the first two numbers to parts is inferred from the table layout: 40 mW for CS2000/CS2100/CS2200 and 59 mW for CS2300. The 13.2 mW figure is for CS2600, a target value at the time.
  - Source: [AN0632 migration note](https://statics.cirrus.com/pubs/appNote/CS2600_Migration.pdf)
- **AD9553 and AD9542.** AD9553: $8.29 per 1k, 1.27 ps rms (12 kHz–20 MHz) from an 8 kHz reference. AD9542: $12.16 per 1k, 213–323 fs rms (12 kHz–20 MHz). — [AD9553 product page](https://www.analog.com/en/products/ad9553.html); [AD9553 datasheet](https://www.analog.com/media/en/technical-documentation/data-sheets/AD9553.pdf); [AD9542 product page](https://www.analog.com/en/products/ad9542.html)

### Inferences
- **Why the Cirrus parts fail regardless of the receiver's tracking bandwidth.**
  - Period jitter pₙ = xₙ₊₁ − xₙ, so var(p) = ∫ Sₓ(f)·4 sin²(πfT) df.
  - At T ≈ 20–22 ns, the weight is below 4×10⁻⁴ for f ≤ 125 kHz. Period jitter therefore comes almost entirely from high-offset TIE, and σ_TIE,HF ≥ σ_period / 2.
  - For CS2600/CS2500/CS2501 that gives ≥ 9 ps rms typical (≥ 12.5 ps at the 25 ps maximum).
  - That already exceeds the ~7.6–8.3 ps rms budget, and ×12 for BER 1e-9 gives ≥ 108 ps p-p against the ~92 ps limit.
  - For CS2000/CS2100 (70 ps period) the bound is ≥ 35 ps rms. The CS2100-CP failure in the brief is consistent with this.
- **The drop-in route leads nowhere.** The drop-in successor for the existing footprint (CS2501 for CS2100) cuts period jitter from 70 to 18 ps but still misses. The CS2100 being discontinued adds a supply argument, independent of jitter, for leaving the CS2x00 family.
- **The low-cost pass candidate needs a test.** The cheapest possibly-passing route is ADI AD9553: 3.3 V-only, CMOS output, and exact integer-N 1024 × Fs for both rates. It must be proven on the bench for jitter between about 170 Hz and 12 kHz. The next cheapest proven route is the AD9542 at $12.16, but its 1.8 V supply and HCSL/CML outputs add a regulator and a translator.

### Gaps
- The Cirrus datasheets characterize jitter only as a 12 MHz reference to 24.576 MHz synthesizer case. No figure exists for multiplier mode from a 44.1/48 kHz CLK_IN at 45.1584/49.152 MHz, although the period-jitter bound above makes that moot.
- Distributor stock and pricing for CS2600/CS2500/CS2501 could not be retrieved (the DigiKey search page returned no product data). Only Cirrus's non-binding budgetary 1k prices are reported.
- The AD9553's phase noise between 170 Hz and 12 kHz, and whether that band counts toward tUJ1, remain open. Both affect whether the $8.29 route is viable.
