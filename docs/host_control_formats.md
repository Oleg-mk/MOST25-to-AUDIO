# MOST25 control channel: host decode reference (primary sources only)

Compiled for the ESP32 host (passive listener: receives the raw 32-byte
control blocks, decodes telegrams, tracks the AuxIn 0x24 channels and whether the
AudioAmplifier 0x22 is connected to them).

Every fact cites file + page. **(inferred)** means that two or more stated facts are
combined and no single sentence in a source says it. **NOT FOUND** means that all the
sources below were searched and none of them has it.

## 0 Sources

Paths are inside the MOST specification archive (not in this repository) unless noted.

| Key | Document | File | Page numbers cited |
|---|---|---|---|
| CORE | MOST Specification Rev 2.5, 10/2006 | `specifications/MOST_version_2V5/MOST_2V5_Application.zip` > `1_Core/Specification_2V5-0.zip` > `MOSTSpecification.pdf` | printed = PDF page |
| CORE30 | MOST Specification Rev 3.0 E2, 07/2010 | `MOST_version_3V0/MOST_3V0_Application.zip` > `1_Core/Specification_3V0-0.zip` > `MOSTSpecification_3V0E2.pdf` | printed = PDF |
| BOOK | MOST Book 2 (Grzemba, "from MOST25 to MOST150") | `most-book/MOST_Book_2.pdf` | **printed** page (= PDF page - 1) |
| STX | MOST Specification for Stream Transmission Rev 1.3.1, 12/2007 | `MOST_2V5_Application.zip` > `6_Stream_Transmission/Stream_Transmission_Specification_1V3-1.zip` > `MOST_Stream_Transmission_Rev1_3_1.pdf` | printed = PDF |
| GFB25 | FBlock Template GeneralFBlock, Speed Grade MOST25, Rev 2.5.1, 10/2007 | `MOST_2V5_FBlock_Library.zip` > `2_Applicative_FBlocks/FBlock_Template_GeneralFBlock_oPhy25_2V5-1.zip` > `MOST25 FunctionBlock GeneralFBlock_Rev2_5_1.pdf` + `MOST25_GeneralFBlock_2_5_1.xml` | printed = PDF |
| AUX | FBlock AuxIn Rev 3.5.2, 02/2013 | same library > `FBlock_AuxIn_3V5-2.zip` > `MOST_FBlock_AuxIn_3V5-2.pdf` / `.xml` | printed = PDF |
| AMP | FunctionBlock AudioAmplifier Rev 2.4.3, 07/2011 | `extracted/FBlock_AudioAmplifier_2V4-3/` | printed = PDF |
| CM25 / NM25 / NB25 | ConnectionMaster / NetworkMaster / NetBlock, Speed Grade MOST25, Rev 2.5.1 | library > `1_System_FBlocks/FBlock_{ConnectionMaster,NetworkMaster,NetBlock}_oPhy25_2V5-1.zip` | printed = PDF |
| OS | Oasis OS8104 Final Product Data Sheet DS8104FP4, Jan 2003 | not in the spec mirror: the NIC maker's data sheet | printed = PDF |

`pdftotext -layout` scrambles the columns of CORE Tables 2-1, 2-4, 3-1, 3-6 and 3-7, of the TelID table
on p.179 and of Table 3-19. Every value from those tables was checked against a rendered image of the
page.

## 1 MOST25 frame: 64 bytes = 512 bits

| Frame byte | Bits | Content | Source |
|---|---|---|---|
| 0 | 0-3 | Preamble (a coding violation; the bit pattern is not given) | CORE T3-1 p.108; BOOK T5.1 p.87 |
| 0 | 4-7 | Boundary Descriptor BD = quadlets of streaming data, 6..15 | CORE p.107, 3.1.3.1.2 p.110; BOOK p.88 |
| 1..60 | 8-487 | Data Byte 0..59: streaming area first, then packet area | CORE T3-1, p.107; BOOK T5.1 |
| 61 | 488-495 | "Control frame Byte 0" | BOOK T5.1 |
| 62 | 496-503 | "Control frame Byte 1" | BOOK T5.1 |
| 63 | 504-510 | "Frame control and status bits" | CORE T3-1; BOOK T5.1 |
| 63 | 511 | Parity bit | CORE T3-1; BOOK T5.1 |

