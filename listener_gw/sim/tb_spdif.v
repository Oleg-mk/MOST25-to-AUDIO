// tb_spdif.v - spdif_tx alone: a frame counter like tdm_out's, a known pair per
// frame; the line is logged half-cell by half-cell (one line per frame) and
// the pairs as truth, for spdif_dec.py (run_spdif.py).
`timescale 1ns / 1ps
module tb_spdif;
    parameter RATE48 = 1;
    parameter NFR = 600;

    reg clk = 1'b0;
    always #10 clk = ~clk;
    reg         run = 1'b0;
    reg  [9:0]  n = 10'd0;                          // the counter; phase_n = the value it takes next
    wire [9:0]  phase_n = n + 10'd1;
    reg  [47:0] lr = 48'd0;
    wire        out;
    always @(posedge clk) if (run) n <= n + 10'd1;

    spdif_tx dut (.clk(clk), .run(run), .phase_n(phase_n), .lr(lr), .rate48(RATE48[0]), .out(out));

    // the pair of frame f: extremes now and then, otherwise patterns that change every frame
    function [47:0] pair(input integer f);
        reg [23:0] l, r;
        begin
            case (f % 7)
                0: begin l = 24'h7FFFFF; r = 24'h800000; end
                1: begin l = 24'h000000; r = 24'hFFFFFF; end
                2: begin l = 24'h000001; r = 24'h800001; end
                default: begin l = {8'h5A, f[15:0]} ^ {f[7:0], 16'h0000}; r = ~{8'hC3, f[15:0]}; end
            endcase
            pair = {l, r};
        end
    endfunction

    integer fo, ft, f = 0;
    reg t; reg [6:0] hh;
    // the level after each tick = the half-cell's level (tick and h read before the edge)
    always @(posedge clk) begin
        t = dut.tick; hh = dut.h;
        #1;
        if (t) begin
            if (hh == 7'd0) $fwrite(fo, "\n");
            $fwrite(fo, "%0d", out);
        end
    end
    // the DUT latches lr at the edge where phase_n == 0, i.e. n == 1023 before it
    always @(negedge clk) begin
        if (run && n == 10'd1023) begin
            lr = pair(f);
            $fwrite(ft, "%0d %06x %06x\n", f, lr[47:24], lr[23:0]);
            f = f + 1;
        end
    end

    initial begin
        fo = $fopen("out_spdif.txt", "w"); ft = $fopen("out_truth.txt", "w");
        repeat (5) @(posedge clk);
        n = 10'd1000;                               // the first frame starts soon after run
        @(negedge clk) run = 1'b1;
        while (f < NFR + 1) @(posedge clk);
        repeat (1100) @(posedge clk);
        $fclose(fo); $fclose(ft);
        $finish;
    end
endmodule
