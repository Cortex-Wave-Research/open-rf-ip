// Target implementation harness: native 12 MHz, no PLL, same pins as NCO harness.
module chirp_top (
    input logic clk,
    output logic activity
);
    logic [3:0] startup = 4'b1111;
    logic signed [13:0] i_sample, q_sample;
    logic sample_valid, chirp_start, chirp_end, busy;
    // Scheduling monitor ports are unused by this hardware harness.
    // Their underlying state remains necessary for NCO/control operation.
    logic [31:0] unused_phase_increment, unused_chirp_count;
    always_ff @(posedge clk)
        startup <= {startup[2:0], 1'b0};

    rf_chirp_nco chirp (
        .clk(clk), .rst(startup[3]), .enable(1'b1), .start(1'b1),
        // Exact model-derived demo words. At native 12 MHz these frequencies
        // scale by 0.12 and active duration is 833.333 us, not the 100 MHz demo.
        .start_phase_inc(32'd85899346), .chirp_step(32'sd77317),
        .chirp_length(32'd10000), .repeat_mode(1'b1),
        .i_out(i_sample), .q_out(q_sample), .sample_valid(sample_valid),
        .chirp_start(chirp_start), .chirp_end(chirp_end), .busy(busy),
        .phase_increment(unused_phase_increment), .chirp_count(unused_chirp_count)
    );
    always_ff @(posedge clk) begin
        if (startup[3])
            activity <= 1'b0;
        else
            activity <= ^{i_sample, q_sample, sample_valid, chirp_start, chirp_end,
                          busy};
    end
endmodule