- Streaming bytes = 4*BD (24..60) and packet bytes = 60 - 4*BD (at most 36). "All Stream data bytes are
  transmitted before any Packet data bytes occur." CORE p.107, p.110, Table 3-3 p.112.
- Frame rate: 30..50 kHz is allowed. "The typical frame rate is 44,100 frames/second" (MOST25).
  CORE p.107, p.114.
- **Channel number vs. frame byte: channel N = Data Byte N = frame byte N+1 (bits 8+8N..15+8N),
  N = 0..59. Channel 0 is frame byte 1, not frame byte 2.** These sources state the links in the chain:
  - STX 5.4.1.1 p.19: "Channel: Number of a data byte in the MOST frame".
  - GFB25 p.30/31: the Channel range is 0..59.
  - BOOK T5.1 p.87: frame byte 1 = Data Byte 0 ... frame byte 60 = Data Byte 59.
  - OS 12 p.97: MRT0x00..0x3B = the 60 network byte positions.
  - OS 14.1 p.131: "CRA0F stands for the physical channel number 0Fh in the MOST frame".
  - OS 8.3.3 p.77: "the first frame source data byte at 0".

  No single sentence says "N+1". The listener's host commands 01/02 take *frame* byte indices 0..63
  (`listener_gw/README.md`), so the host must add 1 to every channel number.
- The meaning of bits 504-510 and the parity sense and coverage are NOT FOUND. CORE 3.1.3.1.3 p.112
  says only that the parity bit "indicates reliable data content and is used for error detection and
  phase lock loop operation".

## 2 Control block: 32 bytes over 16 frames

"A MOST25 Control Message has a fixed size of 32 bytes and is time multiplexed over 16 MOST frames,
each having two Control data bytes." (CORE p.108). A block = 16 frames (CORE 3.1.3.2 p.113; OS 6.1 p.36).

| Block byte | Field | Source |
|---|---|---|
| 0-3 | Arbitration (CSMA; "relies on the first two frames (4 bytes)") | CORE T3-6 p.116; BOOK Fig 5.11 p.100 |
| 4-5 | Target address | CORE T3-6; BOOK p.101 |
| 6-7 | Source ("own") address. The receiver gets the sender's *logical* address here | CORE T3-6; CORE 3.4.1 p.173; OS 13.2.6 p.119 |
| 8 | Message type | CORE T3-6; BOOK p.101 |
| 9-25 | Data area, 17 bytes (the AMS telegram, section 3) | CORE T3-6; CORE 3.4.6.1 p.178 |
| 26-27 | CRC | CORE T3-6; BOOK Fig 5.11 |
| 28-29 | Transmission status (acknowledge) | CORE T3-6; BOOK p.102 |
| 30-31 | Reserved | CORE T3-6 |

- **Block start:** "The preamble of the first frame of a block has a specific bit pattern to identify
  the block." (BOOK p.100). The pattern is NOT FOUND. A block or frame counter in byte 63 is NOT FOUND:
  no source defines bits 504-510.
- Frame k of the block (k = 0..15) carries bytes 2k (frame byte 61) and 2k+1 (frame byte 62)
  (inferred from "16 x 2 Bytes", BOOK Fig 5.12 p.100, and the T5.1 names).
- Addresses are high byte first (inferred from the register order in OS: mXCMB C2h target high /
  C3h target low on p.120, mRCMB A1h source high on p.119).
- **Message type codes:** 0x00 Normal, 0x01 Remote Read, 0x02 Remote Write, 0x03 Resource Allocate,
  0x04 Resource De-allocate, 0x05 Remote GetSource. Sources: BOOK p.101-102 (Fig 5.13 "source: [DS 8104]");
  OS Table 13-13 p.124. CORE p.116 names these types but gives no codes. Allocate and De-allocate always
  go to the TimingMaster, normally to physical address 0x0400 (OS p.111, p.127).
