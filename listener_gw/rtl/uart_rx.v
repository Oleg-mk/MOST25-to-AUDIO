// uart_rx.v - 8N1 receiver, the command input from the host MCU.
//
// Same baud as ctrl_uart (clk / DIV). The line is synchronised, a start bit
// is a falling edge while idle, and each bit is taken in its middle. A byte
// whose stop bit is low is dropped (framing error).
module uart_rx #(
    parameter DIV = 33                      // clk / baud: 99 MHz / 3 Mbaud
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       rxd,
    output reg        valid,                // one clock per received byte
    output reg  [7:0] data
);
    reg [2:0] s;                            // synchroniser; idle high
    always @(posedge clk) s <= rst ? 3'b111 : {s[1:0], rxd};
    wire r = s[2];

    reg       busy;
    reg [7:0] tick;
    reg [3:0] bitn;                         // 0 = start, 1..8 = data, 9 = stop
    reg [7:0] sh;
    always @(posedge clk) begin
        valid <= 1'b0;
        if (rst) begin
            busy <= 1'b0; tick <= 8'd0; bitn <= 4'd0; sh <= 8'd0; data <= 8'd0;
        end else if (!busy) begin
            if (!r) begin                   // start edge: wait half a bit
                busy <= 1'b1; bitn <= 4'd0; tick <= DIV / 2;
            end
        end else if (tick != 8'd0) begin
            tick <= tick - 8'd1;
        end else begin
            tick <= DIV - 1;
            if (bitn == 4'd0) begin
                if (r) busy <= 1'b0;        // glitch, not a start bit
            end else if (bitn == 4'd9) begin
                busy <= 1'b0;
                if (r) begin valid <= 1'b1; data <= sh; end
            end else begin
                sh <= {r, sh[7:1]};         // LSB first
            end
            bitn <= bitn + 4'd1;
        end
    end
endmodule
