// fs_fine.v - the frame-rate square wave, with its edges placed to 1.26 ns.
//
// The clock multiplier locks to this signal, so every error in its edges ends
// up in the regenerated ring clock. Drawn on the 99 MHz clock (as rx_framer's
// fs_sq is), each edge sits up to 10.1 ns late, and the error is a sawtooth
// whose beat with the frame rate falls inside any loop bandwidth for some ring
// offsets: 8-11 ns pp then pass straight through (research report "Такт
// регенератора MOST25 альтернативи Si5319", section on the 99 MHz grid).
//
// Here each edge is placed at the sample time the receiver saw it (rx_framer
// fe_t: UI 0 rising, UI 512 falling), on the same 792 Msps grid the input is
// sampled on, and sent out 8 bits per clock through an output serialiser
// (OSER8 on the Tang Nano, bit 0 first - checked against Gowin's model).
// The output runs D words behind the input: an edge is known only after the
// run that follows it has been measured (the 3-UI preamble run, ~7 words, plus
// the receiver pipeline, 4 clocks), and D must cover that. A constant delay
// does not matter to the clock multiplier.
//
// Lock: a rising edge is only drawn while the framer is locked; losing lock
// pulls the output low at once.
module fs_fine #(
    parameter D = 20                        // output delay, words (158 samples)
) (
    input  wire        clk,
    input  wire        rst,
    input  wire [28:0] wc,                  // word counter, same time base as the receiver
    input  wire        locked,
    input  wire        fe_valid,
    input  wire        fe_rise,
    input  wire [31:0] fe_t,
    output reg  [7:0]  word,                // bit 0 = earliest
    output reg         late                 // sticky: an edge arrived after its slot
);
    // Timing: the word drawn in a clock covers samples from base = (wc - D) x 8.
    // Rather than subtract base from the edge time every clock (two 32-bit
    // subtracts in a row: the slowest path of clk_s), the edge's distance
    // from the NEXT word's base is taken once, when the edge arrives, and then
    // counted down by 8 per word. nb holds that next base, a clock ahead.
    reg        pend, prise, lvl;
    reg [31:0] dd;                                 // pending edge time - this word's base
    reg [31:0] nb;                                 // base of the next word
    always @(posedge clk) nb <= {wc - (D[28:0] - 29'd2), 3'b000};
    wire       here = pend && dd[31:3] == 29'd0;   // 0 <= dd < 8: the edge is in this word
    wire       past = pend && dd[31];              // already behind the output

    integer i;
    always @(posedge clk) begin
        if (rst) begin
            pend <= 1'b0; prise <= 1'b0; lvl <= 1'b0; dd <= 32'd0;
            word <= 8'd0; late <= 1'b0;
        end else if (!locked) begin
            pend <= 1'b0; lvl <= 1'b0; word <= 8'd0;
        end else begin
            // this word: the level so far, switching at the edge if it falls here
            for (i = 0; i < 8; i = i + 1)
                word[i] <= (here && i >= dd[2:0]) ? prise : lvl;
            dd <= dd - 32'd8;
            if (here) begin
                lvl <= prise; pend <= 1'b0;
            end else if (past) begin
                lvl <= prise; pend <= 1'b0; late <= 1'b1;   // must not happen: D too small
            end
            // a new edge (they come ~10 us apart, so never while one is pending)
            if (fe_valid) begin
                pend <= 1'b1; prise <= fe_rise; dd <= fe_t - nb;
            end
        end
    end
endmodule