- **Two blocks in every 64 are not control messages.** "Only 62 of 64 transmitted blocks are available
  for control messages. Two blocks are used for the intra-system network administration such as the
  transmission of the channel resource allocation table." (BOOK p.103). Also:
  - OS 2.5.1 p.21: 62*Fs/1024 messages/s = 2906/s at 48 kHz. BOOK eq. 5.4: 2670/s at 44.1 kHz.
  - OS 14 p.131: the mCRA is "distributed to all nodes ... at regular intervals (every 1024 frames)".

  Which two blocks these are, and their byte format, is NOT FOUND. In NIC memory the mCRA cells are
  0x70 = free and 0x00..0x3B = the Connection Label (= the first channel of that allocation); in the
  TimingMaster the MSB = "in use" (OS T14-2/14-3 p.132). No source says that the wire carries these
  same values.
- **CRC:** the polynomial, initial value, byte coverage and bit order are NOT FOUND. CORE, CORE30,
  BOOK, OS and all 192 PDFs of the 2V5/3V0/3V1/4V0 bundles were searched. The only polynomial is the
  EnhancedTestability DSI CRC-32 0x04C11DB7 (ET 2V6-2, 2.1.16, p.31). That one is an application
  checksum over MHP data, not the control-channel CRC.
- **Transmission status:** the receiver writes one of "Message successfully received / Cache blocked /
  CRC error". The receiver "can only write on the flag and has no possibility to reset it", so in
  group/broadcast the sender sees a failure in any receiver (BOOK p.102).
  - The NIC register bXTS holds: 00h no response, 10h success, 11h success but the message type is not
    supported, 20h bad CRC at the receiver, 21h receiver buffer full, 30h/31h = the OR of different
    acknowledges in group/broadcast (OS 13.2.3 p.118).
  - The byte encoding of bytes 28-29 on the wire is NOT FOUND. The OR remark suggests the same codes
    (inferred). The value that the listener sees depends on its ring position relative to the
    receivers (inferred).
- **Retries:** 6 attempts by default (bXRTY=06h), spaced bXTIM=0Bh = 11 block times, about 4 ms at
  44.1 kHz (OS 13.2.4-5 p.118-119; BOOK p.102-103). A NAKed message therefore shows up to 6 times on
  the wire (inferred; CORE p.117 "automatic retransmission").
- **Spacing:** a node arbitrates again only in the third block after its last message (OS p.21;
  BOOK p.104: "pause for two messages").
- **Groupcast/broadcast:** only 16 of the 17 data bytes are usable. "One byte is used to secure
  groupcast" (OS 13.1.3 p.113; also 13.2.7 p.120 and 13.3 p.121). "reduced by one byte for the
  checksum" (BOOK p.112).
  - So byte 25 of a block to 0x0300..0x03FF is a NIC checksum; its algorithm is NOT FOUND.
  - Such a telegram holds at most 11 data bytes (inferred: 5 header bytes + 11 = 16).
- **Target 0x0000:** CORE30 p.176 says that a blocking broadcast is released by a "free-up message"
  sent to 0x0000, which is "never handed over to the Application Layer". Whether MOST25 does this is
  NOT FOUND in the 2V5-era sources. Do not decode target 0x0000 as a telegram.
