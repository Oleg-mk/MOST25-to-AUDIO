# Renesas (IDT) and TI jitter-attenuating PLLs as the MOST25 regenerator clock (1024 x Fs), judged against Si5319

Scope reminder: clk = 1024 x Fs = 45.1584 MHz (Fs = 44.1 kHz) or 49.152 MHz (Fs = 48 kHz); the reference is a 3.3 V LVCMOS Fs square wave from the FPGA with ~10 ns p-p quantization jitter; lock over Fs +/-0.1 %; SP1 budget ~92 ps p-p (~8 ps rms); 3.3 V LVCMOS output; battery/car. Si5319 baseline figures (194 mA, 114.285 MHz 3rd-OT crystal, 60 Hz-8.4 kHz BW) are from the brief and were not re-verified here.

Method note: datasheet numbers were read from the manufacturer PDFs (text extracted with pdftotext). Where a PDF table's columns came out scrambled, this is flagged. Prices are the figures shown on manufacturer web pages unless marked otherwise. Mouser, DigiKey and Findchips pages could not be read (connection reset / empty result), so there is no distributor pricing in these notes.

## Q1 (objective): Per-part fact sheets

### Takeaway
Leaving aside the oversized RC32112A and ClockMatrix 8A34001, the only candidates in scope that combine a native kHz-range input, a native 3.3 V LVCMOS output and no external VCXO are the Renesas FemtoClock NG 8T49N241/8T49N242 (plus the 8T49N28x siblings), the Renesas VersaClock 7 RC310xxB family (an extra find that was not on the list) and the TI CDCM6208/CDCE62005 analog PLLs. The TI BAW and network-synchronizer parts (LMK05318B, LMK5B33216, LMK5C33216, LMK05028) and the Renesas FemtoClock 2/3 parts (RC32504A, RC32312, RC38x12, RC38x08) fail on at least one of three points: a 1.8 V or 2.65 V LVCMOS output, a minimum input of 1-2 MHz, or a documented frequency-steering range of only +/-50 to +/-244 ppm. A fourth point cuts across all the DPLL parts: none of them documents tracking an input that is off by +/-0.1 %.

### Cited Findings

