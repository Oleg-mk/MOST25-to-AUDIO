// host_cmd.v - command packets from the host MCU (UART_RX), all 11 bytes:
//
//   A5 5A  C  P0 P1 P2 P3 P4 P5 P6  X
//     C       command: 01 = where a source is in the frame (amp_out)
//                      02 = audio in positions   (inject)
//                      03 = a coefficient word for J3 (amp_out)
//     P0..P6  parameters, meaning per command
//     X       XOR of the 10 bytes before it; a packet with a wrong X is dropped
//
// A good packet gives one `ok` pulse with `cmd` and `p` held until the next
// good packet. Each user checks its own command and parameters.
module host_cmd (
    input  wire        clk,
    input  wire        rst,
    input  wire        rx_valid,
    input  wire [7:0]  rx_data,
    output reg         ok,
    output reg  [7:0]  cmd,
    output reg  [55:0] p                    // {P0, P1, .. P6}, P0 in the top byte
);
    reg [3:0]  n;                           // bytes of the packet so far
    reg [7:0]  x;
    reg [7:0]  c;
    reg [55:0] sh;
    always @(posedge clk) begin
        ok <= 1'b0;
        if (rst) begin
            n <= 4'd0; x <= 8'd0; c <= 8'd0; sh <= 56'd0; cmd <= 8'd0; p <= 56'd0;
        end else if (rx_valid) begin
            x <= x ^ rx_data;
            n <= n + 4'd1;
            if (n == 4'd2) c <= rx_data;
            if (n >= 4'd3 && n <= 4'd9) sh <= {sh[47:0], rx_data};
            if ((n == 4'd0 && rx_data != 8'hA5) || (n == 4'd1 && rx_data != 8'h5A)) begin
                // resynchronise: an A5 here may start the next packet
                n <= (rx_data == 8'hA5) ? 4'd1 : 4'd0;
                x <= (rx_data == 8'hA5) ? 8'hA5 : 8'd0;
            end else if (n == 4'd10) begin
                n <= 4'd0; x <= 8'd0;
                if ((x ^ rx_data) == 8'd0) begin
                    ok <= 1'b1; cmd <= c; p <= sh;
                end
            end
        end
    end
endmodule