- **System-message data areas** (OS mXCMB tables; mXCMB C4h = data byte 0 = block byte 9, inferred):

  | Type | Data bytes | Source |
  |---|---|---|
  | 03h Resource Allocate | D1 = channels wanted 1..8<br>D3 Answer1: 01 GRANT, 02 BUSY, 03 DENY, 04 bad count, 05 WRONG_TARGET<br>D4 = free channels<br>D5..D12 = P0..P7 channel numbers (FFh = unused); P0 = Connection Label | T13-18/19 p.127 |
  | 04h Resource De-allocate | D1 = Connection Label (7Fh = De-allocate All)<br>D3 Answer1: 01 GRANT, 02 BUSY, 04 WRONG, 05 WRONG_TARGET | T13-20/21 p.129 |
  | 05h Remote GetSource | sent to 03C8h<br>D1 = CL<br>answer: D6 = node position, D8 = group address, D9-D10 = logical address | p.130 |

  The TimingMaster answers inside the same message, which returns to the sender ("the response ...
  is stored in the transmit buffer", OS p.126). The listener sees the answer only when it sits
  downstream of the TimingMaster (inferred).

## 3 AMS telegram in the data area (CORE 3.4.6.2 p.179)

| Block byte | Data-area byte | Field |
|---|---|---|
| 9 | 0 | FBlockID (8 bit) |
| 10 | 1 | InstID (8 bit) |
| 11 | 2 | FktID bits 11..4 |
| 12 | 3 | FktID bits 3..0 (high nibble), OPType (low nibble) |
| 13 | 4 | TelID (high nibble), TelLen (low nibble) |
| 14..25 | 5..16 | Data 0 .. Data 11 |

The CORE diagram gives the field order and the widths (8, 8, 12, 4, 4, 4 bits, then 12 bytes).
MSB-first nibble packing is inferred from that diagram. The DeviceID (16 bit) is the RxTxAdr, i.e.
the block's target/source field, and is not in the data area (CORE 2.3.2.1 p.28; p.179).

- **TelLen:** 0..12. "it is mandatory that the TelLen is the exact length of the valid data"
  (CORE p.179).
- **TelID values** (CORE p.179 table):

  | TelID | Meaning | Data 0 |
  |---|---|---|
  | 0 | single transfer | payload |
  | 1 | first segment | MsgCnt = 0x00 |
  | 2 | middle segments | MsgCnt 0x01..0xFF, then 0x00... (wraps) |
  | 3 | last segment | MsgCnt continues |
  | 8 | MOST High Protocol user data | |
  | 9 | MOST High Protocol control data | |

- **MsgCnt counts in TelLen:** "the first data byte is used as telegram counter, i.e., there are only
  11 data bytes available ... for the TelID 1 or 2, the TelLen is always 12. It can be shorter for the
  TelID 0 or 3." (BOOK p.103).
- **Reassembly:** the length is "reconstructed from the number of received telegrams and the TelLen"
  (CORE 2.3.2.6 p.46). The message = Data1..Data(TelLen-1) of TelID 1, 2..., 3 in MsgCnt order
  (inferred). Every telegram repeats FBlockID/InstID/FktID/OPType (the p.179 layout).
- **Maximum lengths:** single transfer <= 12 bytes (CORE p.46, p.178). A message is at most 65535
  bytes (the 16-bit Length, CORE p.46); CORE p.178 says "65536" (**contradiction inside CORE**).
- **Segment timeout:** tWaitForNextSegment = 4975 / 5000 / 10015 ms, after which "garbage collection
  is initiated" (CORE T3-19 p.200).
- **Segmentation error** 0x0C, ErrorInfo (CORE T2-5 p.36):
  - 01 first segment missing
  - 02 not enough buffers
  - 03 unexpected segment number
  - 04 too many unfinished messages
  - 05 timeout for the next segment
  - 06 cannot handle segmented messages
  - 07 "Segmented message has not been finished before the arrival of another message sent by the
    same node"

  So one sender has at most one segmented message in flight (inferred).
- **Parameter encoding:** parameters are MSB first; signed values are 2's complement (CORE 2.3.2.7
  p.46).
- **Error reports:** Data[0] = ErrorCode, then the ErrorInfo. For ErrorAck these come after a 2-byte
  SenderHandle (CORE p.36 and footnote). There is no error reply to a broadcast (CORE p.37).
- **FktID ranges** (CORE 2.3.2.4 p.33):
  - 0x000-0x1FF coordination
  - 0x200-0x3FF mandatory
  - 0x400-0x9FF extension
  - 0xA00-0xBFF unique
  - 0xC00-0xEFF system-integrator specific
  - 0xF00-0xFFE supplier specific
- **InstID:** 0x01 is the default. 0x00 = "don't care", one instance in the device. 0xFF = all
  instances. For NetBlock and ET, InstID = node position (CORE 2.3.2.3 p.31-32). FBlockID 0xFF = all
  FBlocks of the device except NetBlock (CORE p.29).

