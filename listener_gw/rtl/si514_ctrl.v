// si514_ctrl.v - the two Si514 operations the clock loop needs, over I2C.
//
// Data sheet: Skyworks Si514 Rev 1.2 (Aug 2021).
//   Fout = FXO x M / (HS_DIV x LS_DIV), FXO = 31.98 MHz; M = M_Int.M_Frac,
//   29 fractional bits; here M is carried as mfix = M x 2^29 (38 bits), whose
//   bytes land exactly on registers 5..9: 5 = [7:0], 6 = [15:8], 7 = [23:16],
//   8 = {M_Int[2:0], M_Frac[28:24]} = [31:24], 9 = M_Int[8:3] = [37:32].
//
// centre  a "large frequency change" (3.3): output off (reg 132 bit 2 = 0),
//         LP1/LP2 (reg 0), M (regs 5..9, 9 last - the change takes effect
//         when M_Int[8:3] is written), HS_DIV/LS_DIV (regs 10, 11), FCAL
//         (reg 132 bit 0), wait for the calibration (10 ms max, FCAL_WAIT
//         here), output on. Reg 132 has reserved bits, so it is changed by
//         read-modify-write; FCAL clears itself.
// update  a "small frequency change" (3.2): regs 5..9 in one burst; glitch-free
//         within +/-1000 ppm of the centre, settled within 100 us.
//
// LP1/LP2 = 2/3 (0x23) holds for M from 65.26 to 67.86 (Table 13); the two
// centres here, 67.626 (49.152 MHz, HS_DIV 44) and 67.780 (45.1584 MHz,
// HS_DIV 48), stay inside it even at +/-1150 ppm. LS_DIV = 1.
//
// Address. A part bought off the shelf answers at whatever 7-bit address its
// factory code gave it, so the address is found, not configured: before the
// first centring every valid address, 0x08..0x77, is probed with an empty
// write (START, address + W, STOP) until one is acknowledged. The bus is the
// Si514's alone, so that is the Si514. No answer anywhere is a NACK error like
// any other; the loop backs off and the next centring scans again.
module si514_ctrl #(
    parameter        QDIV      = 62,        // I2C: 99 MHz / (4 x 62+1) = 393 kHz
    parameter [23:0] FCAL_WAIT = 24'd1188000 // 12 ms at 99 MHz (10 ms max + margin)
) (
    input  wire        clk,
    input  wire        rst,
    input  wire        do_centre,           // pulse: large change to mfix / hs
    input  wire        do_update,           // pulse: small change to mfix
    input  wire [37:0] mfix,
    input  wire [9:0]  hs,
    output reg         busy,                // an operation is running
    output reg         out_off,             // output disabled (centring): clk_r may stop
    output reg         nack_err,            // the last operation got a NACK (clears as the next starts)
    output wire        scl_o,
    output wire        sda_o,
    input  wire        sda_i
);
    // ------------------------------------------------ byte engine
    reg        go, lst;
    reg  [1:0] cmd;
    reg  [7:0] wd;
    wire       ib;
    wire [7:0] rd;
    wire       nk;
    i2c_master #(.QDIV(QDIV)) u_m (.clk(clk), .rst(rst), .go(go), .cmd(cmd), .wdata(wd),
                                   .last(lst), .busy(ib), .rdata(rd), .nack(nk),
                                   .scl_o(scl_o), .sda_o(sda_o), .sda_i(sda_i));

    // ------------------------------------------------ transactions
    // T_WR: S, addr+W, reg, data[0..n-1], P      T_RD: S, addr+W, reg, Sr, addr+R, read, P
    reg        t_run, t_read;
    reg  [7:0] t_reg;
    reg  [2:0] t_n;                          // data bytes to write
    reg  [7:0] t_d [0:4];
    reg  [3:0] t_st;
    reg  [2:0] t_i;
    reg        wait_b, seen_b;               // waiting for the engine: seen it busy?
    reg  [7:0] t_rd;
    reg        t_probe, p_nak;               // address probe; it was not acknowledged
    reg  [6:0] addr, sa;                     // the Si514's address; the one being probed
    reg        have_addr;
    wire [6:0] ta = t_probe ? sa : addr;

    localparam X_S = 4'd0, X_A = 4'd1, X_R = 4'd2, X_D = 4'd3, X_S2 = 4'd4, X_A2 = 4'd5,
               X_RD = 4'd6, X_P = 4'd7, X_END = 4'd8;

    task issue(input [1:0] c, input [7:0] b, input l);
        begin go <= 1'b1; cmd <= c; wd <= b; lst <= l; wait_b <= 1'b1; seen_b <= 1'b0; end
    endtask

    // ------------------------------------------------ operation sequencer
    localparam P_IDLE = 5'd0,
               // centre
               P_C_RD1 = 5'd1, P_C_OFF = 5'd2, P_C_LP = 5'd3, P_C_M = 5'd4, P_C_HS = 5'd5,
               P_C_RD2 = 5'd6, P_C_CAL = 5'd7, P_C_WAIT = 5'd8, P_C_RD3 = 5'd9, P_C_ON = 5'd10,
               // address scan
               P_SCAN = 5'd11, P_SCHK = 5'd12,
               // update
               P_U_M = 5'd16;
    reg  [4:0]  p;
    reg         p_issued;                   // the current step's transaction has started
    reg  [23:0] wt;
    reg  [37:0] m_l;
    reg  [9:0]  hs_l;

    task start_t(input rdop, input [7:0] r, input [2:0] n);
        begin t_run <= 1'b1; t_read <= rdop; t_reg <= r; t_n <= n; t_st <= X_S; t_i <= 3'd0; end
    endtask

    integer k;
    always @(posedge clk) begin
        go <= 1'b0;
        if (rst) begin
            busy <= 1'b0; out_off <= 1'b0; nack_err <= 1'b0;
            t_run <= 1'b0; t_read <= 1'b0; t_reg <= 8'd0; t_n <= 3'd0; t_st <= X_S; t_i <= 3'd0;
            wait_b <= 1'b0; seen_b <= 1'b0; t_rd <= 8'd0; cmd <= 2'd0; wd <= 8'd0; lst <= 1'b0;
            p <= P_IDLE; p_issued <= 1'b0; wt <= 24'd0; m_l <= 38'd0; hs_l <= 10'd0;
            t_probe <= 1'b0; p_nak <= 1'b0; addr <= 7'd0; sa <= 7'h08; have_addr <= 1'b0;
            for (k = 0; k < 5; k = k + 1) t_d[k] <= 8'd0;
        end else if (wait_b) begin
            // one engine command in flight
            if (ib) seen_b <= 1'b1;
            else if (seen_b) begin
                wait_b <= 1'b0;
                if (cmd == 2'd1 && nk) begin            // no ACK: stop and give up
                    if (t_probe) p_nak <= 1'b1;         // (a probe: just not this address)
                    else nack_err <= 1'b1;
                    t_st <= X_P; t_read <= 1'b0;
                end
                if (cmd == 2'd2) t_rd <= rd;
            end
        end else if (t_run) begin
            case (t_st)
            X_S:  begin issue(2'd0, 8'd0, 1'b0); t_st <= X_A; end
            X_A:  begin issue(2'd1, {ta, 1'b0}, 1'b0); t_st <= t_probe ? X_P : X_R; end
            X_R:  begin issue(2'd1, t_reg, 1'b0); t_st <= t_read ? X_S2 : (t_n != 0 ? X_D : X_P); end
            X_D:  begin
                      issue(2'd1, t_d[t_i], 1'b0);
                      t_i <= t_i + 3'd1;
                      if (t_i + 3'd1 == t_n) t_st <= X_P;
                  end
            X_S2: begin issue(2'd0, 8'd0, 1'b0); t_st <= X_A2; end
            X_A2: begin issue(2'd1, {ta, 1'b1}, 1'b0); t_st <= X_RD; end
            X_RD: begin issue(2'd2, 8'd0, 1'b1); t_st <= X_P; end
            X_P:  begin issue(2'd3, 8'd0, 1'b0); t_st <= X_END; end
            default: t_run <= 1'b0;                     // X_END: transaction complete
            endcase
        end else begin
            // between transactions: next step of the operation
            case (p)
            P_IDLE: begin
                busy <= 1'b0; out_off <= 1'b0;          // released only once OE is written
                // nack_err belongs to the operation that got it: each new one
                // starts clean, so a one-off glitch costs one update (and LOCK
                // for HOLD_RE), not the rest of the drive
                if (do_centre) begin
                    busy <= 1'b1; m_l <= mfix; hs_l <= hs; nack_err <= 1'b0;
                    if (have_addr) p <= P_C_RD1;
                    else begin sa <= 7'h08; p <= P_SCAN; end
                end else if (do_update) begin
                    busy <= 1'b1; m_l <= mfix; nack_err <= 1'b0; p <= P_U_M;
                end
            end
            // find the Si514: probe sa, take the first address that answers
            P_SCAN: begin p_nak <= 1'b0; t_probe <= 1'b1; start_t(1'b0, 8'd0, 3'd0); p <= P_SCHK; end
            P_SCHK: begin
                t_probe <= 1'b0;
                if (!p_nak) begin addr <= sa; have_addr <= 1'b1; p <= P_C_RD1; end
                else if (sa == 7'h77) begin nack_err <= 1'b1; p <= P_IDLE; end   // nobody there
                else begin sa <= sa + 7'd1; p <= P_SCAN; end
            end
            P_C_RD1: begin start_t(1'b1, 8'd132, 3'd0); p <= P_C_OFF; end
            P_C_OFF: begin
                out_off <= 1'b1;
                t_d[0] <= t_rd & 8'b1111_1010;           // OE = 0, FCAL = 0
                start_t(1'b0, 8'd132, 3'd1); p <= P_C_LP;
            end
            P_C_LP: begin t_d[0] <= 8'h23; start_t(1'b0, 8'd0, 3'd1); p <= P_C_M; end
            P_C_M: begin
                t_d[0] <= m_l[7:0]; t_d[1] <= m_l[15:8]; t_d[2] <= m_l[23:16];
                t_d[3] <= m_l[31:24]; t_d[4] <= {2'b00, m_l[37:32]};
                start_t(1'b0, 8'd5, 3'd5); p <= P_C_HS;
            end
            P_C_HS: begin
                t_d[0] <= hs_l[7:0]; t_d[1] <= {1'b0, 3'b000, 2'b00, hs_l[9:8]};   // LS_DIV = 1
                start_t(1'b0, 8'd10, 3'd2); p <= P_C_RD2;
            end
            P_C_RD2: begin start_t(1'b1, 8'd132, 3'd0); p <= P_C_CAL; end
            P_C_CAL: begin
                t_d[0] <= (t_rd & 8'b1111_1010) | 8'h01;  // FCAL, output still off
                start_t(1'b0, 8'd132, 3'd1); p <= P_C_WAIT; wt <= FCAL_WAIT;
            end
            P_C_WAIT: if (wt != 0) wt <= wt - 24'd1; else p <= P_C_RD3;
            P_C_RD3: begin start_t(1'b1, 8'd132, 3'd0); p <= P_C_ON; end
            P_C_ON: begin
                t_d[0] <= (t_rd & 8'b1111_1110) | 8'h04;  // OE = 1
                start_t(1'b0, 8'd132, 3'd1); p <= P_IDLE;
            end
            P_U_M: begin
                t_d[0] <= m_l[7:0]; t_d[1] <= m_l[15:8]; t_d[2] <= m_l[23:16];
                t_d[3] <= m_l[31:24]; t_d[4] <= {2'b00, m_l[37:32]};
                start_t(1'b0, 8'd5, 3'd5); p <= P_IDLE;
            end
            default: p <= P_IDLE;
            endcase
        end
    end
endmodule
