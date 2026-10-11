# The end caps of listener v2.0's tube

Written by `gen_caps.py` from `check_fit.py`'s model of the board in the tube; do not edit by hand.

| File | What |
|---|---|
| `in_cap.step`, `in_cap.stl` | the cap at the input end (x = 0): J1, J5, J4, M2's micro-USB, the antenna's SMA |
| `out_cap.step`, `out_cap.stl` | the cap at the output end (x = 98): J6 and the RCA jacks J7..J9 |
| `caps.svg` | the drawing (A2, 2:1): both caps seen from outside, in section and from below, the sizes, the notes (in Ukrainian) |
| `caps_en.svg` | the same drawing in English |

The models are in the print's frame: the outer face on the bed (z = 0), the flange up to 2.0 mm, the
blocks above it to 8.0 mm, the saddle up to 11.0 mm; x runs to the left as seen from outside.

## The caps

- A flange of the tube's outline (80.0 x 30.0 mm, corners R 0.5), 2.0 mm thick, sits on the
  tube's end face; the board's ends butt against the flanges. The tube is as long as the soldered board
  between the flanges' bearing faces: from its input end to the farthest of its output end and the RCA
  housings' fronts (nominally 98.05 mm, the fronts 0.05 past the board's end by BKL's drawing),
  +0.1/-0 mm, its ends square and deburred. The board then slides at most 0.1 mm between the flanges;
  check_fit takes every face that much deeper.
- Each opening is its part's outline plus 0.25 mm a side, its corners R 0.25 (a larger radius would
  bring a part's corner nearer than 0.25); the SMA's hole and the RCA bushings' slots are the thread plus
  the same. No wall is thinner than 1.2 mm (three lines of a 0.4 mm nozzle). J5's frame and J4's face
  share one opening: the web between two would be thinner than that. The thinnest walls:
  - in_cap: 1.55 mm, M2's micro-USB, its plug's overmould to the flange's edge
  - out_cap: 1.20 mm, J6's frame - J7's bushing
- Through the flanges (check_fit, the board slid either way): J1's housing stands 1.50..1.60 mm out
  of the input cap. The faces sit inside their cap's outer face, mm: J5's 1.65..1.75 (limit 2.20); J4's 2.60..2.70 (limit 3.00); J6's 2.05..2.15 (limit 2.20);
  a TOSLINK face may sit as deep as the flange, its plug entering a jack-sized opening. M2's micro-USB
  is 0.00..0.45 mm behind the flange's inner face, the opening passing its plug's overmould to there
  (limit 1.00); the opening is tall enough for the receptacle's unpublished height, 2.5..3.0 mm.
  The RCA threads stand 6.55 mm out of the output cap; the jacks go without nuts (their nut is
  wider than their pitch).
- The RCA bushings go through vertical slots 13.20 mm wide and 13.80 mm tall: BKL's TDS does not
  dimension the axis's height, which scales 6.45..7.05 mm above the board, so the slot keeps 0.25 mm
  round the thread anywhere in that range, with no jack measured.
- Each cap has a block in each side margin (8.0 mm, the board centred across); its post stands
  from the floor. Every block stands 0.7 mm off the tube's walls, floor and top, rounded into its
  corners (inside R up to 2.0): an extruded tube's outside and walls are held only to a few tenths and
  FDM prints outer faces large, so any tube in tolerance takes the caps without being measured. The
  saddle sets the height; across the tube a cap shifts at most 0.7 mm until its screws pin it. The
  post's face, 0.3 mm off the board's edge (JLCPCB's outline: +/-0.2), holds the board across. A lip
  under the edge carries the board's underside at 9.65 mm above the tube's floor, a lip over it holds it
  down: the slot between them is 2.0 mm for the 1.6 board (JLCPCB: +/-10 %; FDM prints a slot
  narrow). Each lip's tip has a 0.5 x 45 degree lead-in toward the slot (it rises with the print: no
  overhang), so the board's end finds the slot from that far off. A lip reaches up to 2.0 mm in and
  runs the block's whole 6.0 mm depth where the parts and leads let it (0.2 mm off a part's
  courtyard in plan, 2.0 mm off a soldered lead's centre on its solder side, 0.4 mm off a peg,
  0.2 mm off a soldered pad on its part's side, 0.5 mm over a part or a lead's tip); where they do
  not, it is cut short to a ledge. At the input end's y = 0 corner J1's action pin (pad 0 at 3.50, 1.55)
  stands 1.55 mm from the board's edge, so that corner sits between a 0.80 x 2.3 mm ledge over the
  board and a 2.00 x 1.5 mm ledge under it (width x depth).
- The input cap's block on J4's side stops at v 16.40, 0.3 mm under the SMA's body; it
  does not reach the tube's top, so it takes no screw. A third block stands over the board between
  J4's opening and the SMA (u 62.40..67.45, from the tube's top down to v 18.35, 0.5 mm over
  M2's header tails, which stand 4.6 mm up through the board there): it takes the input cap's second
  screw and the ground bond.