**OPType** (CORE Table 2-4 p.35; 0x0-0x8 are commands, 0x9-0xF are reports):

| Code | Property | Method |
|---|---|---|
| 0x0 | Set | Start |
| 0x1 | Get | Abort |
| 0x2 | SetGet | StartResult |
| 0x3 | Increment | reserved |
| 0x4 | Decrement | reserved |
| 0x5 | GetInterface | GetInterface |
| 0x6 | not allowed | StartResultAck |
| 0x7 | not allowed | AbortAck |
| 0x8 | not allowed | StartAck |
| 0x9 | reserved | ErrorAck |
| 0xA | not allowed | ProcessingAck |
| 0xB | reserved | Processing |
| 0xC | Status | Result |
| 0xD | not allowed | ResultAck |
| 0xE | Interface | Interface |
| 0xF | Error | Error |

All *Ack OPTypes carry SenderHandle (TUWord, 2 bytes) as the first parameter (CORE 2.3.2.5.4 p.44;
TUWord per CM25 XML).

## 4 FBlocks, functions, parameters

**FBlockIDs** (CORE Table 2-1/2-2 p.29-30, checked on the page image):

| FBlockID | FBlock |
|---|---|
| 0x01 | NetBlock |
| 0x02 | NetworkMaster |
| 0x03 | ConnectionMaster |
| 0x04 | PowerMaster |
| 0x0F | EnhancedTestability |
| 0x20 | Audio Master |
| 0x21 | Audio DSP |
| **0x22** | **Audio Amplifier** |
| 0x23 | HeadphoneAmplifier |
| **0x24** | **AuxiliaryInput (AuxIn)** |
| 0x26 | MicrophoneInput |
| 0x28 | Handsfree Processor |
| 0x31 | Audio Disk Player |
| 0x40 | AM/FM Tuner |
| 0x50 | Telephone |
| 0xA0-0xC7, 0xC9-0xEF | system specific |
| 0xF0-0xFB | supplier specific |
| 0xFC | Secondary Node (MOST25) |
| 0xFF | All |

The catalogues agree: AMP XML `<FBlockID>0x22</FBlockID>`, AUX XML `<FBlockID>0x24</FBlockID>`.

**Which catalogue defines the source/sink functions: GFB25** (the MOST25 GeneralFBlock 2.5.1).

- AUX p.14 lists these functions as "included here by reference":
  - 0x000 FktIDs, 0x001 Notification, 0x002 NotificationCheck, 0x011 FBlockInfo
  - 0x100 SourceInfo, 0x101 Allocate, 0x102 DeAllocate, 0x103 SourceActivity, 0x104 SourceName
  - 0x116 StreamDataInfo (the 3.x name of SyncDataInfo)
  - the player functions

  SourceConnect and SourceDisConnect are not in the list.
- AMP p.7 includes by reference:
  - 0x000-0x002, 0x010 Version
  - 0x110 SinkInfo, 0x111 Connect, 0x112 DisConnect, 0x113 Mute, 0x114 SinkName
  - 0x115 ConnectTo, 0x116 SyncDataInfo, 0x117 SinkRouting

  AMP's own Mute (0x113) was removed and is now referenced from GeneralFBlock (AMP XML changelog;
  PDF p.6). FadeInOut 0x401 is obsolete: "use Mute property (FktID=0x113) with SinkNr=0 instead"
  (AMP p.15).
- **Caveat:** AUX 3.5.2 (p.6-7, change 3V5-2-001) re-points its references from GeneralFBlock 2.5.1
  to 3.0.4. The 3.0.x template (3V0-7 XML) defines only MOST50/MOST150 (BlockWidth +
  ConnectionLabel). CORE30 p.25 records that ChannelList, SrcDelay and SourceConnect were removed as
  MOST25-specific. On a MOST25 ring use the GFB25 forms below.

**Source functions** (GFB25 PDF p.29-34 + XML; parameters in wire order = ParamPos):

