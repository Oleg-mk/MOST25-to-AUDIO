// ctrl_uart.v - raw MOST25 control blocks out over UART, 8N1.
//
// A control message is 32 bytes carried two per frame (frame bytes 61, 62)
// over the 16 frames of a block (MOST Book 2, 5.1.1). Nothing is decoded here:
// the telegram layout and the CRC belong to the receiver's software.
//
// Packet, 42 bytes, once per block (2756 / 3000 per second at 44.1 / 48 kHz):
//   0  A5          sync
//   1  5A          sync
//   2..5           frame counter of the block's first frame, little endian
//   6              status: b0 locked, b1 block known, b6..b2 frames in the
//                  block with frame_par = 1, b7 a packet was dropped before
//   7..8           UI estimate, Q8.8 samples, little endian
//   9..40          the 32 control bytes, in order
//   41             XOR of bytes 0..40
// At 3 Mbaud a packet takes 140 us of a 333 us block, so nothing queues up.
//
// The same line carries the capture dumps (capture.v): 41-byte packets, sync
// A5 C5, sent one per gap between control packets. Control comes first: a
// block that completes while a capture packet is on the line waits for it
// (137 + 140 us fit in the 333 us block period), and only a block completing
// while the previous control packet has not even started is dropped (b7).
module ctrl_uart #(
    parameter DIV = 33                      // clk / baud: 99 MHz / 3 Mbaud
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        byte_we,
    input  wire [5:0]  byte_addr,
    input  wire [7:0]  byte_data,
    input  wire        frame_done,
    input  wire        frame_par,
    input  wire [3:0]  blk_idx,
    input  wire        blk_known,
    input  wire        locked,
    input  wire [15:0] ui_q,
    output reg         txd,
    // capture packets (capture.v): bytes 0..39 in cap_pkt, the XOR appended here
    input  wire        cap_req,
    input  wire [319:0] cap_pkt,
    output reg         cap_take,            // pulse: sending cap_pkt now
    output reg         cap_done             // pulse: cap_pkt has been sent
);
    // ------------------------------------------- collect, two banks of 32
    reg [7:0]  cram [0:63];
    reg        cbank;
    reg [31:0] fcnt;                        // frames since reset
    reg [4:0]  pones;                       // frames with parity 1 in this block
    always @(posedge clk) begin
        if (byte_we && byte_addr == 6'd61) cram[{cbank, blk_idx, 1'b0}] <= byte_data;
        if (byte_we && byte_addr == 6'd62) cram[{cbank, blk_idx, 1'b1}] <= byte_data;
    end

    // snapshot of the header for the finished bank; ctl_pend asks the sender
    // for a control packet and is cleared by its ctl_ack
    reg        ctl_pend, ctl_ack, sbank, dropped;
    reg [31:0] h_cnt;
    reg [7:0]  h_stat;
    reg [15:0] h_ui;
    reg        busy, cap_mode;
    always @(posedge clk) begin
        if (rst) begin
            cbank <= 1'b0; fcnt <= 32'd0; pones <= 5'd0; dropped <= 1'b0; ctl_pend <= 1'b0;
            sbank <= 1'b0; h_cnt <= 32'd0; h_stat <= 8'd0; h_ui <= 16'd0;
        end else begin
            if (ctl_ack) ctl_pend <= 1'b0;
            if (frame_done) begin
                fcnt  <= fcnt + 32'd1;
                if (blk_idx == 4'd15 && blk_known && locked) begin
                    if (ctl_pend && !ctl_ack) dropped <= 1'b1;   // the last one has not even started
                    else begin
                        ctl_pend <= 1'b1;
                        sbank  <= cbank;
                        h_cnt  <= fcnt - 32'd15;
                        h_stat <= {dropped, pones + {4'd0, frame_par}, blk_known, locked};
                        h_ui   <= ui_q;
                        dropped <= 1'b0;
                    end
                    cbank <= ~cbank;
                    pones <= 5'd0;
                end else begin
                    pones <= pones + {4'd0, frame_par};
                end
            end
        end
    end

    // ------------------------------------------------------------- sender
    reg [5:0] idx;                          // packet byte being sent
    reg [7:0] xsum;
    reg [7:0] cur;
    wire [5:0] ci = idx - 6'd9;             // control byte 0..31 for idx 9..40
    wire [5:0] last = cap_mode ? 6'd40 : 6'd41;
    always @* begin
        case (idx)
            6'd0: cur = 8'hA5;
            6'd1: cur = 8'h5A;
            6'd2: cur = h_cnt[7:0];
            6'd3: cur = h_cnt[15:8];
            6'd4: cur = h_cnt[23:16];
            6'd5: cur = h_cnt[31:24];
            6'd6: cur = h_stat;
            6'd7: cur = h_ui[7:0];
            6'd8: cur = h_ui[15:8];
            6'd41: cur = xsum;
            default: cur = cram[{sbank, ci[4:0]}];
        endcase
    end

    // Timing: picking the byte (a subtract, a RAM read, a 42-way choice and,
    // for a capture packet, a 40-way one) was the slowest path in the whole
    // clk_s domain, yet a byte is needed only once per 330 ns. So the byte is
    // picked in stages, one register each, once idx has settled: the capture
    // packet's 8-byte lane around idx (prep), the byte in that lane and the
    // control byte (prep2), the one of the two that goes out (prep3), then the
    // load. The bits then leave through a plain shift register, not a
    // variable bit select. (The 40-way pick in one clock took 9.2 of the
    // 10.1 ns once the S/PDIF encoder had moved the placement.)
    reg [7:0]    ctl_q, cap_q, cur_q;
    reg [63:0]   lane_q;
    reg [2:0]    lo_q;
    reg          x_q;
    wire [383:0] cap_ext = {64'd0, cap_pkt};        // idx 40 (the XOR) reads lane 5: zeros, unused
    always @(posedge clk) begin
        lane_q <= cap_ext[64 * idx[5:3] +: 64];
        lo_q   <= idx[2:0];
        x_q    <= (idx == 6'd40);
        ctl_q  <= cur;
        cap_q  <= x_q ? xsum : lane_q[8 * lo_q +: 8];
        cur_q  <= cap_mode ? cap_q : ctl_q;
    end

    reg [9:0] sh;                           // stop, data[7:0], start; sh[0] is on the line
    reg [3:0] bitpos;                       // bit on the line, 0 = start .. 9 = stop
    reg [7:0] tick;
    reg       prep, prep2, prep3, load;
    always @(posedge clk) begin
        ctl_ack <= 1'b0; cap_take <= 1'b0; cap_done <= 1'b0;
        if (rst) begin
            busy <= 1'b0; cap_mode <= 1'b0; txd <= 1'b1; idx <= 6'd0; xsum <= 8'd0; prep <= 1'b0; prep2 <= 1'b0;
            prep3 <= 1'b0; load <= 1'b0; bitpos <= 4'd0; tick <= 8'd0; sh <= 10'h3FF;
        end else if (!busy) begin
            txd <= 1'b1;
            if (ctl_pend) begin                              // control first
                busy <= 1'b1; cap_mode <= 1'b0; idx <= 6'd0; xsum <= 8'd0; prep <= 1'b1; ctl_ack <= 1'b1;
            end else if (cap_req) begin                      // a capture packet in the gap
                busy <= 1'b1; cap_mode <= 1'b1; idx <= 6'd0; xsum <= 8'd0; prep <= 1'b1; cap_take <= 1'b1;
            end
        end else if (prep) begin
            prep <= 1'b0; prep2 <= 1'b1;    // lane_q, lo_q, x_q and ctl_q catch idx at this edge
        end else if (prep2) begin
            prep2 <= 1'b0; prep3 <= 1'b1;   // cap_q catches the byte of the lane at this edge
        end else if (prep3) begin
            prep3 <= 1'b0; load <= 1'b1;    // cur_q catches the chosen one at this edge
        end else if (load) begin
            sh     <= {1'b1, cur_q, 1'b0};
            xsum   <= xsum ^ cur_q;
            txd    <= 1'b0;                 // start bit
            bitpos <= 4'd0;
            tick   <= DIV - 1;
            load   <= 1'b0;
        end else if (tick != 8'd0) begin
            tick <= tick - 8'd1;
        end else if (bitpos == 4'd9) begin
            // stop bit has been on the line for a full bit time
            if (idx == last) begin busy <= 1'b0; if (cap_mode) cap_done <= 1'b1; end
            else begin idx <= idx + 6'd1; prep <= 1'b1; end
        end else begin
            sh     <= {1'b1, sh[9:1]};
            txd    <= sh[1];
            bitpos <= bitpos + 4'd1;
            tick   <= DIV - 1;
        end
    end
endmodule