#### Ownership and lifecycle context (all Renesas parts)
- SiTime completed its acquisition of Renesas' timing business on July 1, 2026. — [SiTime press release](https://www.sitime.com/company/newsroom/press-release/sitime-completes-acquisition-renesas-timing-business)
- Renesas product pages now say that Renesas' timing portfolio has been acquired by SiTime. They add that datasheets, documentation and sample orders stay on renesas.com through late 2026, and that new designs, purchasing and support go to SiTime. — [8T49N241 part page](https://www.renesas.com/en/products/8t49n241/part-details/8t49n241-999nlgi); [8T49N241 product page](https://www.renesas.com/en/products/8t49n241)
- The SiTime press release does not name product lines and makes no statement on part-number continuity or supply timelines. — [SiTime press release](https://www.sitime.com/company/newsroom/press-release/sitime-completes-acquisition-renesas-timing-business)

#### Renesas 8T49N241 (FemtoClock NG Universal Frequency Translator)
- Document: 8T49N241 Datasheet, dated August 1, 2025. The revision history's latest entry is Aug 1, 2025, and earlier entries go back to 2015. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet)
- Architecture: one fractional-feedback PLL, usable as a jitter attenuator or frequency translator. The register map has separate "Digital PLL" and "Analog PLL" blocks, and the digital PLL drives a delta-sigma-modulated digitally controlled oscillator (DSM integer/fraction fields, DCXOGAIN). VCO operating range is 3000-4000 MHz. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (pp.1, 20-22, Table 11)
- Inputs: two inputs, 8 kHz to 875 MHz. Each accepts LVPECL, LVDS, LVHSTL, HCSL or LVCMOS at 1.8 V, 2.5 V or 3.3 V levels, so a single-ended 3.3 V LVCMOS input is allowed. Table 9 gives CLKx 0.008-875 MHz and a phase-detector frequency fPD of 0.008-8 MHz; pre-dividers bring CLKx into the fPD range. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (p.7, Table 9)
- Input stability assumption: the datasheet says the family assumes input references are stable to +/-100 ppm or better, except where gapped clocks are used. No DPLL pull-in or tracking range is specified anywhere in the datasheet. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (p.8)
- Outputs: four outputs (LVPECL/LVDS/HCSL) or eight LVCMOS (Q and nQ both toggle). Frequency range is 8 kHz-1 GHz differential and 8 kHz-250 MHz LVCMOS.
  - Q0 has an integer divider: a first stage of /4, /5 or /6 times a second stage of bypass or any even value 2-131,070, for /4 to /786,420 overall.
  - Q1-Q3 have fractional dividers: (N.F) x 2, with N from 4 to 2^18-1 (N = 3 allowed for integer use) and a 28-bit fraction.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (pp.1, 9)
- LVCMOS output supply: each output has its own VCCO of 3.3 V, 2.5 V or 1.8 V (1.8 V is LVCMOS only). At VCCO = 3.3 V: VOH >= 2.6 V at -8 mA, VOL <= 0.5 V, rise/fall 240-310 ps (20-80 %), duty cycle 40-60 %. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (Tables 8H, 11)
- Jitter:
  - Headline: 0.35 ps rms typical including spurs, 12 kHz-20 MHz.
  - Table 13A, LVCMOS at 122.88 MHz, 12 kHz-20 MHz: Q0 359 fs; Q1-Q3 integer 383 fs; Q1-Q3 fractional 356 fs.
  - Conditions: all outputs at the same frequency; characterized with the -900/-901 configurations.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (p.1, Table 13A)
- Loop bandwidth:
  - Selectable steps: 0.2, 0.4, 0.8, 1.6, 3.2, 6.4, 12, 25, 50, 100, 200, 400, 800 Hz, 1.6 kHz and 6.4 kHz.
  - Acquisition and locked bandwidths are set separately, which gives a fast-lock option.
  - Synthesizer mode uses a fixed ~200 kHz bandwidth.
  - The loop needs one external fixed capacitor (0.1 uF across CAP/CAP_REF).
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (pp.9, 13, 20)
- Supplies and current:
  - Core is 3.3 V or 2.5 V. VCCCS (control/status) is 1.8-3.3 V.
  - At 3.3 V: ICC 39 mA typ / 48 max; ICCCS 3/6; ICCA 91/121.
  - At 2.5 V: ICC 39/47; ICCCS 3/5; ICCA 87/118.
  - Maximum current per LVCMOS output at maximum fOUT (outputs unloaded): Q0 44 mA at VCCO 3.3 V, 35 mA at 2.5 V, 30 mA at 1.8 V; Q1-Q3 are up to 55-57 mA at 3.3 V.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (Tables 8A-8C)
- Temperature and package: -40 to +85 °C ambient; 40-VFQFPN (package code NDG40). No automotive grade is listed. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (Table 17); [product page](https://www.renesas.com/en/products/8t49n241)
- Reference:
  - 10-50 MHz fundamental-mode parallel-resonant crystal, with 12 pF CL and +/-100 ppm total stability (layout-extracted table). Alternatively an external oscillator: 10-125 MHz with the doubler off, 10-62.5 MHz with it on.
  - A quartz crystal is recommended for best noise.
  - Free-run accuracy equals the crystal's accuracy.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (p.7, Tables 9-10)
- Behaviour on input loss:
  - Initial holdover offset is +/-50 ppb.
  - Three holdover options: return to the VCO tuning-range centre; instantaneous (the frequency 100 ms before loss); or a fast-average IIR with a ~20 min corner.
  - Status outputs LOL, HOLD and LOS[1:0] can be routed to the GPIOs, and there is an open-drain nINT pin.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (pp.7-8, 11)
- Configuration:
  - I2C slave at up to 400 kHz.
  - Internal OTP, which can be factory pre-programmed.
  - The chip can act as an I2C master and boot its registers from an external I2C EEPROM.
  - Renesas recommends its Timing Commander software.
  - Start-up to the first output edge: 110 ms typ / 150 ms max from internal OTP; 110-1200 ms from an external EEPROM, depending on I2C speed and retries.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (pp.1, 7, 13, Table 11)
- Ordering: 8T49N241-dddNLGI (tray) and -dddNLGI8/-dddNLGI# (tape and reel), -40 to +85 °C. The -ddd configuration codes are defined in a separate ordering document. — [datasheet](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (Table 17)
- Status and price: Active. renesas.com lists 8T49N241-998/-999NLGI(8) at US$2.28 with an MOQ of 490 (the quantity tier is not stated). The part page shows all four part numbers out of stock and 0 inventory at the listed distributors (RS, Mouser, Farnell). — [product page](https://www.renesas.com/en/products/8t49n241); [part page](https://www.renesas.com/en/products/8t49n241/part-details/8t49n241-999nlgi)

#### Renesas 8T49N242 (same FemtoClock NG core, integer outputs)
- Document: 8T49N242 Datasheet (IDT), dated January 16, 2019. — [datasheet](https://www.renesas.com/en/document/dst/8t49n242-datasheet)
- Specifications:
  - Four integer output dividers (first stage /4, /5 or /6).
  - Inputs 8 kHz-875 MHz; fPD 0.008-8 MHz; VCO 3000-4000 MHz.
  - Loop bandwidth 0.2 Hz-6.4 kHz.
  - 2.5 V/3.3 V supply, with 1.8 V supported for LVCMOS outputs.
  - -40 to +85 °C; 40-VFQFPN.
  — [datasheet](https://www.renesas.com/en/document/dst/8t49n242-datasheet) (pp.1, 9, Tables 9, 11)
- Jitter (LVCMOS, 12 kHz-20 MHz): 349 fs at 122.88 MHz and 328 fs at 156.25 MHz. — [datasheet](https://www.renesas.com/en/document/dst/8t49n242-datasheet) (Table 13A)
- Product page: 0.276 ps rms including spurs; 6.0 x 6.0 x 0.9 mm package; US$2.17. 8T49N242-998NLGI and -999NLGI are shown in stock and the -NLGI8 reels out of stock. Status Active. — [product page](https://www.renesas.com/en/products/8t49n242)

#### Renesas 8T49N28x siblings (brief)
- 8T49N281: FemtoClock NG UFT, 2 inputs / 1 PLL / 8 outputs.
  - Inputs 8 kHz-875 MHz; outputs LVPECL/LVDS/LVCMOS, with LVCMOS up to 250 MHz.
  - Under 0.3 ps rms including spurs.
  - 2.5 V/3.3 V; 56-VFQFPN 8 x 8 mm; US$9.15; Active.
  - Listed siblings: 8T49N282 (4 inputs / 2 PLLs / 8 outputs) and 8T49N283 (2 inputs / 2 PLLs / 8 outputs).
  — [8T49N281 product page](https://www.renesas.com/en/products/8t49n281)

#### Renesas RC310xxB (VersaClock 7 programmable jitter attenuator: RC31005B / RC31008B / RC31012B)
- Document: RC310xxB Datasheet R31DS0179EU0124 Rev.1.24, Feb 3, 2026. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet)
- Inputs:
  - Table 15 gives the jitter-attenuator (JA) input range: CLKIN single-ended mode 0.008-250 MHz, differential mode 1-650 MHz. The APLL (synthesizer) input is 1-650 MHz.
  - A 3.3 V CMOS input needs VDDR = 3.3 V.
  - The family product page summarizes the input range as 1-650 MHz, which conflicts with the 8 kHz single-ended JA figure in the datasheet.
  — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (Table 15, Table 40 notes); [family page](https://www.renesas.com/en/products/clocks-timing/jitter-attenuators-frequency-translation/rc310-versaclock-7-programmable-jitter-attenuator-family)
- Outputs: LVCMOS 1 kHz-200 MHz; LVDS/LP-HCSL 1 kHz-650 MHz. At VDDO = 3.3 V the LVCMOS output gives VOH >= 2.4 V (3.2 V typ) at -2 mA, VOL <= 0.4 V and a 45-55 % duty cycle. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1, Table 26)
- Jitter: 169 fs rms typical at 156.25 MHz. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1)
- Loop bandwidth: 0.1 Hz-12 kHz. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1)
- Architecture: fractional LC-VCO APLL running at 9.5-10.7 GHz. The DPLL dynamically controls the APLL's fractional feedback divider (26-bit numerator); the DPLL's own fractional feedback divider is static. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (§3.4-3.5)
- DCO mode: frequency-control-word full range is +/-244 ppm, in 0.91 ppt steps. No separate pull-in figure for jitter-attenuator mode was found. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (§3.9.2.3)
- Holdover and status: initial holdover accuracy is better than 50 ppb; APLL and DPLL lock status go to a GPIO or the register map. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (§3.4.1, §3.7.4)
- Configuration:
  - OTP holds up to four complete or 27 partial configurations.
  - I2C/SMBus at 400 kHz or SPI at 20 MHz; can also load from an external I2C EEPROM.
  - Supplies of 1.8 V, 2.5 V or 3.3 V; -40 to +85 °C.
  — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1)
- Packages:
  - RC31012B: 6 x 6 mm 48-QFN, integrated-crystal option.
  - RC31008B: 5 x 5 mm 40-QFN, integrated-crystal option.
  - RC31005B: 4 x 4 mm 32-LGA with integrated crystal.
  — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1)
- Current (Table 40, which the datasheet describes as worst case with all functions enabled and outputs at maximum speed):
  - IDDA 142 mA typ / 151 max; IDDD 69/73; IDDX (crystal) 3.5/5.
  - IDDR per CMOS input 11/20.
  - IDD_IOD 25/28; IDD_FOD 38/51.
  - IDDO per CMOS output pair at 3.3 V: 25/33 with both outputs on, 15/23 with one on.
  - Power-down at 3.3 V: 19/38 mA.
  — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (Table 40)
- Crystal: 8-80 MHz fundamental mode. — [datasheet](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (Table 16)
- Status and price: Active, with longevity through 2040. Prices shown on renesas.com are US$6.91-8.08. — [family page](https://www.renesas.com/en/products/clocks-timing/jitter-attenuators-frequency-translation/rc310-versaclock-7-programmable-jitter-attenuator-family)

#### Renesas RC32504A (FemtoClock 2, "sub-100 fs UFT")
- Document: R31DS0044EU0113 Rev.1.13, Aug 1, 2025. — [datasheet](https://www.renesas.com/en/document/dst/rc32504a-datasheet)
- Specifications:
  - Jitter-attenuator mode input: 1-800 MHz differential, 1-250 MHz single-ended. The minimum is 1 MHz.
  - Outputs 10 MHz-1 GHz (180 MHz for LVCMOS).
  - VDDOx is 1.71-1.89 V, so the LVCMOS outputs are 1.8 V only. VDDD is 1.8 V or 3.3 V.
  - DPLL loop filter 0.1 Hz-12 kHz.
  - 25-80 MHz crystal or XO.
  - OTP holds up to four configurations; I2C up to 1 MHz or SPI up to 20 MHz.
  - 4 x 4 mm 24-QFN; -40 to +85 °C.
  — [datasheet](https://www.renesas.com/en/document/dst/rc32504a-datasheet) (p.1, Tables 5, 8)
- Status and price: Active, with longevity through 2040. RC32504A000GNK#BB0 is shown at US$8.18 and in stock. — [product page](https://www.renesas.com/en/products/rc32504a)

#### Renesas RC32312 / RC32308 (FemtoClock 3 jitter attenuator)
- Document: R31DS0128EU0118 Rev.1.18, Jul 15, 2026. — [datasheet](https://www.renesas.com/en/document/dst/rc32312rc32308-datasheet)
- Specifications:
  - Inputs 1 kHz-1 GHz differential, 1 kHz-250 MHz single-ended.
  - Outputs 4 kHz-1 GHz differential, 4 kHz-250 MHz single-ended.
  - 25 fs rms (12 kHz-20 MHz with a 4 MHz high-pass filter).
  - 1.8 V operating voltage; the serial ports accept 1.8 V or 3.3 V.
  - The LVCMOS output table cites JESD8-7A (the 1.8 V standard): VOH >= VDDO - 0.45 V at -2 mA.
  - -40 to +85 °C ambient (-40 to +105 °C board).
  - Packages: RC32312 is 9 x 9 mm 64-VFQFPN; RC32308 is 7 x 7 mm 48-VFQFPN.
  - OTP.
  — [datasheet](https://www.renesas.com/en/document/dst/rc32312rc32308-datasheet) (p.1, Tables 5, 15)
- Product page: DPLL bandwidth 0.5 Hz-18 kHz; US$18.87 (RC32312A000GN1); Active, with longevity through 2040. — [RC323 page](https://www.renesas.com/en/products/rc323)

#### Renesas RC38312/RC38112 and RC38208/RC38108 (FemtoClock 3 Wireless)
- RC38312/RC38112 (R31DS0132EU0112 Rev.1.12, May 11, 2026):
  - The RC38312 has three DPLLs and the RC38112 has one.
  - 12 outputs, 4 of which can be LVCMOS (DC-250 MHz); CLKIN DC-1 GHz.
  - Runs from a 1.8 V supply, and the VDDO pins are described as supporting 1.8 V.
  - Crystal 25-80 MHz.
  - 9 x 9 mm 100-BGA; -40 to +85 °C; jitter below 25 fs rms (4 MHz HPF).
  — [datasheet](https://www.renesas.com/en/document/dst/rc38312rc38112-datasheet)
- RC38208/RC38108 (R31DS0163EU0114 Rev.1.14, Jun 25, 2026):
  - 8 outputs, 2 of which can be LVCMOS (DC-250 MHz); CLKIN DC-1 GHz.
  - 1.8 V supply, with VDDO pins described as supporting 1.8 V.
  - 7 x 7 mm 64-BGA.
  — [datasheet](https://www.renesas.com/en/document/dst/rc38208rc38108-datasheet)

#### Renesas RC32112A (FemtoClock network synchronizer / jitter attenuator)
- Document: R31DS0127EU0104 Rev.1.04, Jan 10, 2025. — [datasheet](https://www.renesas.com/en/document/dst/rc32112a-datasheet)
- Specifications:
  - Under 1.4 W typical; under 100 fs rms; loop bandwidth 0.1 Hz-12 kHz.
  - Outputs 0.5 Hz-1 GHz in LVCMOS, LVPECL, LVDS, HCSL, CML, SSTL or HSTL.
  - 2.5 V/3.3 V core with 1.8 V, 2.5 V or 3.3 V outputs.
  - OTP (16 configurations) or external I2C EEPROM; 1 MHz I2C or 50 MHz SPI.
  - 10 x 10 mm 72-VFQFPN; -40 to +85 °C; crystal 25-54 MHz.
  - The DPLL phase detector runs up to 150 MHz; the datasheet lists a 1PPS locking time.
  - Frequency-control word full range is +244.20 / -244.08 ppm. Each DPLL also has a programmable frequency-offset limit that caps its maximum frequency range.
  — [datasheet](https://www.renesas.com/en/document/dst/rc32112a-datasheet) (p.1, Table 16, §4.12.4)
- Status: Active, with longevity through 2040. — [product page](https://www.renesas.com/en/products/clocks-timing/jitter-attenuators-frequency-translation/rc32112a-femtoclock-jitter-attenuator-or-clock-generator)

#### Renesas ClockMatrix 8A34001 (brief; representative of 8A3400x)
- Document: 8A34001 Datasheet, August 10, 2023. — [datasheet](https://www.renesas.com/en/document/dst/8a34001-datasheet)
- Specifications:
  - Eight independent channels, each usable as DPLL, DCO, synthesizer or jitter attenuator.
  - Inputs 0.5 Hz-1 GHz (250 MHz single-ended).
  - 12 differential or 24 LVCMOS outputs, 0.5 Hz-1 GHz (250 MHz LVCMOS). LVCMOS supply can be 3.3, 2.5, 1.8, 1.5 or 1.2 V.
  - Under 150 fs rms (10 kHz-20 MHz); digital loop-filter corners from 12 µHz to 22 kHz.
  - The system APLL needs a 25-54 MHz crystal or XO; the system DPLL takes an XO, TCXO or OCXO at 1-150 MHz.
  - Frequency-control word full range is +/-244 ppm.
  - The reference-monitor frequency-offset limit tops out at +/-100 ppm acceptance / +/-130 ppm rejection.
  - Power depends on configuration; the datasheet points to Timing Commander for estimates.
  — [datasheet](https://www.renesas.com/en/document/dst/8a34001-datasheet) (p.1, Table 10, §Power Consumption)
- Product page: Active, with longevity through 2040; 144-CABGA; US$36.48; 8A34001E-000AJG in stock. — [product page](https://www.renesas.com/en/products/8a34001)

#### TI LMK05318B (1 DPLL + 2 APLL, BAW)
- Document: SNAS801D, June 2020, revised May 2026. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- Architecture:
  - APLL1 has a BAW VCO1 at 2499.75-2500.25 MHz; the datasheet text gives its tuning range as 2.5 GHz +/-100 ppm.
  - APLL2 has an LC VCO2 at 5500-6250 MHz.
  - In DPLL mode the DPLL controls APLL1's sigma-delta modulator to pull VCO1 into lock. A cascaded APLL2 is locked to the VCO1 domain.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (EC table, §8.3.8.2, §8.3.8.7)
- Inputs:
  - PRIREF/SECREF accept differential 5-800 MHz or LVCMOS 1 Hz-250 MHz; 1PPS works on PRIREF only.
  - DC-coupled LVCMOS thresholds: VIH >= 1.8 V, VIL <= 0.6 V. Input absolute maximum is 3.6 V.
  - TI recommends LVCMOS for inputs below 5 MHz.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (EC table, notes 4, 16)
- DPLL:
  - TDC rate up to 26 MHz; the reference R divider is 16-bit.
  - Loop bandwidth 0.01 Hz-4 kHz.
  - The programmed bandwidth must be below 1/100 of the TDC rate and below the APLL1 bandwidth (typically 1-10 kHz).
  - Jitter peaking is 0.1 dB or less.
  - Roll-off above the bandwidth is up to 60 dB/decade.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (§8.3.x, EC table)
- Outputs:
  - Eight outputs in AC-LVPECL, AC-CML, AC-LVDS, HCSL or 1.8 V LVCMOS.
  - LVCMOS is available on OUT4-OUT7 only, 1 Hz-200 MHz.
  - When VDDO is 2.5 V or 3.3 V, the LVCMOS driver does not swing to the rail because of the internal LDO's dropout.
  - Output dividers are 8-bit (1-256), with an extra 24-bit divider on OUT7. APLL2 post-dividers are /2 to /7.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (Recommended Operating Conditions note 3, EC table, Eq. 8-11)
- Jitter: 50 fs typ / 80 fs max at 312.5 MHz from APLL1; APLL2 is 130 fs typical (12 kHz-20 MHz). — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (p.1, §8.1)
- Reference: an XO input of 10-100 MHz (XO, TCXO or OCXO), which sets free-run and holdover accuracy. A standard XO is acceptable when holdover stability is not critical. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (EC table, §8.1)
- Current at 3.3 V:
  - IDD_DIG 21 mA; IDD_IN 43; IDD_PLL1 (DPLL + APLL1) 110; IDD_XO 20.
  - IDD_PLL2 is 18.5 with APLL2 disabled and 120 with it enabled.
  - Output currents add per channel (for example, 1.8 V LVCMOS x2 at 100 MHz is 4.7 mA, plus the mux/divider).
  - Power-down: 56 mA typ / 75 max.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) (EC table)
- Lock and holdover:
  - APLL1 locks in 1.0 ms and APLL2 in 2.5 ms (to +/-25 ppm).
  - The DPLL has a fastlock mode, digital holdover with tuning-word history, and hitless switching.
  - LOL/LOFL/LOPL/holdover status is available on the STATUS pins or as an interrupt.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- Configuration: I2C, 3-wire SPI or 4-wire SPI. The EEPROM is factory pre-programmed and in-system programmable (100 cycles maximum). Configuration uses TICS Pro. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- Package, status and price:
  - 48-VQFN, 7 x 7 mm; -40 to +85 °C; no automotive grade indicated; Active.
  - Price is not shown.
  - LMK05318BRGZR and LMK05318BRGZT show as out of stock on TI.com.
  — [product page](https://www.ti.com/product/LMK05318B); [part details](https://www.ti.com/product/LMK05318B/part-details/LMK05318BRGZR)

#### TI LMK05028 (2-channel network synchronizer, LC VCOs)
- Document: SNAS724B, Feb 2018, revised Feb 2025. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05028.pdf)
- Revision B raised the minimum INx frequency from 1 Hz to 2 MHz and removed 1PPS support throughout the document. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05028.pdf) (Revision History)
- Specifications:
  - Inputs: LVCMOS 2-250 MHz, differential 5-750 MHz.
  - VCO1 4.8-5.4 GHz, VCO2 5.5-6.2 GHz.
  - LVCMOS outputs at 1.8 V or 2.5 V only, up to 200 MHz.
  - 3.3 V core.
  - Core currents (configurations A/B): IDD_PLL1 160/185 mA typ, IDD_PLL2 138/160, IDD_DIG 34/42, IDD_XO 25.
  - 150 fs rms.
  - XO 10-100 MHz; TCXO 10-54 MHz.
  - 64-VQFN, 9 x 9 mm; -40 to +85 °C.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk05028.pdf); [product page](https://www.ti.com/product/LMK05028)
- Status: Active. — [product page](https://www.ti.com/product/LMK05028)

#### TI LMK5B33216 (3 DPLL + 3 APLL, BAW)
- Document: SNAS816D, March 2022, revised August 2026. Product page: Active, datasheet Rev D of Aug 14, 2026. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk5b33216.pdf); [product page](https://www.ti.com/product/LMK5B33216)
- Specifications:
  - APLL3 (BAW) VCBO 2499.75-2500.25 MHz; APLL1 LC 4800-5350 MHz; APLL2 LC 5595-5950 MHz.
  - Inputs 1 Hz-800 MHz; DPLL loop bandwidth 1 mHz-4 kHz.
  - DCO tuning range: +/-200 ppm for the DPLLs; +/-200 ppm for the BAW APLL and +/-1000 ppm for the LC APLLs, both in holdover or APLL-only operation.
  - LVCMOS on OUT0/OUT1 is 1.8 V or 2.65 V up to 200 MHz; at 2.65 V, VOH >= 2.3 V at -2 mA.
  - The 3.3 V LVCMOS GPIO clock outputs reach only 25 MHz.
  - IDD_TOT 702-1250 mA typ depending on configuration.
  - 42 fs typ / 60 fs max at 312.5 MHz.
  - 64-VQFN, 9 x 9 mm; -40 to +85 °C; I2C/SPI; EEPROM plus ROM profiles.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk5b33216.pdf) (p.1, EC tables, DCO Characteristics)

#### TI LMK5C33216 (wireless variant, BAW)
- Document: SNAS750B, Nov 2020, revised March 2021. Product page: Active. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk5c33216.pdf); [product page](https://www.ti.com/product/LMK5C33216)
- Specifications:
  - BAW VCO3 2457.47712-2457.72288 MHz; LC VCO1 4.8-5.35 GHz; LC VCO2 5.6-5.95 GHz.
  - DPLL bandwidth 0.01 Hz-4 kHz.
  - Inputs: LVCMOS 1 Hz-200 MHz, differential 5-800 MHz.
  - LVCMOS only on OUT0/OUT1, at 1.8 V or 2.65 V, up to 200 MHz.
  - Single 3.3 V supply.
  - Configuration-1 total current 875 mA typ / 1050 max; power-down 132 mA.
  - 40 fs at 491.52 MHz; EEPROM; 64-VQFN, 9 x 9 mm.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk5c33216.pdf) (p.1, EC tables)

#### TI LMK04832 (dual-loop JESD204B jitter cleaner)
- Document: SNAS688C, Feb 2017, revised May 2018 (Rev C, May 25, 2018 on the product page). — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf); [product page](https://www.ti.com/product/LMK04832)
- PLL1 input:
  - CLKin in MOS mode: 0.001-250 MHz; bipolar mode up to 750 MHz.
  - MOS mode can be DC-coupled: VIH 2 V to Vcc, VIL 0-0.4 V, so a 3.3 V LVCMOS source is allowed.
  - fPD1 up to 40 MHz; CLKin R and PLL1 N dividers are 14-bit.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf) (EC tables, register map 0x153-0x15A)
- PLL1 needs an external VCXO on OSCin; PLL2 then multiplies that VCXO up to its VCO. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf) (§8.1)
- VCO0 2440-2580 MHz; VCO1 2945-3255 MHz. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf)
- Dividers: clock dividers 1-1023; SYSREF divider 8-8191. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf) (§8.1.9)
- LVCMOS: available on the odd clock outputs, CLKout8/10 and OSCout, up to 250 MHz. VOH >= Vcc - 0.1 V and VOL <= 0.1 V at 1 mA. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf) (EC table, §8.1.9)
- Current: 675-1120 mA typ in the listed JESD204B configurations; power-down 1.5 mA. The datasheet points to TICS Pro for other configurations. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf)
- Other:
  - Holdover via PLL1.
  - SPI only (3- or 4-wire); no EEPROM or I2C is mentioned in the datasheet.
  - 64-WQFN, 9 x 9 mm; -40 to +85 °C.
  - 54 fs at 2500 MHz (12 kHz-20 MHz).
  - A -SEP space-grade variant exists; no automotive variant.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04832.pdf); [product page](https://www.ti.com/product/LMK04832)

#### TI LMK04828 (LMK0482x family)
- Document: SNAS605AS, March 2013, revised May 2020. The product-page extraction showed a Sep 27, 2017 date, which conflicts with the PDF header. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04828.pdf); [product page](https://www.ti.com/product/LMK04828)
- Specifications:
  - CLKin 0.001-750 MHz; fPD1 up to 40 MHz.
  - VCO0 2370-2630 MHz; VCO1 2920-3080 MHz.
  - Device-clock dividers only 1-32; SYSREF divider 8-8191.
  - LVCMOS only on OSCout (up to 250 MHz).
  - ICC_CLKS 565 mA typ / 665 max.
  - SPI; Active.
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04828.pdf) (EC tables, §9.1.9); [product page](https://www.ti.com/product/LMK04828)

#### TI LMK04906 (dual-loop jitter cleaner, 6 outputs)
- Document: SNAS589F, June 2012, revised Aug 2017. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04906.pdf)
- Specifications:
  - CLKin 0.001-500 MHz; fPD1 up to 40 MHz.
  - VCO 2370-2600 MHz.
  - Output dividers 1-1045 (even and odd), plus a VCO divider of 2-8.
  - LVCMOS outputs up to 250 MHz, VOH = Vcc - 0.1 V.
  - ICC_CLKS 410 mA typ / 470 max.
  - 3.15-3.45 V; -40 to +85 °C; 64-WQFN, 9 x 9 mm; MICROWIRE interface; no EEPROM mentioned.
  - 100 fs rms (12 kHz-20 MHz).
  — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04906.pdf); [product page](https://www.ti.com/product/LMK04906)
- PLL1 uses an external VCXO or a tunable crystal (on-chip oscillator plus an external varactor), with a typical loop bandwidth of 10-200 Hz. Single-loop mode powers PLL1 down and uses OSCin as the reference. — [datasheet](https://www.ti.com/lit/ds/symlink/lmk04906.pdf) (§8.1)
- Status: Active. — [product page](https://www.ti.com/product/LMK04906)

#### TI CDCM6208 (2:8 clock generator / jitter cleaner, internal LC VCO)
- Document: SCAS931G, May 2012, revised January 2018. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf)
- Inputs: PRI/SEC reference 8 kHz-250 MHz single-ended at VDD_PRI/SEC = 3.3 V (200 MHz at 1.8 V), with VIH >= 0.8 x VDD. PFD 8 kHz-100 MHz. SEC_REF can alternatively take a 10-50 MHz crystal. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (§6.9, §8.3)
- VCO: CDCM6208V1 2.39-2.55 GHz; CDCM6208V2 2.94-3.13 GHz. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (§8.3)
- Dividers: prescalers /4, /5 or /6; a 4-bit plus 14-bit input divider; 8-bit plus 10-bit feedback dividers. Y0-Y3 have 8-bit integer dividers and Y4-Y7 have 20-bit fractional dividers. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (§8.3)
- LVCMOS output: 1.55-250 MHz with integer division or 0.78-250 MHz with fractional division at 2.5/3.3 V. Each output pair can use 1.8, 2.5 or 3.3 V. VOH >= 0.8 x VDD. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (§6.14, Table 4)
- Loop filter: internal plus partly external components, supporting bandwidths from a few Hz to 400 kHz. — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (§8.3)
- Jitter:
  - Jitter-cleaner mode (loop bandwidth under 1 kHz), 10 kHz-20 MHz: random jitter 1.6 ps rms typ / 2.1 ps max with integer division, 2.3 ps rms with fractional division. Total jitter is 40 ps p-p with integer division.
  - Synthesizer mode: 0.27 ps.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) (Tables 2-3)
- Power, control and package:
  - 0.5 W typical.
  - I2C, SPI or pin mode (32 pin modes); no on-chip EEPROM is mentioned in the datasheet text.
  - STATUS pins report lock and loss of signal.
  - -40 to +85 °C; 48-VQFN, 7 x 7 mm; Active.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf); [product page](https://www.ti.com/product/CDCM6208)

#### TI CDCE62005 (3:5 clock generator / jitter cleaner, internal dual VCO)
- Document: SCAS862G, Nov 2008, revised July 2016. The product page shows Rev G dated May 23, 2016. — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf); [product page](https://www.ti.com/product/CDCE62005)
- Inputs and phase detector:
  - PRI/SEC inputs 40 kHz-500 MHz; LVCMOS single-ended up to 250 MHz.
  - The comparison frequency constraint is 40 kHz <= FCOMP < 40 MHz, and the EC table gives a charge-pump frequency of 0.04-40 MHz.
  - Conflict: the Typical Application design procedure instead uses 80 kHz < FIN/M < 40 MHz.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf) (Eq. 1-3, EC table, §9.2.2)
- Dividers and VCO:
  - VCO 1.750-2.356 GHz; prescaler /2 to /5.
  - Input divider /1-/256; reference divider /1-/8.
  - Output divider 1-80, but not every integer in that range is supported.
  - Feedback bypass divider /1, /2, /5, /8, /10, /16 or /20.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf) (§8.2)
- Outputs and jitter:
  - Five LVPECL/LVDS outputs or up to 10 LVCMOS outputs (3.3 V, up to 250 MHz).
  - Jitter cleaner: 2.6 ps rms typ (10 kHz-20 MHz, 100 MHz output). Clock generator: 550 fs.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf)
- Control: SPI with on-chip EEPROM for the power-up configuration; PLL_LOCK pin; auxiliary crystal input. — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf)
- Power (Table 49, per block at 3.3 V; the table text came out scrambled, so the block-to-value mapping below is a best reading):
  - Input circuit 250 mW; PLL and VCO core 500 mW.
  - Output divider: 60 mW at divide-by-1, 180 mW above 1.
  - LVCMOS buffer: 7 mW static plus a transient term.
  — [datasheet](https://www.ti.com/lit/ds/symlink/cdce62005.pdf) (Table 49)
- Package and status: -40 to +85 °C; 48-VQFN, 7 x 7 mm; Active. — [product page](https://www.ti.com/product/CDCE62005)

### Inferences
- **Frequency plans.** The ratio is exactly 1024 for both rates. The integer plans below were worked out here from the cited divider and VCO limits:
  - **8T49N241/242:** Q0 = 5 x 16 = 80 gives VCO 3612.672 MHz for 45.1584 MHz. Q0 = 6 x 12 = 72 gives 3538.944 MHz, or 5 x 16 gives 3932.16 MHz, for 49.152 MHz. All are inside 3000-4000 MHz. The input can run at fPD = Fs (>= 8 kHz).
  - **RC310xxB:** integer IOD 224 gives 10115.48 MHz for 45.1584 MHz, and IOD 200 gives 9830.4 MHz for 49.152 MHz. Both are inside 9.5-10.7 GHz.
  - **CDCM6208V1:** 2528.8704 MHz / (4 x 14) = 45.1584 MHz and 2457.6 MHz / (5 x 10) = 49.152 MHz, both inside 2.39-2.55 GHz. The V2 variant also works: 2980.45 MHz / (6 x 11) and 2949.12 MHz / (5 x 12).
  - **LMK04832 and LMK04906:** 2483.712 MHz / 55 = 45.1584 MHz and 2457.6 MHz / 50 = 49.152 MHz.
  - **LMK05318B:** only APLL2 can produce the two frequencies. 5780.2752 MHz / 4 / 32 gives 45.1584 MHz and 5898.24 MHz / 5 / 24 gives 49.152 MHz. That means APLL2 must be enabled, which adds about 100 mA.
  - **CDCE62005:** P x O = 40 gives 1806.336 MHz for 45.1584 MHz and 1966.08 MHz for 49.152 MHz. Whether those P and O values are in the allowed tables was not checked.
  - **LMK04828 cannot do it on device clocks:** 2370 MHz / 32 = 74 MHz is the lowest device-clock output.
- **A common VCXO for dual-loop designs.** For LMK04832 or LMK04906 dual-loop use, a single VCXO or crystal whose frequency is a multiple of 7.056 MHz (the LCM of 44.1 kHz and 48 kHz) serves both rates with integer PLL1. For example, 112.896 MHz = 2560 x 44.1 kHz = 2352 x 48 kHz, and both N values are within the 14-bit limit. The 48 kHz family then needs PLL2 R = 147 (768 kHz PFD) to reach 2457.6 MHz.
- **Tracking +/-0.1 % is the discriminating requirement, not jitter.** Documented steering limits:
  - LMK05318B: +/-100 ppm (BAW VCO1).
  - LMK5C33216 BAW domain: +/-50 ppm.
  - LMK5B33216 DPLL DCO: +/-200 ppm.
  - RC310xxB, RC32112A and 8A34001 frequency-control word: +/-244 ppm. The 8A34001 reference monitor also tops out at +/-100/130 ppm.
  - 8T49N241/242: assumes references within +/-100 ppm.
  - Dual-loop LMK048xx: bounded by the external VCXO's pull range.
  - Only the internal wide-range LC-VCO analog PLLs (CDCM6208: VCO range about +/-3 %; CDCE62005: 1.75-2.36 GHz) have no documented narrow limit.
  - If real MOST timing masters keep Fs within about +/-100 ppm (crystal-referenced), the DPLL parts become usable. If +/-0.1 % must truly be tracked, most DPLL parts are either out or unverified.
- **Input-jitter attenuation.** The FPGA's ~10 ns p-p input jitter must be attenuated by about 20 x log10(10 ns / 92 ps) ≈ 41 dB. The parts' own 12 kHz-20 MHz jitter (0.03-2.6 ps rms) is not the binding term.
  - With 20-40 dB/decade roll-off, quantization-error components within about 1-2 decades above the loop bandwidth will leak through.
  - Parts that allow very low bandwidth therefore have an advantage over Si5319's 60 Hz minimum: 8T49N241 goes to 0.2 Hz, RC310xxB and RC32112A to 0.1 Hz, LMK05318B to 0.01 Hz. The cost is longer lock times, partly offset by fast-lock modes.
- **Devices with a 1 MHz minimum input.** RC32504A (and, per its product page, the RC310 family's APLL/differential path) could still be used if the FPGA presents a >= 1 MHz multiple of Fs, for example 32 x Fs. That clock would carry the same ~10 ns quantization and would need the same attenuation. This is an architecture option, not something a vendor documents for this use.

### Gaps
- **Tracking range (decides the choice).**
  - 8T49N241/242: no pull-in or tracking range is given, only the "+/-100 ppm references assumed" statement. Whether it locks at +/-1000 ppm needs Renesas/SiTime confirmation or a bench test with Timing Commander.
  - RC310xxB: the DPLL's jitter-attenuator-mode frequency limit (separate from the +/-244 ppm DCO frequency-control word) is not stated.
  - CDCM6208 and CDCE62005: continuous-lock drift or per-band tuning range after VCO calibration is not documented in the extracted text.
- **Jitter at the actual output.** No vendor characterizes jitter at 45.1584 or 49.152 MHz LVCMOS; the figures are at 100-312.5 MHz. Jitter transfer and peaking versus the FPGA's quantization spectrum is not specified for this use.
- **Part-specific details not verified:**
  - CDCE62005: the allowed output-divider and feedback-divider value tables (Tables 13, 23, 24), and whether 40 kHz or 80 kHz is the true FCOMP minimum.
  - LMK04906: minimum OSCin frequency for single-loop mode.
  - LMK04832: minimum PLL2 PFD.
  - 8T49N241: meaning of the -998 and -999 configuration codes.
  - 8A34001: typical power for a small configuration.
  - RC38x12/RC38x08: lifecycle status and price were not checked.
- **Pricing and stock.**
  - No distributor pricing or stock was obtained: Mouser reset the connection, DigiKey returned a generic page, and Findchips returned no results.
  - TI.com showed no prices on the pages fetched.
  - The renesas.com prices for 8T49N24x (about US$2.2) look low for this class of part and have no stated quantity basis; treat them as unconfirmed.

## Q2: Which parts meet ~8 ps rms with a 44.1/48 kHz input, a 3.3 V supply and a 3.3 V LVCMOS output, at reasonable power and complexity?

### Takeaway
Every candidate's intrinsic jitter is 2.6 ps rms or better, so jitter alone disqualifies nothing. Three parts meet all four criteria natively without an external VCXO: the Renesas 8T49N241/8T49N242 (8 kHz input, 3.3 V LVCMOS, 0.35 ps, standard crystal, OTP/EEPROM boot), the Renesas RC31008B/RC31005B/RC31012B (8 kHz single-ended JA input, 3.3 V LVCMOS, 169 fs, OTP holding several configurations, optional integrated crystal) and the TI CDCM6208 (8 kHz input, 3.3 V LVCMOS, 1.6 ps in jitter-cleaner mode, 0.5 W, no NVM). RC32112A and ClockMatrix 8A34001 also meet the four criteria but are oversized for one clock. Three more are conditional: TI LMK04906 and LMK04832 (1 kHz input but an external VCXO or tunable crystal and 0.4-1 A) and TI CDCE62005 (40 kHz PFD minimum is marginal, about 1 W, SPI only). The rest fail on output voltage, minimum input or dividers. Separately, every DPLL part carries an unresolved +/-0.1 % tracking risk.

### Cited Findings
| Part | Native min input | 3.3 V LVCMOS out | Intrinsic jitter | Supply / current | Documented steering limit | Sources |
|---|---|---|---|---|---|---|
| 8T49N241 / 8T49N242 | 8 kHz (fPD 8 kHz-8 MHz) | Yes (VOH >= 2.6 V) | 0.35 ps; LVCMOS 349-383 fs | 3.3/2.5 V; ~133 mA typ core at 3.3 V plus output | Assumes references within +/-100 ppm | [241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet), [242 DS](https://www.renesas.com/en/document/dst/8t49n242-datasheet) |
| RC31005B / RC31008B / RC31012B | 8 kHz single-ended in JA mode | Yes (VOH >= 2.4 V) | 169 fs | 1.8/2.5/3.3 V; core 142 + 69 mA (worst-case table) | DCO frequency-control word +/-244 ppm | [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) |
| CDCM6208 (V1/V2) | 8 kHz | Yes (VOH >= 0.8 x VDD) | 1.6 ps typ / 2.1 max in jitter-cleaner mode | 0.5 W typ | Not stated (LC VCO 2.39-2.55 or 2.94-3.13 GHz) | [DS](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf) |
| LMK04906 | 1 kHz | Yes (Vcc - 0.1 V) | 100 fs | 3.3 V; 410 mA typ (all clocks on) | External VCXO or tunable crystal | [DS](https://www.ti.com/lit/ds/symlink/lmk04906.pdf) |
| LMK04832 | 1 kHz (MOS mode, DC-coupled OK) | Yes (Vcc - 0.1 V) | 54 fs at 2.5 GHz | 3.3 V; 675-1120 mA (JESD configurations) | External VCXO | [DS](https://www.ti.com/lit/ds/symlink/lmk04832.pdf) |
| CDCE62005 | 40 kHz (FCOMP); 80 kHz in the application example | Yes (3.3 V) | 2.6 ps typ in jitter-cleaner mode | 3.3 V; block power table implies about 1 W | Not stated (1.75-2.36 GHz VCO) | [DS](https://www.ti.com/lit/ds/symlink/cdce62005.pdf) |
| LMK05318B | 1 Hz (LVCMOS) | No (1.8 V LVCMOS only) | 50 fs (APLL1), 130 fs (APLL2) | 3.3 V; about 314 mA core with APLL2 on | +/-100 ppm (BAW VCO1) | [DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf) |
| LMK5B33216 | 1 Hz | No (1.8/2.65 V; 3.3 V GPIO clocks <= 25 MHz) | 42 fs | 3.3 V; 702-1250 mA | DPLL DCO +/-200 ppm | [DS](https://www.ti.com/lit/ds/symlink/lmk5b33216.pdf) |
| LMK5C33216 | 1 Hz (LVCMOS) | No (1.8/2.65 V) | 40 fs | 3.3 V; 875 mA typ | BAW VCO3 +/-50 ppm | [DS](https://www.ti.com/lit/ds/symlink/lmk5c33216.pdf) |
| LMK05028 | 2 MHz (since Rev B) | No (1.8/2.5 V) | 150 fs | 3.3 V; about 370 mA core | n/a | [DS](https://www.ti.com/lit/ds/symlink/lmk05028.pdf) |
| LMK04828 | 1 kHz | Only on OSCout (the VCXO frequency) | n/a | 3.3 V; 565 mA typ | Device-clock dividers 1-32 cannot reach 45/49 MHz | [DS](https://www.ti.com/lit/ds/symlink/lmk04828.pdf) |
| RC32504A | 1 MHz | No (VDDO 1.8 V) | < 100 fs | 1.8 V (VDDD 1.8/3.3 V) | n/a | [DS](https://www.renesas.com/en/document/dst/rc32504a-datasheet) |
| RC32312 / RC32308 | 1 kHz | No (JESD8-7A, 1.8 V) | 25 fs | 1.8 V | n/a | [DS](https://www.renesas.com/en/document/dst/rc32312rc32308-datasheet) |
| RC38x12 / RC38x08 | DC-1 GHz | No (1.8 V supply) | < 25 fs | 1.8 V; BGA | n/a | [DS 38x12](https://www.renesas.com/en/document/dst/rc38312rc38112-datasheet), [DS 38x08](https://www.renesas.com/en/document/dst/rc38208rc38108-datasheet) |
| RC32112A | 1PPS-capable | Yes (1.8/2.5/3.3 V outputs) | < 100 fs | < 1.4 W typ; 72-QFN | Frequency-control word +/-244 ppm | [DS](https://www.renesas.com/en/document/dst/rc32112a-datasheet) |
| 8A34001 (ClockMatrix) | 0.5 Hz | Yes (3.3-1.2 V) | < 150 fs | Configuration-dependent; 144-CABGA | Word +/-244 ppm; monitor <= +/-100/130 ppm | [DS](https://www.renesas.com/en/document/dst/8a34001-datasheet) |

- The MOST requirement is 3.3 V LVCMOS. The LMK05318B datasheet states that its LVCMOS driver swings rail to rail only at VDDO = 1.8 V; at 2.5 V or 3.3 V, LDO dropout keeps it from reaching the rail. — [LMK05318B DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- ClockMatrix 8A34001 is an eight-channel IEEE 1588/SyncE synchronization management unit in a 144-CABGA, priced at US$36.48 on renesas.com. — [product page](https://www.renesas.com/en/products/8a34001); [DS](https://www.renesas.com/en/document/dst/8a34001-datasheet)

### Inferences
- **Best fit for power and complexity:**
  - **8T49N241 or 8T49N242:** 6 x 6 mm 40-QFN, standard 10-50 MHz crystal, I2C, OTP or external-EEPROM self-boot. Current is about 133 mA typ core plus one LVCMOS output at 3.3 V. With a 2.5 V core, the core would be about 129 mA at 2.5 V (about 0.32 W); this assumes VCCO at 3.3 V can be mixed with a 2.5 V core, which the independent VCCO specification in Table 8C suggests but which needs confirming.
  - **RC31008B or RC31005B:** 5 x 5 or 4 x 4 mm, integrated-crystal option, OTP can hold separate 44.1 kHz and 48 kHz configurations.
  - **CDCM6208V1:** 0.5 W typ, no crystal needed, but it needs an external loop filter and I2C writes at every boot.
- **Complexity of the LMK048xx route.** LMK04906 and LMK04832 add an external VCXO or tunable crystal, a PLL1 loop filter, SPI/MICROWIRE-only control and 1.4-3.7 W-class supply current. That is a poor fit for a battery-powered in-car tap.
- **Overkill for a single 45/49 MHz clock:** ClockMatrix 8A34001 (eight channels, 144-BGA, power set in Timing Commander, +/-100 ppm reference-monitor design envelope), RC32112A (under 1.4 W, 72-QFN) and the LMK5B33216/LMK5C33216 (about 0.7-1.25 A).

### Gaps
- Whether a 2.65 V LVCMOS output (LMK5B33216/LMK5C33216: VOH >= 2.3 V) would be acceptable to the FPGA's 3.3 V input bank is a system choice, not verified.
- None of the short-listed parts has vendor data at 45.1584 or 49.152 MHz LVCMOS, or with a 44.1/48 kHz reference.

## Q3: Which offer automotive (AEC-Q100) grades?

### Takeaway
None. No Renesas or TI jitter attenuator reviewed here has an AEC-Q100 grade. All are -40 to +85 °C ambient parts, and some allow a 105 °C board or thermal-pad temperature. The nearest automotive parts from either vendor are clock generators that are not usable as 44.1/48 kHz jitter cleaners.

### Cited Findings
- The LMK05318B product page indicates no automotive grade; its range is -40 to +85 °C. — [LMK05318B page](https://www.ti.com/product/LMK05318B)
- The LMK04832 has a -SEP space-grade variant (30 krad) and no automotive variant. It supports a 105 °C PCB temperature measured at the thermal pad. — [LMK04832 page](https://www.ti.com/product/LMK04832)
- No automotive variant is mentioned for the LMK5B33216 (-40 to +85 °C). — [LMK5B33216 page](https://www.ti.com/product/LMK5B33216)
- TI CDCE6214-Q1 is AEC-Q100 qualified at temperature grade 2 (-40 to +105 °C).
  - It is a fractional-N clock generator, not a jitter cleaner.
  - Reference input 10-200 MHz; crystal 10-50 MHz.
  - Loop bandwidth 100 kHz-1.6 MHz.
  - LVCMOS at 1.8, 2.5 or 3.3 V; LVCMOS jitter 1.05 ps typ / 1.5 max.
  - 23 mA (one channel) to 65 mA (four channels) typical.
  - I2C with EEPROM; 4 x 4 mm 24-VQFN; datasheet Rev C, July 31, 2025.
  — [CDCE6214-Q1 page](https://www.ti.com/product/CDCE6214-Q1)
- Renesas' automotive timing page lists only clock generators and a buffer: RC2121 AutoClock, 9FGV1002, 5P49V60, 5L35021, 5P35023 and 5PB1104. It lists no automotive jitter attenuator. — [Renesas automotive timing](https://www.renesas.com/en/products/clocks-timing/application-specific-clocks/automotive-timing)
- The 8T49N241 ordering table offers only -40 to +85 °C "NLGI" parts. The RC310xxB, RC32504A and RC32112A datasheets state -40 to +85 °C. The RC32312 allows -40 to +105 °C board temperature. — [8T49N241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet); [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet); [RC32504A DS](https://www.renesas.com/en/document/dst/rc32504a-datasheet); [RC32112A DS](https://www.renesas.com/en/document/dst/rc32112a-datasheet); [RC32312 DS](https://www.renesas.com/en/document/dst/rc32312rc32308-datasheet)

### Inferences
- CDCE6214-Q1 cannot stand in for a jitter cleaner here, for two reasons. Its 10 MHz minimum reference rules out a 44.1/48 kHz input. Its 100 kHz minimum loop bandwidth would pass the FPGA's 10 ns quantization jitter almost unattenuated.
- An in-car installation with a -40 to +85 °C industrial part is a qualification and warranty decision, not a jitter issue. This applies equally to Si5319, which is also -40 to +85 °C per the brief.

### Gaps
- TI's and Renesas' full parametric catalogues were not filtered for "-Q1" or "AEC-Q100 jitter cleaner"; this pass checked product pages. A future SiTime automotive derivative of the Renesas jitter attenuators is unknown.

## Q4: How do they compare with Si5319 on power, reference needs and start-up from an FPGA over I2C?

### Takeaway
- **8T49N241/242 is the closest drop-in upgrade over Si5319.** It has similar or lower supply current and replaces the 114.285 MHz third-overtone crystal with a standard 10-50 MHz fundamental crystal. It adds OTP/EEPROM self-boot and allows a lower loop bandwidth (0.2 Hz against 60 Hz).
- **RC310xxB is similar**, with the option of an integrated crystal and several stored configurations, but its core current is higher when run from 3.3 V.
- **CDCM6208 needs no crystal and draws 0.5 W typ, but has no NVM.**
- **Everything else costs more power and parts:** LMK05318B needs an XO and draws about 1.1 W; the LMK048xx parts need a VCXO and draw 1.4 W or more; the LMK5x and ClockMatrix parts draw 1 W or more.

### Cited Findings
- **Power, 8T49N241 at 3.3 V:** ICC 39 + ICCCS 3 + ICCA 91 mA typ = about 133 mA (175 mA max) before outputs. One LVCMOS output adds up to 44 mA at maximum fOUT. At a 2.5 V core: 39 + 3 + 87 mA typ. — [8T49N241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet) (Tables 8A-8C)
- **Power, RC310xxB:** IDDA 142 + IDDD 69 + IDDX 3.5 mA typ, plus IDDR about 11 per CMOS input, IDD_IOD 25, and IDDO about 15 for one LVCMOS output at 3.3 V. These are worst-case "all functions on" table values, and all supplies may be 1.8, 2.5 or 3.3 V. — [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet) (p.1, Table 40)
- **Power, CDCM6208:** 0.5 W typical. — [CDCM6208 DS](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf)
- **Power, LMK05318B:** 21 + 43 + 110 + 20 mA, plus 120 mA for APLL2 when enabled, typ at 3.3 V before outputs. — [LMK05318B DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- **Power, LMK04906:** 410 mA typ; **LMK04828:** 565 mA typ; **LMK04832:** 675-1120 mA in the listed configurations. — [LMK04906 DS](https://www.ti.com/lit/ds/symlink/lmk04906.pdf); [LMK04828 DS](https://www.ti.com/lit/ds/symlink/lmk04828.pdf); [LMK04832 DS](https://www.ti.com/lit/ds/symlink/lmk04832.pdf)
- **Power, larger parts:** LMK5B33216 702-1250 mA; LMK5C33216 875 mA typ; RC32112A under 1.4 W typ. — [LMK5B33216 DS](https://www.ti.com/lit/ds/symlink/lmk5b33216.pdf); [LMK5C33216 DS](https://www.ti.com/lit/ds/symlink/lmk5c33216.pdf); [RC32112A DS](https://www.renesas.com/en/document/dst/rc32112a-datasheet)
- **Reference, 8T49N241/242:** 10-50 MHz fundamental crystal (CL 12 pF, +/-100 ppm) or a 10-125 MHz oscillator. — [8T49N241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet)
- **Reference, RC310xxB:** 8-80 MHz fundamental crystal. RC31005B has the crystal integrated; RC31008B and RC31012B offer it as an option. — [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet)
- **Reference, CDCM6208:** internal VCO; SEC_REF can optionally take a 10-50 MHz crystal. — [CDCM6208 DS](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf)
- **Reference, CDCE62005:** internal VCOs; auxiliary crystal input. — [CDCE62005 DS](https://www.ti.com/lit/ds/symlink/cdce62005.pdf)
- **Reference, LMK05318B:** 10-100 MHz XO, TCXO or OCXO. — [LMK05318B DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- **Reference, LMK04832/LMK04906:** external VCXO, or for LMK04906 a tunable crystal plus varactor. — [LMK04832 DS](https://www.ti.com/lit/ds/symlink/lmk04832.pdf); [LMK04906 DS](https://www.ti.com/lit/ds/symlink/lmk04906.pdf)
- **Start-up, 8T49N241:** I2C at up to 400 kHz; internal OTP (factory-programmable) or self-boot from an external EEPROM as I2C master. First output edge 110 ms typ / 150 ms max from OTP. Configuration uses Timing Commander. — [8T49N241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet)
- **Start-up, RC310xxB:** OTP holds four complete or 27 partial configurations; I2C/SMBus 400 kHz or SPI 20 MHz; external I2C EEPROM. — [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet)
- **Start-up, LMK05318B:** EEPROM (up to 100 program cycles) plus ROM pages; I2C/SPI; TICS Pro. — [LMK05318B DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf)
- **Start-up, CDCM6208:** I2C/SPI or 32 pin modes, with no EEPROM mentioned. — [CDCM6208 DS](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf)
- **Start-up, CDCE62005:** SPI with on-chip EEPROM for power-up. — [CDCE62005 DS](https://www.ti.com/lit/ds/symlink/cdce62005.pdf)
- **Start-up, LMK04832/LMK04828:** SPI only, with no EEPROM or I2C in the datasheets. **LMK04906:** MICROWIRE, with no EEPROM mentioned. — [LMK04832 DS](https://www.ti.com/lit/ds/symlink/lmk04832.pdf); [LMK04828 DS](https://www.ti.com/lit/ds/symlink/lmk04828.pdf); [LMK04906 DS](https://www.ti.com/lit/ds/symlink/lmk04906.pdf)
- **Loop bandwidth versus Si5319's 60 Hz floor:** 8T49N241/242 down to 0.2 Hz; RC310xxB 0.1 Hz; LMK05318B 0.01 Hz; CDCM6208 "a few Hz". — [8T49N241 DS](https://www.renesas.com/en/document/dst/8t49n241-datasheet); [RC310xxB DS](https://www.renesas.com/en/document/dst/rc310xxb-datasheet); [LMK05318B DS](https://www.ti.com/lit/ds/symlink/lmk05318b.pdf); [CDCM6208 DS](https://www.ti.com/lit/ds/symlink/cdcm6208.pdf)

### Inferences
- **Estimated power against Si5319 (about 194 mA, about 0.64 W at 3.3 V, per the brief):**
  - 8T49N241/242: about 0.5-0.6 W with a 3.3 V core and one 45-49 MHz LVCMOS output, or about 0.4 W with a 2.5 V core.
  - RC310xxB: about 0.9 W if every rail is at 3.3 V, about 0.55 W with 1.8 V core rails and a 3.3 V VDDO. This rests on the "any valid supply" wording and is unverified.
  - CDCM6208: about 0.5 W.
  - LMK05318B: about 1.1-1.2 W.
  - CDCE62005: about 1 W.
  - LMK04906: about 1.4 W.
  - LMK04832 and the LMK5x parts: 2-4 W.
- **Why OTP or EEPROM helps in a car.** With self-start, the clock comes up correct without the FPGA's I2C master having to run first. The 8T49N241 and RC310xxB can store both the 44.1 kHz and 48 kHz configurations; the RC310xxB explicitly offers multiple stored configurations. This removes a boot-order dependency that CDCM6208 and the LMK048xx parts would keep.
- **Whether Si5319 needs register loading at every reset** was not checked in this pass. The local Rev 0.3 text only says a reset returns registers to their defaults and mentions no NVM; the Si5319 reviewer should confirm.

### Gaps
- Si5319's own tracking range, and whether it has NVM, were outside this pass. They should be checked against the same +/-0.1 % criterion for a fair comparison.
- No lock-acquisition times were found at 44.1/48 kHz with sub-10 Hz bandwidths for any part. That matters for how quickly the MOST ring comes up after wake-up.