| FktID | Name | OPType -> parameters |
|---|---|---|
| 0x100 | SourceInfo (property) | Get 0x1: SourceNr<br>Status 0xC: SourceNr, DataType, DataDescription<br>Error 0xF |
| 0x101 | Allocate (method) | StartResult 0x2: SourceNr<br>Processing 0xB: (none)<br>Result 0xC: SourceNr, SrcDelay, ChannelList<br>Error 0xF |
| 0x102 | DeAllocate | StartResult: SourceNr<br>Result: SourceNr |
| 0x103 | SourceActivity | StartResult: SourceNr, Activity<br>Result: SourceNr, Activity<br>Activity: 0x00 Off, 0x01 Pause, 0x02 On |
| 0x104 | SourceName | Get: SourceNr<br>Status: SourceNr, SourceName (String, MaxSize 11) |
| 0x105 | SourceConnect | StartResult: SourceNr, ChannelList<br>Result: SourceNr, SrcDelay |
| 0x106 | SourceDisConnect | StartResult: SourceNr<br>Result: SourceNr |
| 0x116 | SyncDataInfo (property) | Get: (none)<br>Status: SourceCount, SinkCount |

**Sink functions** (GFB25 p.36-42):

| FktID | Name | OPType -> parameters |
|---|---|---|
| 0x110 | SinkInfo | Get: SinkNr<br>Status: SinkNr, DataType, DataDescription (PCM: Resolution, AudioChannels, SinkDelay, ChannelList) |
| 0x111 | Connect | StartResult 0x2: SinkNr, SrcDelay, ChannelList<br>Processing<br>Result 0xC: SinkNr<br>Error |
| 0x112 | DisConnect | StartResult: SinkNr<br>Result: SinkNr |
| 0x113 | Mute (property) | Get: SinkNr<br>SetGet 0x2: SinkNr, Status<br>Status 0xC: SinkNr, Status<br>SinkNr 0x00 = all sinks; Status bit 0 = 1 means Mute On, bits 1-7 reserved<br>No Set OPType is listed |
| 0x114 | SinkName | Get: SinkNr<br>Status: SinkNr, SinkName |
| 0x115 | ConnectTo | StartResult: FBlockID, InstID, SourceNr<br>Result: the same |

**Parameter details:**
- **Types:** SourceNr, SinkNr, SrcDelay, Resolution and AudioChannels are TUByte. ChannelList =
  Stream of Channel (TUByte 0..59), at most 60 entries, with no count byte. As the last parameter its
  length follows from the message length (GFB25 p.30-31).
- **Numbering:** sources and sinks are numbered from 1 with no gaps (CORE p.181).
- **Allocate error:** ErrorCode 0x20 "function specific", then SourceNr and RequiredChannels. An
  allocation is "never done partially" (CORE p.184).
- **DataType** (GFB25 p.29, p.37):
  - 0x00 PCM, 0x01 CDROM, 0x02 SPDIF
  - 0x20/0x21/0x22 MPEG1 System / MPEG2 Program / MPEG2 Transport
  - 0x40-0x42 the DTCP variants
  - 0xFF Unknown

  **STX Table 5-1 p.18 differs:** 0x00 Audio, 0x01 CD ROM, 0x02 S/PDIF, 0x10 GenericPCM, 0x11 GenericPCM
  with DTCP. STX also says: "If the SourceInfo property is not implemented by the source, 'Audio' is the
  default data type."
- **PCM DataDescription** = Resolution (bytes per sample), AudioChannels, SrcDelay (SinkDelay in
  SinkInfo), ChannelList.
- **Stereo 16-bit takes 4 channels:**
  - STX 5.4.1.1 p.18-19: Resolution 0x02, AudioChannels 0x02, sequence "MSB left, LSB left, MSB right,
    LSB right" (Fig 5-4).
  - OS 2.2.1 p.19: "a stereo CD-audio channel requires four of the byte-wide physical channels".
- **Channel lists** "must always be in ascending order"; an unordered list gets error 0x06
  (CORE 3.5.2.2.4 p.187). So ChannelList[0..3] = L-Hi, L-Lo, R-Hi, R-Lo (inferred from the ascending
  rule and the sequence).
