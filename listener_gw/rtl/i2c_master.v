// i2c_master.v - byte-level I2C master: start, write, read, stop.
//
// One command at a time; `busy` is high while it runs:
//   cmd 0  START   (a repeated start if the bus is already taken)
//   cmd 1  WRITE   byte `wdata`; `nack` = 1 if the slave did not acknowledge
//   cmd 2  READ    one byte into `rdata`; the master acknowledges it unless
//                  `last` is set (NACK before a stop)
//   cmd 3  STOP
// SCL and SDA are open drain: 0 = pull low, 1 = release. Each bit takes four
// quarter periods of QDIV clocks: 62 at 99 MHz gives 399 kHz, inside the
// Si514's fast mode (data sheet Rev 1.2, 5.3). There is no clock stretching:
// the Si514 does not stretch.
module i2c_master #(
    parameter QDIV = 62                     // clk / (4 x SCL rate)
) (
    input  wire       clk,
    input  wire       rst,
    input  wire       go,                   // start `cmd` (ignored while busy)
    input  wire [1:0] cmd,
    input  wire [7:0] wdata,
    input  wire       last,
    output reg        busy,
    output reg  [7:0] rdata,
    output reg        nack,
    output reg        scl_o,
    output reg        sda_o,
    input  wire       sda_i
);
    localparam C_START = 2'd0, C_WRITE = 2'd1, C_READ = 2'd2, C_STOP = 2'd3;
    reg [1:0] c;
    reg [1:0] q;                            // quarter of a bit
    reg [3:0] bi;                           // 8 data bits then the ACK bit
    reg [7:0] qc;
    reg [7:0] sh;
    reg       lst;
    wire      tq = (qc == 8'd0);

    always @(posedge clk) begin
        if (rst) begin
            busy <= 1'b0; rdata <= 8'd0; nack <= 1'b0; scl_o <= 1'b1; sda_o <= 1'b1;
            c <= 2'd0; q <= 2'd0; bi <= 4'd0; qc <= 8'd0; sh <= 8'd0; lst <= 1'b0;
        end else if (!busy) begin
            if (go) begin
                busy <= 1'b1; c <= cmd; q <= 2'd0; bi <= 4'd0; qc <= QDIV[7:0];
                sh <= wdata; lst <= last;
                if (cmd == C_WRITE) nack <= 1'b0;
            end
        end else begin
            qc <= tq ? QDIV[7:0] : qc - 8'd1;
            if (tq) begin
                q <= q + 2'd1;
                case (c)
                C_START: case (q)                 // SDA falls while SCL is high
                    2'd0: sda_o <= 1'b1;          // (from SCL low: release SDA first)
                    2'd1: scl_o <= 1'b1;
                    2'd2: sda_o <= 1'b0;
                    2'd3: begin scl_o <= 1'b0; busy <= 1'b0; end
                endcase
                C_STOP: case (q)                  // SDA rises while SCL is high
                    2'd0: sda_o <= 1'b0;
                    2'd1: scl_o <= 1'b1;
                    2'd2: sda_o <= 1'b1;
                    2'd3: busy <= 1'b0;
                endcase
                default: case (q)                 // WRITE or READ: 8 bits + ACK
                    2'd0: begin
                        if (bi < 4'd8) sda_o <= (c == C_WRITE) ? sh[7] : 1'b1;
                        else           sda_o <= (c == C_WRITE) ? 1'b1 : lst;   // ACK slot
                    end
                    2'd1: scl_o <= 1'b1;
                    2'd2: begin                   // sample in the middle of SCL high
                        if (bi < 4'd8) begin
                            if (c == C_READ) sh <= {sh[6:0], sda_i};
                        end else if (c == C_WRITE) nack <= sda_i;
                    end
                    2'd3: begin
                        scl_o <= 1'b0;
                        if (bi < 4'd8) begin
                            if (c == C_WRITE) sh <= {sh[6:0], 1'b0};
                            bi <= bi + 4'd1;
                        end else begin
                            if (c == C_READ) rdata <= sh;
                            busy <= 1'b0;
                        end
                    end
                endcase
                endcase
            end
        end
    end
endmodule
