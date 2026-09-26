// tdm_out.v - one MOST frame out as one TDM frame, on two TDM8 lines.
//
// Frames arrive byte by byte in the sample domain (clk_s) into one of two
// 64-byte banks. When a frame completes, its bank number is held and a toggle
// crosses into the ring domain.
//
// The frame goes out as it left the listener: where our own audio replaced
// bytes on the ring (inject.v), the same bytes replace them here, from the set
// the injector hands over for the frame just ended (sub_*), taken when the
// frame counter wraps.
//
// Ring domain clk_r = 1024 Fs. BCLK = clk_r / 4 = 256 Fs, so a TDM frame of
// 8 slots x 32 bit lasts exactly one MOST frame:
//   SD0 = frame bytes 0..31, SD1 = frame bytes 32..63, MSB first, byte 0 first
//   FS  = high during the first BCLK of the frame (short frame sync)
//   data changes on the falling BCLK edge, is sampled on the rising one.
//
// Phase. The TDM frame starts 128 clk_r after a MOST frame completes and reads
// that frame's bank for the next 1024 clk_r. The writer refills the same bank
// only after the NEXT frame completes (1024 later) and reaches byte k about
// 16*k UI after that, while the reader passed byte k (on SD0) at 128 + 32*k -
// so the reader always stays ahead. clk_r is locked to the ring, so this phase
// only wanders; `valid` drops if a completion ever lands far from where the
// first one set it.
module tdm_out (
    input  wire       clk_s,
    input  wire       rst_s,
    input  wire       byte_we,
    input  wire [5:0] byte_addr,
    input  wire [7:0] byte_data,
    input  wire       frame_done,
    input  wire       enable,            // clk_s: receiver locked
    input  wire       clk_r,
    input  wire       rst_r,
    input  wire       sub_on,             // inject.v prev_*: the frame just ended was injected...
    input  wire       sub_w3,             // ...24 bit
    input  wire [35:0] sub_pos,           // ...into these bytes
    input  wire [47:0] sub_val,           // ...with these
    output reg        bclk,
    output reg        fs,
    output reg        sd0,
    output reg        sd1,
    output reg        valid,             // clk_r: output carries live frames
    output wire [9:0] phase_n            // clk_r: frame counter, the value it takes next
);
    localparam [9:0] START = 10'd896;          // 1024 - 128

    // ------------------------------------------------ write side (clk_s)
    reg [7:0] ram [0:127];               // {bank, byte}
    reg       wbank, done_bank, done_tgl;
    always @(posedge clk_s) begin
        if (rst_s) begin
            wbank <= 1'b0; done_bank <= 1'b0; done_tgl <= 1'b0;
        end else begin
            if (byte_we) ram[{wbank, byte_addr}] <= byte_data;
            if (frame_done) begin
                done_bank <= wbank;
                wbank     <= ~wbank;
                done_tgl  <= ~done_tgl;
            end
        end
    end

    // ------------------------------------------------- read side (clk_r)
    reg [2:0] t;
    reg [1:0] e;
    always @(posedge clk_r) begin
        t <= {t[1:0], done_tgl};
        e <= {e[0], enable};
    end
    wire new_frame = t[2] ^ t[1];        // done_bank is stable for ~1000 clk_r now

    reg [9:0] cnt;
    reg       synced, rbank, have;
    wire [9:0] n  = cnt + 10'd1;          // value cnt takes next: outputs follow it
    assign phase_n = n;                   // amp_out runs off the same count
    wire [7:0] b  = n[9:2];               // TDM bit index in the frame, 0..255
    wire       rb = (n == 10'd0) ? done_bank : rbank;   // bit 0 already reads the new bank
    wire [7:0] y0 = ram[{rb, 1'b0, b[7:3]}];
    wire [7:0] y1 = ram[{rb, 1'b1, b[7:3]}];
    wire [2:0] bi = 3'd7 - b[2:0];

    // the injected bytes of this frame, in place of the ring's
    reg        s_on, s_w3;
    reg [35:0] s_pos;
    reg [47:0] s_val;
    reg        h0, h1;
    reg [7:0]  v0, v1;
    integer    k;
    always @* begin
        h0 = 1'b0; h1 = 1'b0; v0 = 8'd0; v1 = 8'd0;
        for (k = 0; k < 6; k = k + 1)
            if (s_on && (s_w3 || (k != 2 && k != 5))) begin
                if (s_pos[6 * k +: 6] == {1'b0, b[7:3]}) begin h0 = 1'b1; v0 = s_val[8 * k +: 8]; end
                if (s_pos[6 * k +: 6] == {1'b1, b[7:3]}) begin h1 = 1'b1; v1 = s_val[8 * k +: 8]; end
            end
    end

    always @(posedge clk_r) begin
        if (rst_r || !e[1]) begin
            cnt <= 10'd0; synced <= 1'b0; rbank <= 1'b0; have <= 1'b0; valid <= 1'b0;
            bclk <= 1'b0; fs <= 1'b0; sd0 <= 1'b0; sd1 <= 1'b0;
            s_on <= 1'b0; s_w3 <= 1'b0; s_pos <= 36'd0; s_val <= 48'd0;
        end else begin
            if (new_frame) begin
                have <= 1'b1;
                if (!synced) begin
                    cnt <= START; synced <= 1'b1;
                end else begin
                    cnt <= n;
                    // completions must keep arriving near START; else resync
                    if (cnt < START - 10'd300 || cnt > START + 10'd100) begin
                        synced <= 1'b0; valid <= 1'b0;
                    end
                end
            end else begin
                cnt <= n;
            end
            if (n == 10'd0) begin
                rbank <= done_bank;
                valid <= have & synced;
                s_on <= sub_on; s_w3 <= sub_w3; s_pos <= sub_pos; s_val <= sub_val;
            end
            bclk <= n[1];
            fs   <= (b == 8'd0);
            sd0  <= h0 ? v0[bi] : y0[bi];
            sd1  <= h1 ? v1[bi] : y1[bi];
        end
    end
endmodule
