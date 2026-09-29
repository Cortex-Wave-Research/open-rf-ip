// Implementation harness only. Native EVN clock: U1, 12 MHz, ball L13.
// No PLL. Higher nextpnr --freq values are timing experiments, not board clocks.
module nco_top (
    input logic clk,
    output logic activity
);
    // FPGA configuration initialization followed by four synchronous reset edges.
    logic [3:0] startup = 4'b1111;
    logic signed [13:0] i_sample, q_sample;
    logic sample_valid;

    always_ff @(posedge clk)
        startup <= {startup[2:0], 1'b0};

    rf_nco #(.PHASE_WIDTH(32), .OUTPUT_WIDTH(14), .LUT_ADDR_WIDTH(10)) nco (
        .clk(clk), .rst(startup[3]), .enable(1'b1),
        // round(2^32 / 12): approximately 1 MHz at the native 12 MHz clock.
        // Odd increment exercises the complete accumulator state space.
        .phase_increment(32'h15555555),
        .i_out(i_sample), .q_out(q_sample), .sample_valid(sample_valid)
    );

    // Consume every sample bit to retain the full NCO without sample-stream IO.
    // This is an activity signature, not a readable waveform or slow heartbeat.
    always_ff @(posedge clk) begin
        if (startup[3])
            activity <= 1'b0;
        else
            activity <= ^{i_sample, q_sample, sample_valid};
    end
endmodule
