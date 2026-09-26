# virtual_most_source - MOST25 frames and line coding

What the simulations in `listener_gw/sim` feed the listener with:
`make_stim.py` builds real MOST25 frames here, turns them into the
Biphase Mark line, then distorts and samples it.

| Module | What it holds |
|---|---|
| `most_spec.py` | every constant the specifications fix - frame and control block layout, bit and UI rates, line coding, FBlock and function IDs - each with its source |
| `config.py` | what the specifications leave open (parity rule, frame control, CRC mode, boundary descriptor, stream offsets), as settings; `PREAMBLE_SETS` names the preamble shapes the simulations run with - the placeholder and an S/PDIF-like one with two 3UI runs |
| `frame_builder.py` | complete 64-byte frames: preamble nibble, boundary descriptor, 60 data bytes, control bytes, frame control, parity |
| `bmc.py` | Biphase Mark encoding into runs of 1, 2 or 3 UI with the preamble's coding violation, and the decoder back |

These are four modules of a larger desktop MOST source written earlier;
only what the stimulus needs came along.

Tests (no simulator needed):

```text
python -m virtual_most_source.tests.test_frames
```

They check the specification constants and exact timing (no drift over an
hour of UI), the function IDs against the FBlock catalogue, the frame layout
(sample positions, control bytes, parity catching a flipped bit, refused
settings), and the line coding for every preamble set (only 1/2/3-UI runs,
3-UI runs only inside preambles and every frame opening with one, a decode
back to the same frames, a 4-UI run refused).
