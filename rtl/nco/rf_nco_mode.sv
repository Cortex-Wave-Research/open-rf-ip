// Elaboration-time selector. Original rf_nco interface/source remains available.
// No runtime mode mux; only the selected branch is synthesized.
module rf_nco_mode #(
    parameter integer HIGH_PURITY = 0,
    parameter integer PHASE_WIDTH = (HIGH_PURITY != 0) ? 64 : 32,
    parameter integer OUTPUT_WIDTH = (HIGH_PURITY != 0) ? 18 : 14
) (
    input logic clk, rst, enable,
    input logic [PHASE_WIDTH-1:0] phase_increment,
    output logic signed [OUTPUT_WIDTH-1:0] i_out, q_out,
    output logic sample_valid
);
    if ((HIGH_PURITY != 0 && HIGH_PURITY != 1) ||
        PHASE_WIDTH != ((HIGH_PURITY != 0) ? 64 : 32) ||
        OUTPUT_WIDTH != ((HIGH_PURITY != 0) ? 18 : 14)) begin : invalid_configuration
        initial $fatal(1, "rf_nco_mode supports only COMPACT 32/14 or HIGH_PURITY 64/18");
    end
    if (HIGH_PURITY != 0) begin : high_purity
        rf_nco_high_purity nco (.clk(clk), .rst(rst), .enable(enable),
            .sample_enable(1'b1), .phase_increment(phase_increment),
            .i_out(i_out), .q_out(q_out), .sample_valid(sample_valid));
    end else begin : compact
        rf_nco nco (.clk(clk), .rst(rst), .enable(enable),
            .phase_increment(phase_increment), .i_out(i_out), .q_out(q_out),
            .sample_valid(sample_valid));
    end
endmodule