- Under the tube each flange runs on into a saddle, 3.0 mm thick and 9.0 mm along the tube
  from its end, with an ear 10.0 mm out on either side. The tube's floor rests on the two saddles, and
  four screws through the ears' 4.6 mm holes hold the listener: DIN 7981 ST4.2 self-tapping (4.22 mm at
  most across the thread) or M4, a DIN 125 M4 washer (9 mm) under each head (PETG creeps under a
  bare head), which clears the tube's side by 0.5 mm. The ear holes lie horizontal in the print, so
  they are teardrops, their point away from the flange, cut flat at the circle's top. The saddle rises
  from the bed with the flange, so the caps print without supports.

Openings, blocks, screws and the saddle, mm, seen from outside that end: u from the flange's left edge,
v from its bottom edge, w from its outer face into the tube. At the input end the left side is the
board's y = 0 edge (J1's), at the output end its y = 60 edge (J8's). A lip's row gives the whole lip,
its lead-in included.

| Cap | What | u | v | w |
|---|---|---|---|---|
| in_cap | J1's housing, with the notch for its standoff | 11.05..36.75 | 13.00..26.75 | 0..2.0 |
| in_cap | M2's micro-USB, its plug's overmould | 45.45..56.55 | 1.55..10.80 | 0..2.0 |
| in_cap | J5's frame and J4's face (one opening: 1.17 between them) | 40.35..61.88 | 13.00..22.87 | 0..2.0 |
| in_cap | the antenna's SMA bulkhead: Ø6.85, centre | 72.38 | 21.35 | 0..2.0 |
| in_cap | left block (y 0 edge): post | 2.70..9.70 | 2.70..27.30 | 2.0..8.0 |
| in_cap | left block (y 0 edge): ledge over the board | 9.70..10.80 | 13.65..27.30 | 2.0..4.3 |
| in_cap | left block (y 0 edge): ledge under the board | 9.70..12.00 | 2.70..11.65 | 2.0..3.5 |
| in_cap | left block (y 0 edge): ST2.2×9.5 screw through the top | 6.20 | 28.00..30.00 | 5.00 |
| in_cap | right block (y 60 edge): post | 70.30..77.30 | 2.70..16.40 | 2.0..8.0 |
| in_cap | right block (y 60 edge): lip over the board | 69.10..70.30 | 13.65..16.40 | 2.0..8.0 |
| in_cap | right block (y 60 edge): lip under the board | 68.00..70.30 | 2.70..11.65 | 2.0..8.0 |
| in_cap | ground block (over J4's side): block | 62.40..67.45 | 18.35..27.30 | 2.0..8.0 |
| in_cap | ground block (over J4's side): ST2.2×9.5 screw through the top, ground under it | 64.90 | 28.00..30.00 | 5.00 |
| in_cap | the saddle | -10.00..90.00 | -3.00..0.00 | 0..11.0 |
| in_cap | ear hole: Ø4.6, a teardrop, its point away from the flange | -5.00 | -3.00..0.00 | 6.50 |
| in_cap | ear hole: Ø4.6, a teardrop, its point away from the flange | 85.00 | -3.00..0.00 | 6.50 |
| out_cap | J6's frame | 58.85..69.05 | 13.30..22.87 | 0..2.0 |
| out_cap | J7's bushing: slot 13.20 wide, 13.80 tall, centre | 51.05 | 20.00 | 0..2.0 |
| out_cap | J9's bushing: slot 13.20 wide, 13.80 tall, centre | 34.21 | 20.00 | 0..2.0 |
| out_cap | J8's bushing: slot 13.20 wide, 13.80 tall, centre | 18.97 | 20.00 | 0..2.0 |
| out_cap | left block (y 60 edge): post | 2.70..9.70 | 2.70..27.30 | 2.0..8.0 |
| out_cap | left block (y 60 edge): lip over the board | 9.70..11.10 | 13.65..27.30 | 2.0..8.0 |
| out_cap | left block (y 60 edge): lip under the board | 9.70..12.00 | 2.70..11.65 | 2.0..8.0 |
| out_cap | left block (y 60 edge): ST2.2×9.5 screw through the top | 6.20 | 28.00..30.00 | 5.00 |
| out_cap | right block (y 0 edge): post | 70.30..77.30 | 2.70..27.30 | 2.0..8.0 |
| out_cap | right block (y 0 edge): lip over the board | 69.20..70.30 | 13.65..27.30 | 2.0..8.0 |
| out_cap | right block (y 0 edge): lip under the board | 68.05..70.30 | 2.70..11.65 | 2.0..8.0 |
| out_cap | right block (y 0 edge): ST2.2×9.5 screw through the top | 73.80 | 28.00..30.00 | 5.00 |
| out_cap | the saddle | -10.00..90.00 | -3.00..0.00 | 0..11.0 |
| out_cap | ear hole: Ø4.6, a teardrop, its point away from the flange | -5.00 | -3.00..0.00 | 6.50 |
| out_cap | ear hole: Ø4.6, a teardrop, its point away from the flange | 85.00 | -3.00..0.00 | 6.50 |

## Printing

- FDM in PETG or ASA (PLA softens in a parked car), or MJF PA12 from a print service; the outer face
  on the bed, no supports.
- 100 % infill: the screws are drilled into the blocks at assembly, and sparse infill round them would
  strip. The caps are in_cap 8.7 cm3 and out_cap 9.4 cm3, about 23 g of PETG together.

## Assembly

1. Before the board goes in (check_fit's notes): the FPGA flashed before M1 is soldered in (the RCA
   housings cover its USB-C); M1's tails cut flush underneath and J4's and J5's leads cut short before M2
   goes on; M2 hangs component side down; the RCA jacks' thin pins trimmed to 2 mm.
2. Measure the soldered board from its input end to the farthest of its output end and the RCA
   housings' fronts, and cut the tube to that +0.1/-0 mm. Drill 2.4 mm holes in its top for the screws
   (ISO 273 medium for 2 mm, so the screws do not tap the wall), 3.0 mm from each end, at u from the
   left edge seen from outside that end:
   - in_cap: u 6.20, left block (y 0 edge)
   - in_cap: u 64.90, ground block (over J4's side)
   - out_cap: u 6.20, left block (y 60 edge)
   - out_cap: u 73.80, right block (y 0 edge)

   Not through the tube's sides: a screw head there stands in the way of a screwdriver on the ear
   below it (5.0 mm from the side).
3. The antenna pigtail: clip its U.FL onto M2's WROVER-IE (component side down, the plug at the module's
   antenna end). Lead the cable off past the module's antenna end, not across its shield, under the
   board to its y = 60 edge, along that edge toward the input end, and round the edge up to the SMA's
   place more than 8 mm from the input end, past the cap's blocks. Tape it, the spare as a flat
   loop along that edge, to the board's underside so that nothing hangs below M2. Put the SMA through the
   input cap from the inside, its internal-tooth lock washer and nut outside.
4. Fit the input cap onto the board's input end, outside the tube: J1's housing through its opening,
   the board's edges into the slots.
5. Lay the tube on its top, and the board with its M2 side up. Slide the board, the input cap trailing,
   into the tube from its input end, output end first, until the flange sits on the tube's end. The
   board hangs from the input cap's slots (their play would let its free end droop 6.7 mm), so it
   can only come down onto the tops of J7/J8/J9, 1.25 mm under the tube's top; M2 and the pigtail
   move away from the tube's floor and rest on nothing.
6. Fit the output cap, still upside down: hold the board's end at the slots' height by the RCA
   bushings, which stand out of the tube's end, put the cap's slots over them and push it home: J6 through
   its opening, the board's edges into the slots over the lead-ins. Turn the tube right way up.
7. Set each flange flush with the tube's outline (that centres its blocks), drill each block 1.6 mm square
   through the tube's hole, about 8 mm deep (the thinnest wall round a pilot 1.30 mm, the pilot off
   the hole's centre by 0.4), and drive the four DIN 7981 C ST2.2×9.5 screws until their heads
   seat: the blocks stay up to 0.7 mm under the tube's top, the screws pin the caps and do not pull
   them up. Each grips 6.8 mm of its block, the ground screw 5.7 mm under its ring terminal
   and washer (see below).
8. Once the pigtail is plugged in, never let the board rest on M2: its EN/BOOT end lies 1.25 mm lower
   than the slots, and under the WROVER-IE's end the cable has only 0.88 mm with the caps on.

In the car: the tube's floor down on the two saddles, four screws through the ears.

## The ground bond

An M2 ring terminal and a serrated washer under the head of the ground block's screw (input cap, u
64.90, on the tube's top 3.0 mm from its end, over J4), a 3-5 cm wire to the GND wire of J4's
harness by its plug (soldered, heat-shrunk). A raw tube, or its anodizing scraped off under the washer.

## The antenna

- A U.FL-to-SMA pigtail, 150 mm (check_fit's path from the panel to the U.FL's zone, +20 % for the
  bends), any whose SMA female bulkhead jack is the plain hex type, 8 mm across flats (a flanged or
  O-ring one, 11 across, does not fit the 8 mm margin); its 1/4"-36 UNS-2A thread may be round or
  have flats. No particular one is chosen, so the hole is round, 6.85 mm (the thread's 6.35 + 0.25 a
  side), in the input cap above the board in the margin on J4's side (centre u 72.38, v 21.35).
  The nut and the jack's internal-tooth lock washer outside keep it from turning; the flange is 2.0 mm,
  within the 3.2 mm panel limit of Amphenol's SMA-to-U.FL assemblies (the least found).
- Behind the panel the jack has room to w 22.00 for its body, ferrule and boot: 1.00 mm off the tube's
  wall (0.30 with its cap shifted against it), clear of the blocks and the parts.
- The cable's route is step 3 above; the WROVER-IE's U.FL spot is unverified (check_fit takes the
  module's last 8.6 mm).
