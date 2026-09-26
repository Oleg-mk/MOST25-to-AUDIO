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
    output reg         txd
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

    // snapshot of the header for the finished bank
    reg        go, sbank, dropped;
    reg [31:0] h_cnt;
    reg [7:0]  h_stat;
    reg [15:0] h_ui;
    reg        busy;
    always @(posedge clk) begin
        go <= 1'b0;
        if (rst) begin
            cbank <= 1'b0; fcnt <= 32'd0; pones <= 5'd0; dropped <= 1'b0;
            sbank <= 1'b0; h_cnt <= 32'd0; h_stat <= 8'd0; h_ui <= 16'd0;
        end else if (frame_done) begin
            fcnt  <= fcnt + 32'd1;
            if (blk_idx == 4'd15 && blk_known && locked) begin
                if (busy) dropped <= 1'b1;
                else begin
                    go     <= 1'b1;
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

    // ------------------------------------------------------------- sender
    reg [5:0] idx;                          // packet byte being sent
    reg [7:0] xsum;
    reg [7:0] cur;
    wire [5:0] ci = idx - 6'd9;             // control byte 0..31 for idx 9..40
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

    // Timing: picking the byte (a subtract, a RAM read and a 42-way choice)
    // was the slowest path in the whole clk_s domain, yet a byte is needed
    // only once per 330 ns. So the chosen byte is registered (cur_q) one clock
    // before it is loaded: `prep` gives idx that clock to settle. The bits then
    // leave through a plain shift register, not a variable bit select.
    reg [7:0] cur_q;
    always @(posedge clk) cur_q <= cur;

    reg [9:0] sh;                           // stop, data[7:0], start; sh[0] is on the line
    reg [3:0] bitpos;                       // bit on the line, 0 = start .. 9 = stop
    reg [7:0] tick;
    reg       prep, load;
    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; txd <= 1'b1; idx <= 6'd0; xsum <= 8'd0; prep <= 1'b0; load <= 1'b0;
            bitpos <= 4'd0; tick <= 8'd0; sh <= 10'h3FF;
        end else if (!busy) begin
            txd <= 1'b1;
            if (go) begin busy <= 1'b1; idx <= 6'd0; xsum <= 8'd0; prep <= 1'b1; end
        end else if (prep) begin
            prep <= 1'b0; load <= 1'b1;     // cur_q catches cur(idx) at this edge
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
            if (idx == 6'd41) busy <= 1'b0;
            else begin idx <= idx + 6'd1; prep <= 1'b1; end
        end else begin
            sh     <= {1'b1, sh[9:1]};
            txd    <= sh[1];
            bitpos <= bitpos + 4'd1;
            tick   <= DIV - 1;
        end
    end
endmodule