- **Other stream rules** (STX):
  - The channel order is front-left, front-right, rear-left, rear-right (p.18).
  - A ChannelList entry of 0xFF means "not allocated/connected" (p.19).
  - Samples are HiByte first, bits MSB first, left-adjusted, and unused bits are 0 (5.2 p.15).
  - 24-bit audio uses 3 bytes per channel (Fig 5-5 p.19).

**ConnectionMaster 0x03** (CM25 PDF p.10-14 + XML; CORE 3.7.2.1 p.190-191):
- **0x200 BuildSyncConnection:**
  - StartResult: SourceFBlock, SourceInstID, SourceNr, SinkFBlock, SinkInstID, SinkNr. Result:
    the same.
  - The Ack form puts SenderHandle first; "Ack and non-Ack must not be mixed".
  - CM error info: 0x10 not enough channels, 0x11 busy, 0x12 source error, 0x13 sink error,
    0x14 sink in use, 0x15 source/sink mismatch. A failure is reported as ErrorAck 0x42 (CORE p.191).
- **0x201 RemoveSyncConnection:** the same parameters.
- **0x400 SyncConnectionTable.Status:** {SourceFBlock, SourceInstID, SourceNr, SinkFBlock, SinkInstID,
  SinkNr, SrcDelay, NoChannels, ChannelList}, repeated.

**To map address to FBlock:**
- NM25 0xA00 Configuration.Status (broadcast) = ConfigurationControl (00 NotOK, 01 OK, 02 Invalid,
  03 New) + DeltaFBlockList {FBlockID, InstID}... (NM25 p.9).
- NM25 0xA01 CentralRegistry.Status = {RxTxLog (TUWord), FBlockID, InstID}... (NM25 p.10).
- NB25 0x000 FBlockIDs.Status = {FBlockID, InstID}..., sent by each device with its logical address
  in the source field (NB25 p.10).

## 5 Addresses

CORE Table 3-7 p.118 (checked on the page image):

| Range | Meaning |
|---|---|
| 0x0000-0x000F | internal communication |
| 0x0010-0x00FF | static |
| 0x0100-0x013F | dynamic logical = 0x0100 + position |
| 0x0140-0x02FF | static |
| 0x0300-0x03FF | group / broadcast |
| 0x0400-0x043F | node position = 0x0400 + position |
| 0x0440-0x04FF | reserved |
| 0x0500-0x0FEF | static |
| 0x0FF0 | optional debug |
| 0x0FF1-0x0FFD | reserved |
| 0x0FFE | init address of the Network Service |
| 0x0FFF | init address of the NIC (the OS8104 reset default, OS 13.1.1 p.112) |
| 0x1000-0xFFFE | reserved |
| 0xFFFF | uninitialized logical address |

- **Positions:** the TimingMaster is position 0, logical 0x0100, physical 0x0400. There are at most
  64 nodes (CORE 3.4.1 p.173-174, p.106).
- **Group address:** the default is 0x0300 + the FBlockID of the device's most characteristic FBlock
  (CORE p.174; BOOK p.111). So an amplifier would default to 0x0322 and an AuxIn device to 0x0324
  (inferred example).
- **Blocking broadcast** = 0x03C8 (CORE p.28; OS 13.1.4 p.113).
- **Groupcast ranges** = 0x0300-0x03C7 and 0x03C9-0x03FF (OS T13-1 p.113).
- **Unblocking broadcast 0x03FF** exists only in the 3.0 sources (CORE30 p.176; BOOK T5.7 p.109
  "[MOST 3.0]"). In the MOST25 sources 0x03FF is an ordinary group address.
- **DeviceID 0xFFFF:** an application may send with DeviceID 0xFFFF. The Network Service replaces it
  before transmission (CORE p.28, 3.4.4 p.176), so 0xFFFF should never be a target on the wire.
- **What the listener should do** (inferred): decode every target and classify it by range. Select
  telegrams by FBlockID and FktID, not by address, because the amp and AuxIn can be reached by
  logical, group or broadcast addresses.

## 6 How a source gets connected to the amplifier (MOST25)

