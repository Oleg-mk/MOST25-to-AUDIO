// si514_model.v - behavioural Si514 for simulation (data sheet Rev 1.2).
//
// I2C slave at ADDR with a register file: burst writes and reads with auto
// increment; ACKs every byte addressed to it. The master finds ADDR by
// probing: address bytes for other addresses before the first one for ADDR
// are counted in `n_probe`; after it, any other address - or any data byte
// sent after an address nobody acknowledged - counts in `n_nack` (an error).
// Between GLITCH_FROM_NS and GLITCH_TO_NS the part ignores even its own
// address (a disturbed bus): those refusals count in `n_glitch`, not as errors.
// Frequency behaviour:
//   * Fout = FXO (1 + DSI_PPM) x M / HS_DIV (LS_DIV = 1 here), M = regs 5..9
//   * writing reg 9 applies a new M after SETTLE_NS ("small change"); a change
//     made with the output on that lands more than 1000 ppm from the
//     calibrated centre is counted in `bad_small`
//   * reg 132 bit 0 (FCAL) recalibrates: the output is squelched for FCAL_NS,
//     then the centre becomes the new M / HS_DIV
//   * reg 132 bit 2 (OE) switches the output; while off `freq` = 0
// Reg 132 starts as 0x84: bit 7 is a reserved bit set to 1 on purpose, so a
// write that does not preserve it (no read-modify-write) is counted in
// `bad_rmw`. Everything is observable hierarchically (freq, fcentre, counters).
// START_HZ is the frequency the part runs at from power-up, as the factory
// set it (any 3.3 V CMOS Si514 off the shelf, 100 kHz to 250 MHz); the
// registers' start-up content is not modelled beyond the 49.152 MHz defaults
// - the first large change overwrites all of it.
`timescale 1ns/1ps
module si514_model #(
    parameter [6:0] ADDR      = 7'h55,
    parameter real  FXO       = 31.98e6,
    parameter real  DSI_PPM   = 0.0,
    parameter real  SETTLE_NS = 100000.0,
    parameter real  FCAL_NS   = 10000000.0,
    parameter real  START_HZ  = 49.152e6,
    parameter real  GLITCH_FROM_NS = -1.0,
    parameter real  GLITCH_TO_NS   = -1.0
) (
    input  wire scl,
    input  wire sda,                        // the bus as the master drives it
    output reg  sda_low                     // 1 = this slave pulls SDA low
);
    reg  [7:0] regs [0:255];
    real freq, fcentre, m_now;
    integer n_small, n_fcal, bad_small, bad_rmw, n_nack, n_probe, n_glitch;
    reg  oe, cal_busy, seen_ours;
    integer i;

    function real mval;
        input dummy;
        begin
            mval = {regs[9][5:0], regs[8][7:5]} + ({regs[8][4:0], regs[7], regs[6], regs[5]} / 536870912.0);
        end
    endfunction
    function real hsval;
        input dummy;
        begin hsval = {regs[11][1:0], regs[10]}; end
    endfunction

    initial begin
        for (i = 0; i < 256; i = i + 1) regs[i] = 8'h00;
        regs[132] = 8'h84;
        // start-up: 49.152 MHz (HS_DIV 44, M 67.6263), calibrated there
        regs[0] = 8'h23; regs[5] = 8'hDE; regs[6] = 8'h5F; regs[7] = 8'h0A; regs[8] = 8'h74;
        regs[9] = 8'h08; regs[10] = 8'd44; regs[11] = 8'h00;
        m_now = mval(0);
        freq = FXO * (1.0 + DSI_PPM * 1e-6) * m_now / hsval(0);
        if (START_HZ > 0.0) freq = START_HZ;                      // the factory start-up frequency
        fcentre = freq; oe = 1'b1; cal_busy = 1'b0;
        n_small = 0; n_fcal = 0; bad_small = 0; bad_rmw = 0; n_nack = 0; n_probe = 0; n_glitch = 0;
        seen_ours = 1'b0; sda_low = 1'b0;
    end

    // --------------------------------------------------- frequency behaviour
    task apply_m;
        real f;
        begin
            m_now = mval(0);
            f = FXO * (1.0 + DSI_PPM * 1e-6) * m_now / hsval(0);
            // a small change is one made with the output on; M written with the
            // output off belongs to a large change (followed by FCAL)
            if (oe && (f / fcentre - 1.0 > 1000e-6 || f / fcentre - 1.0 < -1000e-6))
                bad_small = bad_small + 1;
            if (oe && !cal_busy) freq = f;
        end
    endtask

    task write_reg(input [7:0] a, input [7:0] v);
        begin
            if (a == 8'd132 && regs[132][7] && !v[7]) bad_rmw = bad_rmw + 1;
            regs[a] = v;
            if (a == 8'd9) begin
                n_small = n_small + 1;
                fork : settle
                    #(SETTLE_NS) apply_m;
                join_none
            end
            if (a == 8'd132) begin
                oe = v[2];
                if (!oe) freq = 0.0;
                if (v[0]) begin
                    n_fcal = n_fcal + 1; cal_busy = 1'b1; freq = 0.0;
                    regs[132][0] = 1'b0;                        // self-clearing
                    fork : cal
                        begin
                            #(FCAL_NS);
                            m_now = mval(0);
                            fcentre = FXO * (1.0 + DSI_PPM * 1e-6) * m_now / hsval(0);
                            cal_busy = 1'b0;
                            if (oe) freq = fcentre;
                        end
                    join_none
                end else if (oe && !cal_busy) begin
                    freq = FXO * (1.0 + DSI_PPM * 1e-6) * m_now / hsval(0);
                end
            end
        end
    endtask

    // --------------------------------------------------- I2C slave
    // bitc counts SCL falling edges in a byte: data on 0..7, ACK clock at 8.
    // A START is followed by SCL's own fall, which is not a data bit: -1.
    // sending = this slave drives data bytes (read transfer after its address).
    integer    bitc;
    reg  [7:0] sh, ptr;
    reg        active, addressed, rd, sending, mack;
    integer    nbyte;
    always @(negedge sda) if (scl) begin                   // START / repeated START
        bitc = -1; active = 1'b1; addressed = 1'b0; rd = 1'b0; sending = 1'b0;
        nbyte = 0; sda_low = 1'b0;
    end
    always @(posedge sda) if (scl) begin                   // STOP
        active = 1'b0; sending = 1'b0; sda_low = 1'b0;
    end
    always @(posedge scl) if (active && bitc >= 0) begin
        if (bitc < 8) begin
            if (!sending) sh = {sh[6:0], sda};
        end else if (sending) mack = !sda;                  // master's ACK on our byte
    end
    always @(negedge scl) if (active) begin
        if (bitc < 0) bitc = 0;                             // the START's own fall
        else if (bitc < 8) begin
            bitc = bitc + 1;
            if (!sending) begin
                if (bitc == 8) begin                        // a byte from the master
                    if (nbyte == 0) begin
                        addressed = (sh[7:1] == ADDR);
                        rd = sh[0];
                        if (addressed && $realtime >= GLITCH_FROM_NS && $realtime < GLITCH_TO_NS) begin
                            addressed = 1'b0; n_glitch = n_glitch + 1;
                        end else if (addressed) seen_ours = 1'b1;
                        else if (seen_ours) n_nack = n_nack + 1;
                        else n_probe = n_probe + 1;
                        sda_low = addressed;
                    end else if (addressed) begin
                        if (nbyte == 1) ptr = sh;
                        else begin write_reg(ptr, sh); ptr = ptr + 1; end
                        sda_low = 1'b1;
                    end else if (n_glitch == 0 || $realtime < GLITCH_FROM_NS || $realtime >= GLITCH_TO_NS)
                        n_nack = n_nack + 1;                // data after a NACKed address
                    nbyte = nbyte + 1;
                end
            end else begin
                sda_low = (bitc < 8) ? !regs[ptr][7 - bitc] : 1'b0;   // next bit, then let go
            end
        end else begin                                      // end of the ACK clock
            bitc = 0;
            if (!sending) begin
                sda_low = 1'b0;
                if (addressed && rd && nbyte == 1) begin    // our address, read: send
                    sending = 1'b1; sda_low = !regs[ptr][7];
                end
            end else if (mack) begin
                ptr = ptr + 1; sda_low = !regs[ptr][7];
            end else begin
                sending = 1'b0; active = 1'b0; sda_low = 1'b0;   // NACK: done, STOP follows
            end
        end
    end
endmodule
