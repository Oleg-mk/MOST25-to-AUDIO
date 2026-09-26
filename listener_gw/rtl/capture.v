// capture.v - the line as it came: run lengths from the sampler into a buffer,
// out over the UART on request.
//
// Everything the simulations could only assume about a MOST25 line - the
// preamble's run pattern, which preamble marks a block, the parity rule, the
// frame control bits - is read off one recording of a real ring. This block
// makes that recording: every run rx_runlen measures on RX_IN (its length in
// samples of 1.26 ns, saturating at 255, and the glitch flag of the word that
// ended the run before it) goes into a buffer of 2^AW runs, 65536 by default:
// 32 BSRAM blocks, about 85 frames or 5 control blocks at 48 kHz.
//
// Capturing starts at power-up on its own, so the first runs the line ever
// carries - the ring's start-up - are kept until the host asks for them. The
// host can capture anew at any time (arm), with or without a dump as soon as
// the buffer is full (auto), and dump what has been captured (dump), the
// whole buffer or what is there. A dump goes out as packets of 32 runs on the
// UART, in the gaps between the control-block packets (ctrl_uart.v
// arbitrates, control first, so no block is lost to a dump), 2048 packets in
// about 0.7 s, then one trailer:
//
//   0  A5  1  C5      sync (C5, not the control packets' 5A)
//   2..3              packet number n, little endian: runs 32 n .. 32 n + 31
//   4..35             the 32 run lengths, in order
//   36..39            their glitch flags, bit i of byte 36 + i / 8 for run i
//   40                XOR of bytes 0..39 (appended by the sender)
//   trailer: packet number FFFF, bytes 4..7 the number of runs captured
//            (little endian), bytes 8..39 zero
//
// The level is not stored: runs alternate, so it follows from the first one,
// except across a glitch, which the flag marks.
module capture #(
    parameter AW = 16                       // 2^AW runs; 16 = 32 BSRAM blocks
) (
    input  wire         clk,
    input  wire         rst,
    input  wire         run_valid,          // rx_runlen, RX_IN
    input  wire [7:0]   run_len,
    input  wire         glitch,
    input  wire         arm,                // pulse: capture anew from the next run
    input  wire         auto_dump,          // with arm: dump as soon as the buffer is full
    input  wire         dump,               // pulse: send what has been captured (capturing stops)
    output reg          req,                // a packet is ready in pkt, until taken
    input  wire         take,               // pulse: the sender starts sending pkt
    input  wire         done,               // pulse: the sender has sent it
    output reg  [319:0] pkt,                // bytes 0..39, byte i in [8i +: 8]
    output wire         busy                // capturing (not full) or dumping
);
    reg  [8:0]    mem [0:(1<<AW)-1];        // {glitch, length}
    reg  [AW:0]   wptr;                     // runs captured; wptr[AW] = full
    reg           capturing, auto_q;
    reg  [8:0]    q, q2;
    reg  [5:0]    ld2;
    reg  [AW-1:0] raddr;
    always @(posedge clk) q <= mem[raddr];   // BSRAM: registered read

    localparam [2:0] S_IDLE = 3'd0, S_LOAD = 3'd1, S_READY = 3'd2, S_SEND = 3'd3,
                     S_TRAIL = 3'd4, S_TSEND = 3'd5;
    reg  [2:0]    st;
    reg  [AW-5:0] rpkt, npkt;               // packet being loaded / sent; packets to send
    reg  [5:0]    ld;                       // loading: 0 header, then the runs' data (q2 with ld2 = 1..32)
    always @(posedge clk) begin q2 <= q; ld2 <= ld; end   // the read once more, before the 40-way write into pkt
    wire          full  = wptr[AW];
    wire          go_dump = (dump || (auto_q && full && capturing)) && st == S_IDLE;
    assign busy = (capturing && !full) || st != S_IDLE;

    // ---------------------------------------------------------------- write
    always @(posedge clk) begin
        if (rst) begin
            capturing <= 1'b1; wptr <= 0; auto_q <= 1'b0;   // the ring's start-up, from the first run
        end else if (arm && st == S_IDLE) begin
            capturing <= 1'b1; wptr <= 0; auto_q <= auto_dump;
        end else if (go_dump) begin
            capturing <= 1'b0; auto_q <= 1'b0;
        end else if (capturing && run_valid && !full) begin
            mem[wptr[AW-1:0]] <= {glitch, run_len};
            wptr <= wptr + 1'b1;
        end
    end

    // ----------------------------------------------------------- read, dump
    integer i;
    always @(posedge clk) begin
        if (rst) begin
            st <= S_IDLE; req <= 1'b0; rpkt <= 0; npkt <= 0; ld <= 6'd0; raddr <= 0; pkt <= 320'd0;
        end else begin
            case (st)
            S_IDLE: if (go_dump) begin
                npkt  <= (wptr + 31) >> 5;               // ceil(runs / 32)
                rpkt  <= 0;
                raddr <= 0;
                ld    <= 6'd0;
                st    <= (wptr != 0) ? S_LOAD : S_TRAIL;
            end
            S_LOAD: begin
                // address k is presented at ld = k (k = 0 already before); its data is
                // in q with ld = k + 1 and in q2 with ld2 = k + 1, a clock later
                if (ld <= 6'd31) raddr <= {rpkt, ld[4:0]} + 1'b1;
                if (ld == 6'd0) begin
                    pkt[7:0] <= 8'hA5; pkt[15:8] <= 8'hC5;
                    pkt[31:16] <= {{(16 - (AW - 4)){1'b0}}, rpkt};
                    for (i = 36; i < 40; i = i + 1) pkt[8 * i +: 8] <= 8'd0;
                end
                if (ld2 >= 6'd1 && ld2 <= 6'd32) begin
                    pkt[8 * (ld2 + 3) +: 8] <= q2[7:0];  // byte 4 + (ld2 - 1)
                    pkt[8 * 36 + (ld2 - 1)] <= q2[8];    // glitch bit ld2 - 1
                end
                if (ld2 == 6'd32) begin req <= 1'b1; st <= S_READY; end
                if (ld != 6'd33) ld <= ld + 6'd1;
            end
            S_READY: if (take) begin req <= 1'b0; st <= S_SEND; end
            S_SEND: if (done) begin
                if (rpkt + 1'b1 == npkt) st <= S_TRAIL;
                else begin
                    rpkt <= rpkt + 1'b1; ld <= 6'd0; raddr <= {rpkt + 1'b1, 5'd0}; st <= S_LOAD;
                end
            end
            S_TRAIL: begin                               // the trailer: how many runs there were
                pkt <= 320'd0;
                pkt[7:0] <= 8'hA5; pkt[15:8] <= 8'hC5; pkt[31:16] <= 16'hFFFF;
                pkt[63:32] <= {{(32 - (AW + 1)){1'b0}}, wptr};
                req <= 1'b1; st <= S_TSEND;
            end
            S_TSEND: begin
                if (take) req <= 1'b0;
                if (done && !req) st <= S_IDLE;
            end
            default: st <= S_IDLE;
            endcase
        end
    end
endmodule