**Build sequence** (CORE 3.7.2.2 p.192-193, Fig 3-30):
1. The initiator calls CM BuildSyncConnection.
2. The CM sends Allocate (or SourceConnect) to the source.
3. The source allocates. If the TimingMaster is busy it retries up to 20 times (tResourceRetry
   <= 10 ms, p.199).
4. The source answers Allocate.Result (SourceNr, SrcDelay, Channels), or Allocate.Error (SourceNr,
   RequiredChannels).
5. The CM sends Connect (SinkNr, SrcDelay, Channels) to the sink.
6. The sink connects.
7. The sink answers Connect.Result.
8. The CM answers BuildSyncConnection.ResultAck. On failure all changes are undone.

A second sink on the same source only needs Connect.

**Other rules:**
- **Removal** (3.7.2.3 p.194-195): sink DisConnect; then, if no other sink uses the channels, source
  DeAllocate (or SourceDisConnect); then RemoveSyncConnection.ResultAck.
- **Repeated commands** (3.5.2.2.3 p.186): a repeated Allocate gets a normal Result with the channels
  already allocated. A Connect with other channels makes the sink disconnect and reconnect, and the
  new SrcDelay is used.
- **Source drop** (3.7.2.4.2 p.196): the source routes zeros for tCleanChannels (3.5/5/25 ms, p.200),
  then disconnects.
- **Deadlock timer:** tCM_DeadlockPrev <= 1000 ms (p.200).

**BOOK:**
- Fig 4.10 p.75 gives the order [opt] SourceInfo.Get/Status -> Allocate -> Connect -> [opt]
  SourceActivity(On). It is drawn in the 3.0 form (Ack OPTypes, BlockWidth, ConnectionLabel), not the
  MOST25 ChannelList form.
- p.77: a central infotainment instance "often also adopts the tasks of the ConnectionMaster. The
  FBlock ConnectionMaster is, in this case, often only implemented for debugging purposes". So expect
  the head unit to send Allocate and Connect itself, with no BuildSyncConnection on the wire.
- Fig 17.6 p.286 (phone gateway): BuildSyncConnection -> SourceConnect -> Connect ->
  BuildSyncConnection.ResultAck.

**Host tracking rule** (inferred from all of the above):
- AUX channels = the ChannelList in 0x24.0x101 Result (OPType 0xC). Alternatively, the ChannelList in
  0x24.0x100 SourceInfo.Status.
- The amp listens to them when 0x22.0x111 StartResult (0x2) carries the same list and is confirmed by
  0x22.0x111 Result (SinkNr).
- The connection ends on 0x22.0x112 DisConnect or 0x24.0x102 DeAllocate.
- Connect.Result carries no channels, so keep the StartResult list per SinkNr.
- 0x24.0x103 SourceActivity (0x02 On / 0x01 Pause / 0x00 Off) says whether AUX is really playing.

## 7 NOT FOUND and contradictions (summary)

**NOT FOUND in any listed source:**
- the control CRC (polynomial, initial value, coverage, bit order)
- the wire encoding of the transmission status in bytes 28-29
- the contents of arbitration bytes 0-3
- the block-start preamble pattern
- the meaning of frame-control bits 504-510, and any block counter there
- the parity sense and coverage
- the position and format of the 2 administrative blocks in every 64
- the group/broadcast checksum algorithm (byte 25)
- the content of an idle block
- whether MOST25 uses the 0x0000 free-up message

**Contradictions:**
- **Maximum message length:** CORE p.46 gives 65535; CORE p.178 says 65536.
- **DataType codes:** GFB25 (0x20..0x42 MPEG/DTCP, no 0x10) differs from STX T5-1 (0x10/0x11
  GenericPCM).
- **Which GeneralFBlock AuxIn points to:** AUX 3.5.2 refers to GeneralFBlock 3.0.4, which has no
  MOST25 definition. Use GFB25 2.5.1.
- **The book's sequence chart:** BOOK Fig 4.10 shows the MOST 3.0 function signatures, not the
  MOST25 ones.
- **OS 13.2.6 p.119** says "For Groupcast and Broadcast, the data bytes are bRCD4 to bRCD15". This
  does not match its own 16-byte statements (13.1.3, 13.2.7, 13.3); the meaning is unclear.
